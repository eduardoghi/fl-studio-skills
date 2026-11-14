"""Tests for the bridge, with FL Studio's modules faked in memory.

Run with `python3 -m unittest discover -s tests`. The server tools need the mcp package.
"""

import importlib.util
import json
import os
import struct
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
import zlib
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bridge"))

from fl_bridge import client, doorbell, notes, paths, render, window

SCRIPTS = ROOT / "bridge" / "fl_scripts"
NOTE = {"pitch": 60, "start": 0, "length": 1}


class FakeFL:
    """The parts of FL's API that the device script calls."""

    def __init__(self):
        self.params = [("?", 0.0), ("Reverb size", 0.4), ("Reverb decay", 0.5), ("Mix", 0.2), ("mix ", 0.3)]
        self.grid = {}
        self.names = {}
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
            channelCount=lambda: 2,
            setGridBit=lambda c, p, v: fl.grid.__setitem__((c, p), v),
            setChannelName=lambda c, name: fl.names.__setitem__(c, name),
            getChannelName=lambda c: fl.names.get(c, f"Channel {c}"),
            getChannelVolume=lambda c: 0.78,
            getChannelPan=lambda c: 0.0,
            isChannelMuted=lambda c: False,
            getTargetFxTrack=lambda c: 0,
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

    def test_plugin_params_hides_placeholders_and_counts_them(self):
        self.fl.params = [
            ("Level (p1)", 0.7),
            ("Param 8", 0.1),
            ("5. ", 0.0),
            ("MIDI CC #1 (Modulation wheel)", 0.0),
            ("MIDI Channel 1 Aftertouch", 0.0),
        ]
        result = self.ask("plugin_params", {"track": 9, "slot": 2})["result"]
        self.assertEqual([p["name"] for p in result["params"]], ["Level (p1)"])
        self.assertEqual((result["count"], result["hidden"]), (1, 4))

    def test_plugin_params_can_show_placeholders(self):
        self.fl.params = [("Level (p1)", 0.7), ("MIDI CC #1 (Modulation wheel)", 0.0)]
        result = self.ask("plugin_params", {"track": 9, "slot": 2, "contains": "cc #1", "named_only": False})["result"]
        self.assertEqual([p["name"] for p in result["params"]], ["MIDI CC #1 (Modulation wheel)"])
        self.assertEqual(result["hidden"], 0)

    def test_placeholder_check_keeps_real_names(self):
        for name in ("1. Bleed - OH", "Param Link", "Level (p1)", "Mix"):
            with self.subTest(name=name):
                self.assertFalse(self.device._is_placeholder(name))

    def test_limit_applies_after_hiding_placeholders(self):
        self.fl.params = [("Param 1", 0.0), ("Param 2", 0.0), ("Mix", 0.2)]
        result = self.ask("plugin_params", {"track": 9, "slot": 2, "limit": 1})["result"]
        self.assertEqual([p["name"] for p in result["params"]], ["Mix"])

    def test_channel_set_renames_a_channel(self):
        answer = self.ask("channel_set", {"channel": 1, "name": "Pad"})
        self.assertEqual(self.fl.names[1], "Pad")
        self.assertEqual(answer["result"]["name"], "Pad")

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

    def run_script(self, queue, velocity=0.5):
        if queue is not None:
            (self.folder / "pianoroll_queue.json").write_text(json.dumps(queue))
        score = types.SimpleNamespace(PPQ=96, noteCount=1, added=[])
        score.addNote = score.added.append
        score.clearNotes = lambda everything: None
        score.getNote = lambda i: types.SimpleNamespace(number=60, time=192, length=96, velocity=velocity)

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
        self.assertEqual(self.done()["result"]["added"], 1)

    def test_other_notes_refuse_the_write(self):
        score, _ = self.run_script({"id": "a", "action": "add_notes", "expect": "abc", "payload": {"notes": [NOTE]}})
        self.assertEqual(score.added, [])
        self.assertIn("expected fingerprint abc", self.done()["error"])
        self.assertEqual((self.folder / "pianoroll_queue.json").read_text(), "{}")

    def test_matching_fingerprint_lets_the_write_through(self):
        self.run_script({"id": "a", "action": "read"})
        expected = self.done()["result"]["fingerprint"]
        score, _ = self.run_script({"id": "b", "action": "add_notes", "expect": expected, "payload": {"notes": [NOTE]}})
        self.assertEqual(len(score.added), 1)

    def test_fingerprint_tells_apart_channels_with_the_same_count(self):
        self.run_script({"id": "a", "action": "read"})
        first = self.done()["result"]["fingerprint"]
        self.run_script({"id": "b", "action": "read"}, velocity=0.6)
        self.assertNotEqual(self.done()["result"]["fingerprint"], first)

    def test_fingerprint_counts_velocity_in_fl_steps(self):
        # 0.787 is what was written and 0.789 what FL kept (101/128), so both must give the same fingerprint.
        self.run_script({"id": "a", "action": "read"}, velocity=0.787)
        written = self.done()["result"]["fingerprint"]
        self.run_script({"id": "b", "action": "read"}, velocity=101 / 128)
        self.assertEqual(self.done()["result"]["fingerprint"], written)

    def test_add_notes_stores_velocity_on_fl_steps(self):
        note = dict(NOTE, velocity=0.787)
        score, _ = self.run_script({"id": "a", "action": "add_notes", "payload": {"notes": [note]}})
        self.assertEqual(score.added[0].velocity, 101 / 128)

    def test_a_bad_note_stops_the_whole_action(self):
        notes = [NOTE, {"pitch": "x", "start": 0, "length": 1}]
        score, _ = self.run_script({"id": "a", "action": "add_notes", "payload": {"notes": notes}})
        self.assertEqual(score.added, [])
        self.assertFalse(self.done()["ok"])

    def test_read_returns_beats(self):
        self.run_script({"id": "a", "action": "read"})
        self.assertEqual(self.done()["result"]["notes"], [{"pitch": 60, "start": 2.0, "length": 1.0, "velocity": 0.5}])

    def test_unknown_action_is_reported_and_queue_cleared(self):
        self.run_script({"id": "a", "action": "nope"})
        self.assertFalse(self.done()["ok"])
        self.assertEqual((self.folder / "pianoroll_queue.json").read_text(), "{}")

    def test_empty_queue_does_nothing_quietly(self):
        score, messages = self.run_script({})
        self.assertEqual((score.added, messages), ([], []))
        self.assertFalse((self.folder / "pianoroll_done.json").exists())

    def test_missing_queue_does_nothing_quietly(self):
        score, messages = self.run_script(None)
        self.assertEqual((score.added, messages), ([], []))
        self.assertFalse((self.folder / "pianoroll_done.json").exists())


class Client(unittest.TestCase):
    def setUp(self):
        # Windows can keep the lock file busy for a moment after the process holding it is killed.
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
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
        self.assertEqual(calls, ["piano_roll_hide", "channel_select", "piano_roll_show", "focus_state"])

    def test_focus_accepts_the_caption_fl_really_reports(self):
        self.focus("Piano roll -")

    def test_focus_refuses_when_another_channel_is_selected(self):
        with self.assertRaisesRegex(client.BridgeError, "didn't open"):
            self.focus("Piano roll -", selected=3)

    def test_focus_tries_again_when_the_selection_misses(self):
        answers = iter([{"selected": 3}, {"selected": 9}])

        def command(name, params=None):
            if name != "focus_state":
                return {}
            return {**next(answers), "piano_roll_focused": True, "caption": "Piano roll -"}

        state = client.focus_piano_roll(9, command=command, sleep=lambda _: None)
        self.assertEqual(state["selected"], 9)

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

    def test_a_waiting_action_is_not_replaced(self):
        client.queue_piano_roll("add_notes", {"notes": []})
        with self.assertRaisesRegex(client.BridgeError, "still queued"):
            client.queue_piano_roll("clear")
        self.assertEqual(client.read_json(self.folder / "pianoroll_queue.json")["action"], "add_notes")

    def test_discard_frees_the_queue(self):
        client.queue_piano_roll("read")
        self.assertEqual(client.discard_piano_roll(), "read")
        self.assertIsNone(client.discard_piano_roll())
        client.queue_piano_roll("clear")

    def test_a_finished_action_frees_the_queue(self):
        client.queue_piano_roll("read")
        (self.folder / "pianoroll_queue.json").write_text("{}")
        client.queue_piano_roll("clear")

    def test_concurrent_calls_get_their_own_answers(self):
        def ring():
            request = json.loads((self.folder / "request.json").read_text())
            time.sleep(0.01)
            answer = {"id": request["id"], "ok": True, "result": request["params"]["n"]}
            (self.folder / "response.json").write_text(json.dumps(answer))

        results = {}

        def work(n):
            results[n] = client.call("ping", {"n": n}, timeout=5, ring=ring)

        threads = [threading.Thread(target=work, args=(n,)) for n in range(12)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(results, {n: n for n in range(12)})

    def test_lock_held_by_another_process_times_out(self):
        code = (
            "import sys, time; sys.path.insert(0, sys.argv[1]); from fl_bridge import client; from pathlib import Path\n"
            "handle = open(Path(sys.argv[2]) / 'bridge.lock', 'a+b'); client._lock_file(handle)\n"
            "print('held', flush=True); time.sleep(3)\n"
        )
        holder = subprocess.Popen(
            [sys.executable, "-c", code, str(ROOT / "bridge"), str(self.folder)], stdout=subprocess.PIPE, text=True
        )
        self.addCleanup(holder.wait)
        self.addCleanup(holder.stdout.close)
        self.addCleanup(holder.kill)
        self.assertEqual(holder.stdout.readline().strip(), "held")
        with self.assertRaisesRegex(client.BridgeError, "another process"), client.exclusive(self.folder, timeout=0.2):
            pass

    def test_lock_is_free_after_use(self):
        with client.exclusive(self.folder):
            pass
        with client.exclusive(self.folder, timeout=0.2):
            pass

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


class Window(unittest.TestCase):
    def test_only_fl_processes_count(self):
        self.assertTrue(window.is_fl(r"C:\Program Files\Image-Line\FL Studio 2026\FL64.exe"))
        self.assertFalse(window.is_fl(r"C:\Windows\explorer.exe"))
        self.assertFalse(window.is_fl(""))

    def capture_with(self, color, width=10, height=10):
        b, g, r = color
        return bytes([b, g, r, 255] * width * height), width

    def test_radio_reads_the_orange_of_an_option_that_is_on(self):
        pixels, width = self.capture_with((137, 172, 243))  # BGR read from an option that was on
        self.assertTrue(window.radio_is_on(pixels, width, (5, 5)))

    def test_radio_reads_grey_as_off(self):
        pixels, width = self.capture_with((70, 70, 70))
        self.assertFalse(window.radio_is_on(pixels, width, (5, 5)))

    def test_expected_window_matches_part_of_the_class(self):
        self.assertTrue(window.expected_window("JUCE_1a1d788206b", "juce"))
        self.assertFalse(window.expected_window("TEventEditForm", "JUCE"))
        self.assertTrue(window.expected_window("TEventEditForm", None))

    def test_ppq_keys_count_rows_of_the_list(self):
        self.assertEqual(window.ppq_keys(96, 960), ["down"] * 7)
        self.assertEqual(window.ppq_keys(960, 96), ["up"] * 7)
        self.assertEqual(window.ppq_keys(96, 96), [])
        with self.assertRaises(window.WindowError):
            window.ppq_keys(96, 100)

    def test_from_top_left_scales_with_the_form(self):
        self.assertEqual(window.from_top_left((22, 183), (386, 291), (386, 291)), (22, 183))
        self.assertEqual(window.from_top_left((22, 183), (772, 582), (386, 291)), (44, 366))

    def test_inside_excludes_the_right_and_bottom_edges(self):
        self.assertTrue(window.inside((10, 20, 100, 50), 10, 20))
        self.assertFalse(window.inside((10, 20, 100, 50), 110, 30))
        self.assertFalse(window.inside((10, 20, 100, 50), 50, 70))

    def test_popup_size_leaves_out_menu_shadows(self):
        self.assertTrue(window.popup_size((424, 316, 199, 191)))
        self.assertFalse(window.popup_size((424, 507, 199, 12)))
        self.assertFalse(window.popup_size((623, 304, 12, 215)))

    def test_click_param_keeps_negative_coordinates(self):
        self.assertEqual(window.click_param(135, 629), (629 << 16) | 135)
        self.assertEqual(window.click_param(-1, 0), 0xFFFF)

    def test_key_param_marks_alt_and_release(self):
        self.assertEqual(window.key_param(0x15, False, False), 0x00150001)
        self.assertEqual(window.key_param(0x15, True, False), 0x20150001)
        self.assertEqual(window.key_param(0x15, False, True), 0xC0150001)

    def test_alt_shortcuts_use_system_key_messages(self):
        self.assertEqual(window.key_message(True, False), window.WM_SYSKEYDOWN)
        self.assertEqual(window.key_message(True, True), window.WM_SYSKEYUP)
        self.assertEqual(window.key_message(False, False), window.WM_KEYDOWN)

    def test_wheel_param_is_signed(self):
        self.assertEqual(window.wheel_param(1), 120 << 16)
        self.assertEqual(window.wheel_param(-1), (0x10000 - 120) << 16)

    def test_unknown_menu_key_is_refused(self):
        self.assertEqual(window.menu_key("down"), window.VK_DOWN)
        with self.assertRaisesRegex(window.WindowError, "unknown menu key"):
            window.menu_key("space")

    def test_ghost_style_hides_and_lets_clicks_through(self):
        style = window.ghosted(0x50000)
        self.assertTrue(style & window.WS_EX_LAYERED)
        self.assertTrue(style & window.WS_EX_TRANSPARENT)
        self.assertEqual(style & 0x50000, 0x50000)
        self.assertTrue(window.is_ghost(style))

    def test_one_ghost_bit_alone_is_not_a_ghost(self):
        self.assertFalse(window.is_ghost(window.WS_EX_LAYERED))
        self.assertFalse(window.is_ghost(0x50000))

    def test_unghosted_keeps_the_other_bits(self):
        self.assertEqual(window.unghosted(window.ghosted(0x50000)), 0x50000)

    def test_dialog_is_centered_on_fl(self):
        self.assertEqual(window.centered((207, 21, 2777, 1240), (433, 611)), (1379, 335))

    def test_points_follow_the_bottom_right_of_a_larger_form(self):
        self.assertEqual(window.scaled((290, 587), (433, 611)), (290, 587))
        self.assertEqual(window.scaled((290, 587), (450, 630)), (307, 606))

    def test_crop_returns_the_asked_pixels(self):
        pixels = bytes(range(24))  # Two rows of three BGRA pixels.
        cut, width, height = window.crop(pixels, 3, 2, (1, 1, 2, 1))
        self.assertEqual((width, height), (2, 1))
        self.assertEqual(cut, bytes(range(16, 24)))

    def test_crop_refuses_a_region_outside_the_image(self):
        with self.assertRaisesRegex(window.WindowError, "outside"):
            window.crop(bytes(16), 2, 2, (5, 0, 1, 1))

    def test_png_holds_the_pixels_in_rgb(self):
        png = window.encode_png(bytes([1, 2, 3, 255, 4, 5, 6, 255]), 2, 1)
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", png[16:24]), (2, 1))
        start = png.index(b"IDAT") + 4
        length = struct.unpack(">I", png[start - 8 : start - 4])[0]
        self.assertEqual(zlib.decompress(png[start : start + length]), bytes([0, 3, 2, 1, 6, 5, 4]))


class Render(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.project = self.folder / "song.flp"
        self.project.write_bytes(b"FLhd")

    def test_refuses_to_replace_an_existing_file(self):
        output = self.folder / "a.wav"
        output.write_bytes(b"old")
        with self.assertRaisesRegex(render.RenderError, "already exists"):
            render.render(self.project, output, running=lambda: False)
        self.assertEqual(output.read_bytes(), b"old")

    def test_overwrite_replaces_it(self):
        output = self.folder / "a.wav"
        output.write_bytes(b"old")
        with mock.patch.dict(os.environ, {"FL_STUDIO_EXE": "FL64.exe"}):
            render.render(self.project, output, overwrite=True, running=lambda: False, run=self.fake_run(2000))
        self.assertEqual(output.stat().st_size, 2000)

    def test_copy_stays_next_to_the_project_and_is_removed(self):
        seen = []

        def run(command, check, timeout):
            seen.append(Path(command[-1]))
            self.assertTrue(seen[0].exists())
            Path(command[1][2:]).write_bytes(b"x" * 2000)
            return types.SimpleNamespace(returncode=0)

        with mock.patch.dict(os.environ, {"FL_STUDIO_EXE": "FL64.exe"}):
            render.render(self.project, self.folder / "a.wav", running=lambda: False, run=run)
        self.assertEqual(seen[0].parent, self.project.parent)
        self.assertFalse(seen[0].exists())

    def test_copy_is_removed_when_fl_hangs(self):
        def run(command, check, timeout):
            raise subprocess.TimeoutExpired(command, timeout)

        with mock.patch.dict(os.environ, {"FL_STUDIO_EXE": "FL64.exe"}), self.assertRaises(render.RenderError):
            render.render(self.project, self.folder / "a.wav", running=lambda: False, run=run)
        self.assertEqual([p.name for p in self.folder.iterdir()], ["song.flp"])

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


class FakePianoRoll:
    """Plays FL's side of fl_bridge.notes. Each channel keeps its notes, and running the script applies the queue."""

    def __init__(self, folder, channels, pattern=1, script_runs=True, ppq=960):
        self.folder = folder
        self.channels = channels
        self.pattern = pattern
        self.script_runs = script_runs
        self.ppq = ppq
        self.open = None
        self.writes = 0

    def call(self, command, params=None, timeout=5.0):
        if command == "pattern_select":
            self.pattern = params["index"]
        if command == "project":
            return {"current_pattern": self.pattern, "ppq": self.ppq}
        return {}

    def focus(self, channel):
        self.open = channel

    def fingerprint(self):
        return str(sorted(notes._key(n, self.ppq) for n in self.channels[self.open]))

    def run_last_script(self):
        queue = client.read_json(self.folder / "pianoroll_queue.json")
        if not self.script_runs or not queue:
            return
        expect = queue.get("expect")
        if expect is not None and expect != self.fingerprint():
            answer = {"id": queue["id"], "ok": False, "error": "expected fingerprint " + expect}
        else:
            if queue["action"] == "clear":
                self.channels[self.open] = []
                self.writes += 1
            elif queue["action"] == "add_notes":
                # FL rounds times to the project's PPQ and keeps velocity in steps of 1/128.
                added = [
                    {
                        **n,
                        "start": round(n["start"] * self.ppq) / self.ppq,
                        "length": round(n["length"] * self.ppq) / self.ppq,
                        "velocity": round(round(n.get("velocity", 0.8) * 128) / 128, 3),
                    }
                    for n in queue["payload"]["notes"]
                ]
                self.channels[self.open] = self.channels[self.open] + added
                self.writes += 1
            result = {"notes": list(self.channels[self.open]), "fingerprint": self.fingerprint()}
            answer = {"id": queue["id"], "ok": True, "result": result}
        client.write_json(self.folder / "pianoroll_done.json", answer)
        client.write_json(self.folder / "pianoroll_queue.json", {})


class Notes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        patcher = mock.patch.dict(os.environ, {"FL_BRIDGE_PIANO_ROLL_DIR": str(self.folder)})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(client, "SETTLE_S", 0).start()
        mock.patch.object(notes, "RESULT_TIMEOUT_S", 0.05).start()

    def fake(self, channels, **options):
        fl = FakePianoRoll(self.folder, channels, **options)
        mock.patch.object(client, "call", fl.call).start()
        mock.patch.object(client, "focus_piano_roll", fl.focus).start()
        mock.patch.object(window, "run_last_script", fl.run_last_script).start()
        return fl

    def test_write_reads_the_notes_back(self):
        fl = self.fake({2: [], 3: []})
        want = {2: [NOTE], 3: [{"pitch": 48, "start": 1, "length": 2, "velocity": 0.62}]}
        report = notes.write(1, want)
        self.assertEqual(fl.channels[3][0]["velocity"], 0.617)
        self.assertEqual(report, ["2: 1 notes written and read back", "3: 1 notes written and read back"])

    def test_busy_channel_stops_the_write_before_anything_changes(self):
        fl = self.fake({2: [], 3: [{"pitch": 70, "start": 0, "length": 1}]})
        with self.assertRaisesRegex(client.BridgeError, r"channels \[3\]"):
            notes.write(1, {2: [NOTE], 3: [NOTE]})
        self.assertEqual(fl.writes, 0)
        self.assertEqual(fl.channels[2], [])

    def test_replace_clears_a_busy_channel(self):
        fl = self.fake({3: [{"pitch": 70, "start": 0, "length": 1}]})
        notes.write(1, {3: [NOTE]}, replace=True)
        self.assertEqual([n["pitch"] for n in fl.channels[3]], [60])

    def test_notes_already_there_are_left_alone(self):
        fl = self.fake({2: [NOTE]})
        self.assertEqual(notes.write(1, {2: [NOTE]}), ["2: already written, 1 notes"])
        self.assertEqual(fl.writes, 0)

    def test_velocity_counts_in_steps_of_1_128(self):
        self.assertTrue(notes.same([{**NOTE, "velocity": 0.617}], [{**NOTE, "velocity": 0.62}], 960))
        self.assertFalse(notes.same([{**NOTE, "velocity": 0.6}], [{**NOTE, "velocity": 0.62}], 960))

    def test_times_count_in_ticks_of_the_project(self):
        fl = self.fake({2: []}, ppq=96)
        report = notes.write(1, {2: [{"pitch": 38, "start": 0, "length": 3.9, "velocity": 0.62}]})
        self.assertAlmostEqual(fl.channels[2][0]["length"], 374 / 96)
        self.assertEqual(report, ["2: 1 notes written and read back"])

    def test_script_that_never_runs_leaves_the_queue_empty(self):
        self.fake({2: []}, script_runs=False)
        with self.assertRaisesRegex(client.BridgeError, "didn't run on channel 2"):
            notes.read(1, [2])
        self.assertFalse(client.read_json(self.folder / "pianoroll_queue.json"))

    def test_wrong_pattern_is_reported(self):
        fl = self.fake({2: []})
        fl.call = lambda command, params=None, timeout=5.0: {"current_pattern": 4} if command == "project" else {}
        mock.patch.object(client, "call", fl.call).start()
        with self.assertRaisesRegex(client.BridgeError, "pattern 4"):
            notes.read(1, [2])

    def test_bad_note_is_refused_before_fl_is_touched(self):
        fl = self.fake({2: []})
        with self.assertRaisesRegex(ValueError, "note 0"):
            notes.write(1, {2: [{"pitch": 60, "start": 0, "length": 1, "velocity": 2}]})
        self.assertIsNone(fl.open)


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
            self.server.fl_queue_notes([{"pitch": 200, "start": 0, "length": 1}], "abc")

    def test_short_pattern_clears_the_rest_of_the_row(self):
        with mock.patch.object(client, "call", return_value={}) as call:
            self.server.fl_channel_steps(0, "1010")
        steps = call.call_args.args[1]["steps"]
        self.assertEqual(len(steps), 64)
        self.assertEqual(steps[:5], [True, False, True, False, False])
        self.assertFalse(any(steps[4:]))

    def test_plugin_params_hides_placeholders_unless_asked(self):
        with mock.patch.object(client, "call", return_value={}) as call:
            self.server.fl_plugin_params(channel=3)
            self.assertTrue(call.call_args.args[1]["named_only"])
            self.server.fl_plugin_params(channel=3, named_only=False)
            self.assertFalse(call.call_args.args[1]["named_only"])

    def test_channel_rename_is_read_back(self):
        with (
            mock.patch.object(client, "call", return_value={"name": "Old", "muted": False, "track": 0}),
            mock.patch.object(client, "SETTLE_S", 0),
            self.assertRaisesRegex(client.BridgeError, "name='Old'"),
        ):
            self.server.fl_channel_set(0, name="New")

    def test_loaded_channel_waits_for_the_plugin_name(self):
        rows = iter([[{"plugin": "Fruity Wrapper"}], [{"plugin": "Fruity Wrapper"}], [{"plugin": "Ample Guitar SC"}]])
        with mock.patch.object(client, "call", side_effect=lambda *a, **k: next(rows)):
            row = self.server._loaded_channel(sleep=lambda _: None)
        self.assertEqual(row["plugin"], "Ample Guitar SC")

    def test_steps_are_checked_before_sending(self):
        with self.assertRaises(ValueError):
            self.server.fl_channel_steps(0, "10x")

    def test_effect_added_in_the_first_empty_slot(self):
        before = [{"slot": 0, "plugin": "Reverb"}, {"slot": 2, "plugin": "Delay"}]
        after = before + [{"slot": 1, "plugin": "Limiter"}]
        self.assertEqual(self.server.effect_added(before, after), {"slot": 1, "plugin": "Limiter"})

    def test_effect_that_replaced_another_is_refused(self):
        before = [{"slot": 0, "plugin": "Reverb"}]
        with self.assertRaisesRegex(client.BridgeError, r"slots \[0\] changed"):
            self.server.effect_added(before, [{"slot": 0, "plugin": "Limiter"}])

    def test_effect_in_an_unexpected_slot_is_refused(self):
        with self.assertRaisesRegex(client.BridgeError, "slot 0"):
            self.server.effect_added([], [{"slot": 3, "plugin": "Limiter"}])

    def add_effect(self, mixer, load, caption="Piano roll - Guitar", channels=None):
        """Run fl_mixer_add_effect against a fake FL whose mixer_list returns the rows in mixer."""

        def call(name, params=None, **kwargs):
            rows = [{"track": t, "effects": e} for t, e in mixer.items()]
            return {"channel_list": channels or [{"channel": 2, "track": 5}], "mixer_list": rows}[name]

        focus = {"selected": 2, "piano_roll_focused": True, "caption": caption}
        with (
            mock.patch.object(client, "call", side_effect=call),
            mock.patch.object(client, "focus_piano_roll", return_value=focus) as focused,
            mock.patch.object(client, "SETTLE_S", 0),
            mock.patch.object(self.server.window, "load_effect", side_effect=load),
            mock.patch.object(self.server.window, "close_plugin_forms", return_value=0),
        ):
            return self.server.fl_mixer_add_effect(10, 10, 5), focused

    def remove_effect(self, before, after, focused_id):
        snapshots = iter([before, after])

        def call(name, params=None, **kwargs):
            if name == "mixer_list":
                return [{"track": t, "effects": e} for t, e in next(snapshots).items()]
            return {"id": focused_id, "caption": "Reverb (Insert 5)"}

        delete = mock.Mock()
        with (
            mock.patch.object(client, "call", side_effect=call),
            mock.patch.object(client, "SETTLE_S", 0),
            mock.patch.object(self.server.window, "close_plugin_forms", return_value=0),
            mock.patch.object(self.server.window, "plugin_forms", return_value=["form"]),
            mock.patch.object(self.server.window, "delete_plugin_form", delete),
        ):
            return self.server.fl_mixer_remove_effect(5, 1), delete

    def test_remove_effect_deletes_the_checked_window(self):
        before = {5: [{"slot": 0, "plugin": "Reverb"}, {"slot": 1, "plugin": "Limiter"}]}
        after = {5: [{"slot": 0, "plugin": "Reverb"}]}
        result, delete = self.remove_effect(before, after, self.server.effect_form_id(5, 1))
        delete.assert_called_once_with("form")
        self.assertEqual(result, {"track": 5, "effects": [{"slot": 0, "plugin": "Reverb"}]})

    def test_remove_effect_refuses_another_window(self):
        before = {5: [{"slot": 1, "plugin": "Limiter"}]}
        with self.assertRaisesRegex(client.BridgeError, "Nothing deleted"):
            self.remove_effect(before, before, self.server.effect_form_id(5, 0))

    def test_remove_effect_reports_an_unexpected_result(self):
        before = {5: [{"slot": 1, "plugin": "Limiter"}], 3: [{"slot": 0, "plugin": "Delay"}]}
        with self.assertRaisesRegex(client.BridgeError, "expected only"):
            self.remove_effect(
                before,
                {3: [{"slot": 0, "plugin": "Delay"}], 5: [{"slot": 1, "plugin": "Limiter"}]},
                self.server.effect_form_id(5, 1),
            )

    def test_remove_effect_needs_an_effect_in_the_slot(self):
        with self.assertRaisesRegex(ValueError, "no effect in slot 1"):
            self.remove_effect({5: [{"slot": 0, "plugin": "Reverb"}]}, {}, 0)

    def test_add_effect_needs_a_channel_feeding_the_track(self):
        with self.assertRaisesRegex(ValueError, "no channel"):
            self.add_effect({}, None, channels=[{"channel": 0, "track": 1}])

    def test_add_effect_refuses_a_full_track(self):
        full = {5: [{"slot": s, "plugin": "X"} for s in range(10)]}
        with self.assertRaisesRegex(ValueError, "no empty"):
            self.add_effect(full, None)

    def test_add_effect_focuses_the_feeding_channel_and_checks_the_slot(self):
        def load(x, y, snapshot):
            return {5: [{"slot": 0, "plugin": "Limiter"}]}

        result, focused = self.add_effect({}, load)
        focused.assert_called_once_with(2)
        self.assertEqual(result, {"track": 5, "via_channel": 2, "slot": 0, "plugin": "Limiter"})

    def test_add_effect_reports_an_effect_replaced_on_another_track(self):
        # FL puts a browser effect into the focused plugin's slot when a plugin window has the focus
        before = {3: [{"slot": 0, "plugin": "Reverb"}, {"slot": 1, "plugin": "Limiter"}]}

        def load(x, y, snapshot):
            return {3: [{"slot": 0, "plugin": "Reverb"}, {"slot": 1, "plugin": "Delay"}]}

        with self.assertRaisesRegex(client.BridgeError, r"changed tracks \[3\]"):
            self.add_effect(before, load)

    def test_add_effect_reports_other_tracks_even_after_a_timeout(self):
        state = {3: [{"slot": 0, "plugin": "Reverb"}]}

        def load(x, y, snapshot):
            state[3] = [{"slot": 0, "plugin": "Delay"}]
            raise self.server.window.WindowError("FL didn't add the effect")

        with self.assertRaisesRegex(client.BridgeError, r"changed tracks \[3\]"):
            self.add_effect(state, load)

    def test_add_effect_sends_nothing_when_a_plugin_keeps_the_focus(self):
        load = mock.Mock()
        with self.assertRaisesRegex(client.BridgeError, "Nothing was sent"):
            self.add_effect({}, load, caption="Fruity Limiter (Insert 5)")
        load.assert_not_called()


if __name__ == "__main__":
    unittest.main()


def midi_bytes(tracks=1, declared=None, division=960):
    track = b"MTrk" + struct.pack(">I", 4) + b"\x00\xff\x2f\x00"
    header = b"MThd" + struct.pack(">IHHH", 6, 1, declared if declared is not None else tracks, division)
    return header + track * tracks


class MidiFile(unittest.TestCase):
    def write(self, data):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "song.mid"
        path.write_bytes(data)
        return path

    def test_reads_format_tracks_and_ppq(self):
        from fl_bridge import midifile

        self.assertEqual(midifile.check(self.write(midi_bytes(3))), {"format": 1, "tracks": 3, "ppq": 960})

    def test_refuses_what_fl_would_misread(self):
        from fl_bridge import midifile

        cases = {
            "isn't a standard MIDI file": b"RIFF" + bytes(20),
            "SMPTE": midi_bytes(division=0xE728),
            "declares 2 tracks and holds 1": midi_bytes(1, declared=2),
            "truncated": midi_bytes(1)[:-2],
        }
        for message, data in cases.items():
            with self.subTest(message), self.assertRaisesRegex(midifile.MidiFileError, message):
                midifile.check(self.write(data))
        with self.assertRaisesRegex(midifile.MidiFileError, "doesn't exist"):
            midifile.check(Path(tempfile.gettempdir()) / "no-such-file.mid")


class ImportMidi(unittest.TestCase):
    """The import tool's safeguards, with FL and its windows faked."""

    @classmethod
    def setUpClass(cls):
        try:
            from fl_bridge import server
        except ImportError:
            raise unittest.SkipTest("the server needs the mcp package") from None
        cls.server = server

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.midi = Path(tmp.name) / "song.mid"
        self.midi.write_bytes(midi_bytes(2))
        self.channels = [{"name": "Sampler", "plugin": None}]
        self.patterns = [{"index": 1, "name": "Pattern 1", "length": 16}]
        self.ppq_after = 960
        self.calls = []
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(client, "call", self.call).start()
        mock.patch.object(client, "settled", lambda command, params, check=None: self.call(command, params)).start()
        self.importer = mock.patch.object(window, "import_midi", side_effect=self.fake_import).start()
        self.imported = False

    def call(self, command, params=None, timeout=5.0):
        self.calls.append(command)
        if command == "project":
            ppq = self.ppq_after if self.imported else 960
            return {"ppq": ppq, "patterns": len(self.patterns), "current_pattern": len(self.patterns) + 1}
        if command == "channel_list":
            return self.channels
        if command == "pattern_list":
            return {"patterns": [dict(p) for p in self.patterns]}
        return {}

    def fake_import(self, path, options):
        self.imported = True
        self.options = options
        return dict(options)

    def test_an_empty_project_imports_into_the_next_pattern_with_every_option_set(self):
        result = self.server.fl_import_midi(str(self.midi))
        self.assertEqual(result["pattern"], 2)
        self.assertEqual(result["warnings"], [])
        self.assertEqual(set(self.options), set(window.MIDI_IMPORT_OPTIONS))
        self.assertFalse(self.options["start_new_project"])
        self.assertFalse(self.options["import_zero_velocity"])

    def test_a_bad_file_is_refused_before_anything_changes(self):
        self.midi.write_bytes(b"not midi")
        with self.assertRaises(ValueError):
            self.server.fl_import_midi(str(self.midi))
        self.assertEqual(self.calls, [])
        self.importer.assert_not_called()

    def test_a_project_with_data_is_refused_unless_allowed(self):
        cases = {
            "2 channels": ([{"name": "A", "plugin": None}, {"name": "B", "plugin": None}], self.patterns),
            "holds Kontakt": ([{"name": "Guitar", "plugin": "Kontakt 8"}], self.patterns),
            "hold data": (self.channels, [{"index": 1, "name": "Verse", "length": 64}]),
        }
        for message, (channels, patterns) in cases.items():
            with self.subTest(message):
                self.channels, self.patterns = channels, patterns
                with self.assertRaisesRegex(ValueError, message):
                    self.server.fl_import_midi(str(self.midi))
                self.importer.assert_not_called()
        self.server.fl_import_midi(str(self.midi), allow_existing_channels=True)
        self.importer.assert_called_once()

    def test_a_changed_pattern_is_reported(self):
        def change_pattern_1(path, options):
            self.patterns[0]["length"] = 32
            return self.fake_import(path, options)

        self.importer.side_effect = change_pattern_1
        result = self.server.fl_import_midi(str(self.midi))
        self.assertEqual(result["warnings"], ["pattern 1 (Pattern 1) changed during the import"])

    def test_a_changed_ppq_is_an_error(self):
        self.ppq_after = 96
        with self.assertRaisesRegex(client.BridgeError, "PPQ changed"):
            self.server.fl_import_midi(str(self.midi))
