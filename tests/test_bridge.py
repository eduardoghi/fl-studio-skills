"""Tests for the bridge, with FL Studio's modules faked in memory.

Run with `python3 -m unittest discover -s tests`. The server tools need the mcp package.
"""

import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bridge"))

from fl_bridge import client, doorbell, hotkey, paths, render

SCRIPTS = ROOT / "bridge" / "fl_scripts"


class FakeFL:
    """The parts of FL's API that the device script calls."""

    def __init__(self):
        self.params = [("?", 0.0), ("Reverb size", 0.4), ("Reverb decay", 0.5), ("Mix", 0.2), ("mix ", 0.3)]
        self.grid = {}
        self.muted = {6: False}
        self.playing = False

    def modules(self):
        fl = self
        plugins = types.SimpleNamespace(
            isValid=lambda index, slot=-1: index == 9,
            getPluginName=lambda index, slot=-1: "LuxeVerb",
            getParamCount=lambda index, slot=-1: len(fl.params),
            getParamName=lambda i, index, slot=-1: fl.params[i][0],
            getParamValue=lambda i, index, slot=-1: fl.params[i][1],
            getParamValueString=lambda i, index, slot=-1: f"{fl.params[i][1]:.2f}x ",
            setParamValue=lambda value, i, index, slot=-1: fl.params.__setitem__(i, (fl.params[i][0], value)),
            getPadInfo=lambda channel, slot, option, pad: 2 if option == 0 else [36, 38][pad],
            getPresetCount=lambda index, slot=-1: 3,
        )
        mixer = types.SimpleNamespace(
            getCurrentTempo=lambda: 95000,
            trackCount=lambda: 12,
            getTrackName=lambda t: "Master" if t == 0 else f"Insert {t}",
            getTrackVolume=lambda t: 0.8,
            getTrackPan=lambda t: 0.0,
            isTrackMuted=lambda t: fl.muted.get(t, False),
            isTrackSolo=lambda t: False,
            muteTrack=lambda t: fl.muted.__setitem__(t, not fl.muted.get(t, False)),
        )
        channels = types.SimpleNamespace(
            channelCount=lambda: 2, setGridBit=lambda c, p, v: fl.grid.__setitem__((c, p), v)
        )
        transport = types.SimpleNamespace(
            isPlaying=lambda: fl.playing, start=lambda: setattr(fl, "playing", True), stop=lambda: None
        )
        return {
            "channels": channels,
            "general": types.SimpleNamespace(getVersion=lambda: 45),
            "midi": types.SimpleNamespace(MIDI_CONTROLCHANGE=176),
            "mixer": mixer,
            "patterns": types.SimpleNamespace(patternNumber=lambda: 1),
            "plugins": plugins,
            "transport": transport,
            "ui": types.SimpleNamespace(),
        }


class DeviceScript(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.fl = FakeFL()
        self.previous = os.getcwd()
        os.chdir(self.folder)
        self.addCleanup(os.chdir, self.previous)
        patcher = mock.patch.dict(sys.modules, self.fl.modules())
        patcher.start()
        self.addCleanup(patcher.stop)
        spec = importlib.util.spec_from_file_location("device_ClaudeBridge", SCRIPTS / "device_ClaudeBridge.py")
        self.device = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.device)

    def ask(self, command, params=None, request_id="a"):
        (self.folder / "request.json").write_text(json.dumps({"id": request_id, "command": command, "params": params}))
        self.device.OnMidiMsg(types.SimpleNamespace(midiId=176, midiChan=15, data1=110, handled=False))
        return json.loads((self.folder / "response.json").read_text())

    def test_first_line_names_the_controller(self):
        self.assertEqual((SCRIPTS / "device_ClaudeBridge.py").read_text().splitlines()[0], "# name=Claude Bridge")

    def test_other_midi_is_left_alone(self):
        event = types.SimpleNamespace(midiId=176, midiChan=0, data1=110, handled=False)
        self.device.OnMidiMsg(event)
        self.assertFalse(event.handled)
        self.assertFalse((self.folder / "response.json").exists())

    def test_the_same_request_only_runs_once(self):
        self.ask("transport", {"action": "play"})
        self.fl.playing = False
        self.ask("transport", {"action": "play"})
        self.assertFalse(self.fl.playing)

    def test_unknown_command_is_reported(self):
        self.assertIn("unknown command", self.ask("nope")["error"])

    def test_plugin_set_finds_by_name_and_reads_back(self):
        answer = self.ask("plugin_set", {"track": 9, "slot": 2, "name": "reverb SIZE", "value": 0.6})
        self.assertEqual(answer["result"]["before"], 0.4)
        self.assertEqual(answer["result"]["value"], 0.6)
        self.assertEqual(answer["result"]["text"], "0.60x")

    def test_plugin_set_refuses_an_ambiguous_or_unknown_name(self):
        self.assertIn(
            "matches 2", self.ask("plugin_set", {"track": 9, "slot": 2, "name": "mix", "value": 0.1})["error"]
        )
        self.assertIn(
            "no parameter", self.ask("plugin_set", {"track": 9, "slot": 2, "name": "x", "value": 0.1}, "b")["error"]
        )

    def test_plugin_set_refuses_a_value_out_of_range(self):
        self.assertIn(
            "between 0 and 1", self.ask("plugin_set", {"track": 9, "slot": 2, "name": "Mix", "value": 2})["error"]
        )

    def test_plugin_params_skips_empty_slots(self):
        result = self.ask("plugin_params", {"track": 9, "slot": 2, "contains": "reverb"})["result"]
        self.assertEqual([p["name"] for p in result["params"]], ["Reverb size", "Reverb decay"])

    def test_missing_plugin_is_reported(self):
        self.assertIn("no plugin", self.ask("plugin_params", {"track": 3, "slot": 0})["error"])

    def test_mute_only_toggles_when_needed(self):
        self.ask("mixer_set", {"track": 6, "muted": False})
        self.assertFalse(self.fl.muted[6])
        self.ask("mixer_set", {"track": 6, "muted": True}, "b")
        self.ask("mixer_set", {"track": 6, "muted": True}, "c")
        self.assertTrue(self.fl.muted[6])

    def test_pad_map(self):
        self.fl.params = []
        answer = self.ask("pad_map", {"channel": 9})
        self.assertEqual(answer["result"], [{"pad": 0, "note": 36}, {"pad": 1, "note": 38}])

    def test_steps_reject_a_channel_that_does_not_exist(self):
        self.assertIn("no channel", self.ask("channel_steps", {"channel": 8, "steps": [True]})["error"])

    def test_file_errors_from_fl_reach_the_server(self):
        def blocked():
            raise SystemError("returned NULL without setting an exception")

        self.device.HANDLERS["ping"] = lambda params: blocked()
        self.assertIn("SystemError", self.ask("ping")["error"])


class PianoRollScript(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.previous = os.getcwd()
        os.chdir(self.folder)
        self.addCleanup(os.chdir, self.previous)

    def run_script(self, queue):
        (self.folder / "pianoroll_queue.json").write_text(json.dumps(queue))
        score = types.SimpleNamespace(PPQ=96, noteCount=1, added=[])
        score.addNote = score.added.append
        score.clearNotes = lambda everything: None
        score.getNote = lambda i: types.SimpleNamespace(number=60, time=192, length=96, velocity=0.5)

        class Note:
            pass

        messages = []
        fake = types.SimpleNamespace(score=score, Note=Note, Utils=types.SimpleNamespace(ShowMessage=messages.append))
        with mock.patch.dict(sys.modules, {"flpianoroll": fake}):
            source = (SCRIPTS / "ClaudeBridge.pyscript").read_text(encoding="utf-8")
            exec(compile(source, "ClaudeBridge.pyscript", "exec"), {"__name__": "fl"})  # noqa: S102
        return score, messages

    def done(self):
        return json.loads((self.folder / "pianoroll_done.json").read_text())

    def test_add_notes_converts_beats_and_clears_the_queue(self):
        score, _ = self.run_script(
            {"id": "a", "action": "add_notes", "payload": {"notes": [{"pitch": 60, "start": 2, "length": 0.5}]}}
        )
        self.assertEqual((score.added[0].time, score.added[0].length), (192, 48))
        self.assertEqual((self.folder / "pianoroll_queue.json").read_text(), "{}")
        self.assertEqual(self.done(), {"id": "a", "ok": True, "result": {"added": 1}})

    def test_wrong_note_count_refuses_the_write(self):
        score, _ = self.run_script(
            {
                "id": "a",
                "action": "add_notes",
                "expect_notes": 5,
                "payload": {"notes": [{"pitch": 60, "start": 0, "length": 1}]},
            }
        )
        self.assertEqual(score.added, [])
        self.assertIn("expected 5 notes, found 1", self.done()["error"])
        self.assertEqual((self.folder / "pianoroll_queue.json").read_text(), "{}")

    def test_matching_note_count_lets_the_write_through(self):
        score, _ = self.run_script(
            {
                "id": "a",
                "action": "add_notes",
                "expect_notes": 1,
                "payload": {"notes": [{"pitch": 60, "start": 0, "length": 1}]},
            }
        )
        self.assertEqual(len(score.added), 1)

    def test_read_returns_beats(self):
        self.run_script({"id": "a", "action": "read"})
        self.assertEqual(self.done()["result"]["notes"], [{"pitch": 60, "start": 2.0, "length": 1.0, "velocity": 0.5}])

    def test_unknown_action_is_reported_and_queue_cleared(self):
        self.run_script({"id": "a", "action": "nope"})
        self.assertFalse(self.done()["ok"])
        self.assertEqual((self.folder / "pianoroll_queue.json").read_text(), "{}")

    def test_empty_queue_tells_the_user(self):
        _, messages = self.run_script({})
        self.assertIn("nothing queued", messages[0])


class Client(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        patcher = mock.patch.dict(
            os.environ, {"FL_BRIDGE_DIR": str(self.folder), "FL_BRIDGE_PIANO_ROLL_DIR": str(self.folder)}
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def answer(self, **fields):
        def ring():
            request = json.loads((self.folder / "request.json").read_text())
            (self.folder / "response.json").write_text(json.dumps({"id": request["id"], **fields}))

        return ring

    def test_returns_the_result(self):
        self.assertEqual(client.call("ping", ring=self.answer(ok=True, result=1)), 1)

    def test_raises_what_fl_reported(self):
        with self.assertRaisesRegex(client.BridgeError, "broken"):
            client.call("ping", ring=self.answer(ok=False, error="broken"))

    def test_ignores_an_old_response(self):
        (self.folder / "response.json").write_text(json.dumps({"id": "old", "ok": True, "result": 1}))
        with self.assertRaisesRegex(client.BridgeError, "didn't answer"):
            client.call("ping", timeout=0.05, ring=lambda: None)

    def test_partial_response_reads_as_nothing(self):
        (self.folder / "response.json").write_text('{"id": "a", "ok"')
        self.assertIsNone(client.read_json(self.folder / "response.json"))

    def test_missing_folder_points_to_the_installer(self):
        missing = {"FL_BRIDGE_DIR": str(self.folder / "nope")}
        with mock.patch.dict(os.environ, missing), self.assertRaisesRegex(client.BridgeError, "install.py"):
            client.call("ping", ring=lambda: None)

    def test_piano_roll_error_is_raised(self):
        request = client.queue_piano_roll("clear")
        (self.folder / "pianoroll_done.json").write_text(json.dumps({"id": request, "ok": False, "error": "bad"}))
        with self.assertRaisesRegex(client.BridgeError, "bad"):
            client.piano_roll_result(request)

    def focus(self, caption, selected=9):
        calls = []

        def command(name, params=None):
            calls.append(name)
            if name == "focus_state":
                return {"selected": selected, "name": "Guitar", "piano_roll_focused": True, "caption": caption}
            return {}

        return calls, client.focus_piano_roll(9, command=command, sleep=lambda _: None)

    def test_focus_uses_separate_requests(self):
        calls, _ = self.focus("Piano roll - Guitar")
        self.assertEqual(calls, ["channel_select", "piano_roll_show", "focus_state"])

    def test_focus_accepts_the_caption_fl_really_reports(self):
        self.focus("Piano roll -")

    def test_focus_refuses_when_another_channel_is_selected(self):
        with self.assertRaisesRegex(client.BridgeError, "didn't open"):
            self.focus("Piano roll -", selected=3)

    def test_focus_refuses_when_another_window_has_focus(self):
        with self.assertRaisesRegex(client.BridgeError, "didn't open"):
            self.focus("Channel rack")

    def test_settled_fails_when_fl_disagrees(self):
        with (
            mock.patch.object(client, "call", return_value={"muted": False}),
            self.assertRaisesRegex(client.BridgeError, "muted=False"),
        ):
            client.settled("mixer_get", {}, {"muted": True}, sleep=lambda _: None)

    def test_settled_ignores_values_that_were_not_changed(self):
        with mock.patch.object(client, "call", return_value={"muted": False}):
            self.assertEqual(client.settled("mixer_get", {}, {"muted": None}, sleep=lambda _: None), {"muted": False})

    def test_piano_roll_not_run_yet(self):
        self.assertIsNone(client.piano_roll_result(client.queue_piano_roll("read")))


class Doorbell(unittest.TestCase):
    def test_message_is_control_change_110_on_channel_16(self):
        self.assertEqual(doorbell.trigger_message(), 0x7F6EBF)

    def test_finds_the_port_by_part_of_its_name(self):
        self.assertEqual(doorbell.find_port(["Microsoft GS", "FL MCP 1"], "fl mcp"), 1)

    def test_missing_port_mentions_loopmidi(self):
        with self.assertRaisesRegex(doorbell.DoorbellError, "loopMIDI"):
            doorbell.find_port(["Microsoft GS"], "FL MCP")


class Hotkey(unittest.TestCase):
    def test_only_fl_processes_count(self):
        self.assertTrue(hotkey.is_fl(r"C:\Program Files\Image-Line\FL Studio 2026\FL64.exe"))
        self.assertFalse(hotkey.is_fl(r"C:\Windows\explorer.exe"))
        self.assertFalse(hotkey.is_fl(""))

    def test_keys_are_released_in_reverse_order(self):
        sequence = hotkey.key_sequence()
        self.assertEqual([key for key, released in sequence if not released], [0x11, 0x12, 0x59])
        self.assertEqual([key for key, released in sequence if released], [0x59, 0x12, 0x11])


class Render(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.project = self.folder / "song.flp"
        self.project.write_bytes(b"FLhd")

    def test_refuses_when_fl_is_open(self):
        with self.assertRaisesRegex(render.RenderError, "open"):
            render.render(self.project, self.folder / "a.wav", running=lambda: True)

    def fake_run(self, size, code=0):
        def run(command, check, timeout):
            if size:
                Path(command[1][2:]).write_bytes(b"x" * size)
            return types.SimpleNamespace(returncode=code)

        return run

    def test_writes_the_output(self):
        output = self.folder / "out" / "a.wav"
        with mock.patch.dict(os.environ, {"FL_STUDIO_EXE": "FL64.exe"}):
            size = render.render(self.project, output, running=lambda: False, run=self.fake_run(2000))
        self.assertEqual((size, output.is_file()), (2000, True))

    def test_exit_without_a_file_is_an_error(self):
        exe = {"FL_STUDIO_EXE": "FL64.exe"}
        with mock.patch.dict(os.environ, exe), self.assertRaisesRegex(render.RenderError, "without writing"):
            render.render(self.project, self.folder / "a.wav", running=lambda: False, run=self.fake_run(0))

    def test_never_passes_the_real_project_to_fl(self):
        seen = []

        def run(command, check, timeout):
            seen.append(command[-1])
            Path(command[1][2:]).write_bytes(b"x" * 2000)
            return types.SimpleNamespace(returncode=0)

        with mock.patch.dict(os.environ, {"FL_STUDIO_EXE": "FL64.exe"}):
            render.render(self.project, self.folder / "a.wav", running=lambda: False, run=run)
        self.assertNotEqual(seen[0], str(self.project))


class Paths(unittest.TestCase):
    def test_environment_overrides_the_mailbox(self):
        with mock.patch.dict(os.environ, {"FL_BRIDGE_DIR": "somewhere"}):
            self.assertEqual(paths.device_dir(), Path("somewhere"))


class Server(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from fl_bridge import server
        except ImportError:
            raise unittest.SkipTest("the server needs the mcp package") from None
        cls.server = server

    def test_color_matches_what_fl_stores(self):
        self.assertEqual(self.server.rgb("#2F45A8"), -13679192)

    def test_bad_color_is_refused(self):
        with self.assertRaises(ValueError):
            self.server.rgb("red")

    def test_target_needs_a_channel_or_a_full_effect_address(self):
        self.assertEqual(self.server._target(3, None, None), {"channel": 3})
        with self.assertRaises(ValueError):
            self.server._target(None, 9, None)

    def test_notes_are_checked_before_queueing(self):
        with self.assertRaisesRegex(ValueError, "note 0"):
            self.server.fl_queue_notes([{"pitch": 200, "start": 0, "length": 1}], 0)

    def test_steps_are_checked_before_sending(self):
        with self.assertRaises(ValueError):
            self.server.fl_channel_steps(0, "10x")


if __name__ == "__main__":
    unittest.main()
