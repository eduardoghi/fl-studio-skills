-- File bridge between REAPER and the mps library.
--
-- Each REAPER instance running this script makes its own folder, <resource path>/mps/instances/<id>/, holding
--   info.json   who the instance is (written once)
--   heartbeat   rewritten every second, and the client only reads its modification time
--   req/        requests the client published (renamed from tmp/ to a name that doesn't exist yet)
--   work/       the request the bridge claimed (renamed from req/, so only one claim can win)
--   res/        responses, published the same way as requests
--   tmp/        files still being written
-- A request left in work/ without a response started and never finished (REAPER crashed or hung), so the client
-- reports its outcome as uncertain. Nothing here runs Lua code sent in a request, only the commands in the
-- COMMANDS table.
--
-- An instance started only to render (environment variable MPS_ROLE=render) doesn't start the bridge.
-- An instance started with MPS_BRIDGE_FAULTS=1 lets envelope.set take an "_fault" argument that makes it fail on
-- purpose ("insert" in the middle of the change, "restore" also during the recovery), which the live tests use to
-- check the recovery. Without that variable the argument is ignored.

if os.getenv("MPS_ROLE") == "render" then return end

local VERSION = "0.2.9"
local FAULTS = os.getenv("MPS_BRIDGE_FAULTS") == "1"

-- launching the script again ends the running copy and starts the new one, instead of asking in a dialog
if reaper.set_action_options then reaper.set_action_options(1 | 2) end
local SEP = package.config:sub(1, 1)

---------------------------------------------------------------------------------------------------------------- JSON
local json = {}

local function esc(s)
  return s:gsub('[%c"\\]', function(c)
    local map = { ['"'] = '\\"', ['\\'] = '\\\\', ['\n'] = '\\n', ['\r'] = '\\r', ['\t'] = '\\t' }
    return map[c] or string.format("\\u%04x", c:byte())
  end)
end

local function finite(v) return type(v) == "number" and v == v and v ~= math.huge and v ~= -math.huge end

local function is_array(t)
  if next(t) == nil then return getmetatable(t) == json.array_mt end
  local n = 0
  for k in pairs(t) do
    if type(k) ~= "number" or k < 1 or k % 1 ~= 0 then return false end
    n = n + 1
  end
  return n == #t
end

json.array_mt = {}
function json.array(t) return setmetatable(t or {}, json.array_mt) end

function json.encode(v)
  local t = type(v)
  if v == nil or v == json.null then return "null"
  elseif t == "boolean" then return tostring(v)
  elseif t == "number" then
    if v ~= v or v == math.huge or v == -math.huge then return "null" end
    if math.type(v) == "integer" then return tostring(v) end
    return string.format("%.17g", v)
  elseif t == "string" then return '"' .. esc(v) .. '"'
  elseif t == "table" then
    local out = {}
    if is_array(v) then
      for i = 1, #v do out[i] = json.encode(v[i]) end
      return "[" .. table.concat(out, ",") .. "]"
    end
    for k, val in pairs(v) do out[#out + 1] = '"' .. esc(tostring(k)) .. '":' .. json.encode(val) end
    return "{" .. table.concat(out, ",") .. "}"
  end
  error("json: cannot encode " .. t)
end

json.null = setmetatable({}, { __tostring = function() return "null" end })

function json.decode(s)
  local i = 1
  local function ws() i = s:find("[^ \t\r\n]", i) or #s + 1 end
  local value
  local function str()
    local out, j = {}, i + 1
    while true do
      local c = s:sub(j, j)
      if c == "" then error("json: unterminated string") end
      if c == '"' then i = j + 1; return table.concat(out) end
      if c == "\\" then
        local n = s:sub(j + 1, j + 1)
        local map = { b = "\b", f = "\f", n = "\n", r = "\r", t = "\t", ['"'] = '"', ["\\"] = "\\", ["/"] = "/" }
        if n == "u" then
          local cp = tonumber(s:sub(j + 2, j + 5), 16)
          if cp >= 0xD800 and cp <= 0xDBFF and s:sub(j + 6, j + 7) == "\\u" then
            local lo = tonumber(s:sub(j + 8, j + 11), 16)
            cp = 0x10000 + (cp - 0xD800) * 0x400 + (lo - 0xDC00)
            j = j + 6
          end
          out[#out + 1] = utf8.char(cp)
          j = j + 6
        else
          out[#out + 1] = map[n] or error("json: bad escape")
          j = j + 2
        end
      else
        local k = s:find('["\\]', j) or #s + 1
        out[#out + 1] = s:sub(j, k - 1)
        j = k
      end
    end
  end
  function value()
    ws()
    local c = s:sub(i, i)
    if c == "{" then
      local obj = {}
      i = i + 1; ws()
      if s:sub(i, i) == "}" then i = i + 1; return obj end
      while true do
        ws()
        local k = str()
        ws(); if s:sub(i, i) ~= ":" then error("json: expected ':'") end
        i = i + 1
        obj[k] = value()
        ws()
        local d = s:sub(i, i); i = i + 1
        if d == "}" then return obj end
        if d ~= "," then error("json: expected ',' or '}'") end
      end
    elseif c == "[" then
      local arr = json.array({})
      i = i + 1; ws()
      if s:sub(i, i) == "]" then i = i + 1; return arr end
      while true do
        arr[#arr + 1] = value()
        ws()
        local d = s:sub(i, i); i = i + 1
        if d == "]" then return arr end
        if d ~= "," then error("json: expected ',' or ']'") end
      end
    elseif c == '"' then return str()
    elseif s:sub(i, i + 3) == "true" then i = i + 4; return true
    elseif s:sub(i, i + 4) == "false" then i = i + 5; return false
    elseif s:sub(i, i + 3) == "null" then i = i + 4; return json.null
    else
      local num = s:match("^-?%d+%.?%d*[eE]?[-+]?%d*", i)
      if not num or num == "" then error("json: unexpected character at " .. i) end
      i = i + #num
      return math.tointeger(tonumber(num)) or tonumber(num)
    end
  end
  local v = value()
  ws()
  if i <= #s then error("json: trailing data") end
  return v
end

--------------------------------------------------------------------------------------------------------------- files
local function read_file(path)
  local f = io.open(path, "rb")
  if not f then return nil end
  local data = f:read("a")
  f:close()
  return data
end

local function publish(dir, name, text, tmpdir)
  -- write in tmp/ and publish by renaming to a name that doesn't exist yet, on the same volume
  local tmp = tmpdir .. SEP .. name .. ".tmp"
  local f = assert(io.open(tmp, "wb"))
  f:write(text)
  f:close()
  local ok, err = os.rename(tmp, dir .. SEP .. name)
  if not ok then os.remove(tmp); error("publish failed: " .. tostring(err)) end
end

local function random_id()
  math.randomseed(math.floor(reaper.time_precise() * 1e6) % 2147483647 + os.time())
  local t = {}
  for k = 1, 16 do t[k] = string.format("%x", math.random(0, 15)) end
  return table.concat(t)
end

local ROOT = reaper.GetResourcePath() .. SEP .. "mps" .. SEP .. "instances"
local IID = random_id()
local DIR = ROOT .. SEP .. IID
local D = { req = DIR .. SEP .. "req", work = DIR .. SEP .. "work", res = DIR .. SEP .. "res", tmp = DIR .. SEP .. "tmp" }
for _, p in pairs({ ROOT, DIR, D.req, D.work, D.res, D.tmp }) do reaper.RecursiveCreateDirectory(p, 0) end

------------------------------------------------------------------------------------------------------------- helpers
local function project_path()
  local _, path = reaper.EnumProjects(-1)
  return path or ""
end

local function need(args, key, kind)
  local v = args[key]
  if v == nil or v == json.null then error("bad_args: missing '" .. key .. "'") end
  if kind and type(v) ~= kind then error("bad_args: '" .. key .. "' must be " .. kind) end
  return v
end

local function opt(args, key, kind)
  local v = args[key]
  if v == nil or v == json.null then return nil end
  if kind and type(v) ~= kind then error("bad_args: '" .. key .. "' must be " .. kind) end
  return v
end

local function track_by_guid(guid)
  for i = 0, reaper.CountTracks(0) - 1 do
    local tr = reaper.GetTrack(0, i)
    if reaper.GetTrackGUID(tr) == guid then return tr, i end
  end
  error("not_found: track " .. tostring(guid))
end

local function item_by_guid(guid)
  for i = 0, reaper.CountMediaItems(0) - 1 do
    local it = reaper.GetMediaItem(0, i)
    local _, g = reaper.GetSetMediaItemInfo_String(it, "GUID", "", false)
    if g == guid then return it end
  end
  error("not_found: item " .. tostring(guid))
end

local function fx_index(track, args)
  local fx = need(args, "fx")
  if type(fx) == "number" then
    if fx < 0 or fx >= reaper.TrackFX_GetCount(track) then error("not_found: fx index " .. fx) end
    return math.tointeger(fx)
  end
  for i = 0, reaper.TrackFX_GetCount(track) - 1 do
    if reaper.TrackFX_GetFXGUID(track, i) == fx then return i end
  end
  error("not_found: fx " .. tostring(fx))
end

local function fx_info(track, i)
  local _, name = reaper.TrackFX_GetFXName(track, i)
  local _, ident = reaper.TrackFX_GetNamedConfigParm(track, i, "fx_ident")
  local _, ftype = reaper.TrackFX_GetNamedConfigParm(track, i, "fx_type")
  return { index = i, guid = reaper.TrackFX_GetFXGUID(track, i), name = name, ident = ident, type = ftype,
           enabled = reaper.TrackFX_GetEnabled(track, i), offline = reaper.TrackFX_GetOffline(track, i),
           params = reaper.TrackFX_GetNumParams(track, i) }
end

local function track_info(tr, i)
  local _, name = reaper.GetTrackName(tr)
  local fx = json.array({})
  for k = 0, reaper.TrackFX_GetCount(tr) - 1 do fx[#fx + 1] = fx_info(tr, k) end
  local items = json.array({})
  for k = 0, reaper.CountTrackMediaItems(tr) - 1 do
    local it = reaper.GetTrackMediaItem(tr, k)
    local take = reaper.GetActiveTake(it)
    local _, g = reaper.GetSetMediaItemInfo_String(it, "GUID", "", false)
    items[#items + 1] = { guid = g, position = reaper.GetMediaItemInfo_Value(it, "D_POSITION"),
                          length = reaper.GetMediaItemInfo_Value(it, "D_LENGTH"),
                          midi = take ~= nil and reaper.TakeIsMIDI(take) or false }
  end
  local sends = json.array({})
  for k = 0, reaper.GetTrackNumSends(tr, 0) - 1 do
    local dest = reaper.GetTrackSendInfo_Value(tr, 0, k, "P_DESTTRACK")
    sends[#sends + 1] = { index = k, dest = dest and reaper.GetTrackGUID(dest) or json.null,
                          volume_db = 20 * math.log(math.max(reaper.GetTrackSendInfo_Value(tr, 0, k, "D_VOL"), 1e-10), 10),
                          mode = math.floor(reaper.GetTrackSendInfo_Value(tr, 0, k, "I_SENDMODE")),
                          src_channel = math.floor(reaper.GetTrackSendInfo_Value(tr, 0, k, "I_SRCCHAN")),
                          mute = reaper.GetTrackSendInfo_Value(tr, 0, k, "B_MUTE") == 1 }
  end
  local color = math.floor(reaper.GetMediaTrackInfo_Value(tr, "I_CUSTOMCOLOR"))
  local rgb = json.null
  if color & 0x1000000 ~= 0 then
    local r, g, b = reaper.ColorFromNative(color & 0xFFFFFF)
    rgb = json.array({ r, g, b })
  end
  return { index = i, guid = reaper.GetTrackGUID(tr), name = name, fx = fx, items = items,
           volume = reaper.GetMediaTrackInfo_Value(tr, "D_VOL"), pan = reaper.GetMediaTrackInfo_Value(tr, "D_PAN"),
           mute = reaper.GetMediaTrackInfo_Value(tr, "B_MUTE") == 1,
           folder_depth = math.floor(reaper.GetMediaTrackInfo_Value(tr, "I_FOLDERDEPTH")),
           main_send = reaper.GetMediaTrackInfo_Value(tr, "B_MAINSEND") == 1,
           channels = math.floor(reaper.GetMediaTrackInfo_Value(tr, "I_NCHAN")), color = rgb, sends = sends }
end

local function read_midi(take)
  local notes, ccs = json.array({}), json.array({})
  local _, nn, nc = reaper.MIDI_CountEvts(take)
  for k = 0, nn - 1 do
    local _, sel, mut, s, e, ch, p, v = reaper.MIDI_GetNote(take, k)
    notes[#notes + 1] = { start_ppq = s, end_ppq = e, start_qn = reaper.MIDI_GetProjQNFromPPQPos(take, s),
                          end_qn = reaper.MIDI_GetProjQNFromPPQPos(take, e), chan = ch, pitch = p, vel = v,
                          muted = mut }
  end
  for k = 0, nc - 1 do
    local _, sel, mut, pos, chanmsg, ch, m2, m3 = reaper.MIDI_GetCC(take, k)
    ccs[#ccs + 1] = { ppq = pos, qn = reaper.MIDI_GetProjQNFromPPQPos(take, pos), status = chanmsg, chan = ch,
                      msg2 = m2, msg3 = m3 }
  end
  return { notes = notes, ccs = ccs }
end

local RENDER_FORMATS = {
  -- WAV sink settings in base64 ("evaw" followed by the bit depth and options)
  wav16 = "ZXZhdxAAAQ==", wav24 = "ZXZhdxgAAQ==", wav32f = "ZXZhdyAAAQ==",
}
-- RENDER_SETTINGS flag (16<<16) that delays the render start by RENDER_DELAY seconds, for FX that load samples
local RENDER_DELAY_FLAG = 16 << 16
-- RENDER_NORMALIZE flag (4<<16) that disables all render postprocessing (normalize, limit, fades, trim, pad)
local RENDER_NO_POSTPROCESSING = 4 << 16

------------------------------------------------------------------------------------------------------------ commands
-- mutates = true wraps the command in an undo block
local COMMANDS = {}

COMMANDS.ping = { run = function()
  return { instance = IID, bridge = VERSION, reaper = reaper.GetAppVersion(), resource = reaper.GetResourcePath(),
           project = project_path(), tracks = reaper.CountTracks(0) }
end }

-- holds the main thread for a few seconds, to test timeouts and uncertain outcomes
COMMANDS["debug.sleep"] = { run = function(a)
  local s = need(a, "seconds", "number")
  if s < 0 or s > 10 then error("bad_args: seconds must be between 0 and 10") end
  local t = reaper.time_precise()
  while reaper.time_precise() - t < s do end
  return { slept = reaper.time_precise() - t }
end }

COMMANDS["project.new_tab"] = { run = function()
  reaper.Main_OnCommand(40859, 0) -- New project tab
  return { project = project_path(), tracks = reaper.CountTracks(0) }
end }

COMMANDS["project.open"] = { run = function(a)
  local path = need(a, "path", "string")
  if not reaper.file_exists(path) then error("not_found: " .. path) end
  reaper.Main_OnCommand(40859, 0) -- New project tab, so the tab in use is left alone
  reaper.Main_openProject("noprompt:" .. path)
  return { project = project_path(), tracks = reaper.CountTracks(0) }
end }

COMMANDS["project.save"] = { run = function(a)
  local path = a.path
  if path and path ~= json.null then
    reaper.RecursiveCreateDirectory(path:match("^(.*)[\\/]") or ".", 0)
    reaper.Main_SaveProjectEx(0, path, 8) -- option 8 makes the project take this file name
  else
    if project_path() == "" then error("bad_args: project has no file name, pass 'path'") end
    reaper.Main_SaveProject(0, false)
  end
  return { project = project_path(), dirty = reaper.IsProjectDirty(0) ~= 0 }
end }

COMMANDS["project.close_tab"] = { run = function(a)
  -- closes every tab holding this project file, and refuses if one has unsaved changes
  local want = need(a, "path", "string"):lower()
  local current = reaper.EnumProjects(-1)
  local closed, k = 0, 0
  while true do
    local proj, path = reaper.EnumProjects(k)
    if not proj then break end
    if path:lower() == want then
      if reaper.IsProjectDirty(proj) ~= 0 then error("refused: " .. path .. " has unsaved changes") end
      reaper.SelectProjectInstance(proj)
      reaper.Main_OnCommand(40860, 0) -- Close current project tab
      closed = closed + 1
      if proj == current then current = nil end
    else
      k = k + 1
    end
  end
  if current then reaper.SelectProjectInstance(current) end
  return { closed = closed, project = project_path() }
end }

COMMANDS["project.info"] = { run = function()
  local tracks = json.array({})
  for i = 0, reaper.CountTracks(0) - 1 do tracks[#tracks + 1] = track_info(reaper.GetTrack(0, i), i) end
  local bpm, bpi = reaper.GetProjectTimeSignature2(0)
  local markers = json.array({})
  local k = 0
  while true do
    local n, isrgn, pos, rgnend, name, idx = reaper.EnumProjectMarkers3(0, k)
    if n == 0 then break end
    markers[#markers + 1] = { index = idx, region = isrgn, position = pos, ["end"] = isrgn and rgnend or json.null,
                              name = name }
    k = k + 1
  end
  return { project = project_path(), dirty = reaper.IsProjectDirty(0) ~= 0, bpm = bpm, beats_per_measure = bpi,
           srate = reaper.GetSetProjectInfo(0, "PROJECT_SRATE", 0, false), tracks = tracks, markers = markers }
end }

COMMANDS["project.set_tempo"] = { mutates = true, run = function(a)
  local bpm = need(a, "bpm", "number")
  reaper.SetCurrentBPM(0, bpm, false)
  local srate = a.srate
  if srate and srate ~= json.null then
    reaper.GetSetProjectInfo(0, "PROJECT_SRATE", srate, true)
    reaper.GetSetProjectInfo(0, "PROJECT_SRATE_USE", 1, true)
  end
  local got = reaper.GetProjectTimeSignature2(0)
  return { bpm = got, srate = reaper.GetSetProjectInfo(0, "PROJECT_SRATE", 0, false) }
end }

COMMANDS["track.add"] = { mutates = true, run = function(a)
  local idx = a.index
  if idx == nil or idx == json.null then idx = reaper.CountTracks(0) end
  reaper.InsertTrackAtIndex(idx, true)
  local tr = reaper.GetTrack(0, idx)
  if a.name and a.name ~= json.null then reaper.GetSetMediaTrackInfo_String(tr, "P_NAME", a.name, true) end
  return track_info(tr, idx)
end }

-- level, pan, mute and name of an existing track, each optional, read back from REAPER
COMMANDS["track.set"] = { mutates = true, run = function(a)
  local tr = track_by_guid(need(a, "track", "string"))
  if a.volume_db ~= nil and a.volume_db ~= json.null then
    if type(a.volume_db) ~= "number" then error("bad_request: volume_db must be a number") end
    reaper.SetMediaTrackInfo_Value(tr, "D_VOL", 10 ^ (a.volume_db / 20))
  end
  if a.pan ~= nil and a.pan ~= json.null then
    if type(a.pan) ~= "number" or a.pan < -1 or a.pan > 1 then error("bad_request: pan must be from -1 to 1") end
    reaper.SetMediaTrackInfo_Value(tr, "D_PAN", a.pan)
  end
  if a.mute ~= nil and a.mute ~= json.null then reaper.SetMediaTrackInfo_Value(tr, "B_MUTE", a.mute and 1 or 0) end
  if a.name and a.name ~= json.null then reaper.GetSetMediaTrackInfo_String(tr, "P_NAME", a.name, true) end
  -- folder_depth is REAPER's I_FOLDERDEPTH (1 opens a folder at this track, 0 is a plain track, -n closes n levels)
  if a.folder_depth ~= nil and a.folder_depth ~= json.null then
    local d = a.folder_depth
    if type(d) ~= "number" or d ~= math.floor(d) or d > 1 or d < -16 then
      error("bad_request: folder_depth must be an integer from -16 to 1")
    end
    reaper.SetMediaTrackInfo_Value(tr, "I_FOLDERDEPTH", d)
  end
  if a.main_send ~= nil and a.main_send ~= json.null then
    reaper.SetMediaTrackInfo_Value(tr, "B_MAINSEND", a.main_send and 1 or 0)
  end
  if a.channels ~= nil and a.channels ~= json.null then
    local c = a.channels
    if type(c) ~= "number" or c ~= math.floor(c) or c < 2 or c > 128 or c % 2 ~= 0 then
      error("bad_request: channels must be an even integer from 2 to 128")
    end
    reaper.SetMediaTrackInfo_Value(tr, "I_NCHAN", c)
  end
  if a.color == false then
    reaper.SetMediaTrackInfo_Value(tr, "I_CUSTOMCOLOR", 0)
  elseif a.color ~= nil and a.color ~= json.null then
    local c = a.color
    if type(c) ~= "table" or #c ~= 3 then error("bad_request: color must be [r, g, b] or false") end
    for _, v in ipairs(c) do
      if type(v) ~= "number" or v ~= math.floor(v) or v < 0 or v > 255 then
        error("bad_request: color components must be integers from 0 to 255")
      end
    end
    reaper.SetMediaTrackInfo_Value(tr, "I_CUSTOMCOLOR", reaper.ColorToNative(c[1], c[2], c[3]) | 0x1000000)
  end
  local idx = math.floor(reaper.GetMediaTrackInfo_Value(tr, "IP_TRACKNUMBER")) - 1
  local info = track_info(tr, idx)
  info.volume_db = 20 * math.log(math.max(reaper.GetMediaTrackInfo_Value(tr, "D_VOL"), 1e-10), 10)
  return info
end }

-- moves a track so it sits at `index` (0-based, counted before the move), keeping the selection as it was
COMMANDS["track.move"] = { mutates = true, run = function(a)
  local tr = track_by_guid(need(a, "track", "string"))
  local idx = need(a, "index", "number")
  if idx ~= math.floor(idx) or idx < 0 or idx > reaper.CountTracks(0) then
    error("bad_args: index must be an integer from 0 to the number of tracks")
  end
  local saved = {}
  for i = 0, reaper.CountSelectedTracks(0) - 1 do saved[#saved + 1] = reaper.GetSelectedTrack(0, i) end
  reaper.SetOnlyTrackSelected(tr)
  local ok = reaper.ReorderSelectedTracks(idx, 0)
  for i = 0, reaper.CountTracks(0) - 1 do reaper.SetTrackSelected(reaper.GetTrack(0, i), false) end
  for _, t in ipairs(saved) do reaper.SetTrackSelected(t, true) end
  if not ok then error("failed: ReorderSelectedTracks") end
  local now = math.floor(reaper.GetMediaTrackInfo_Value(tr, "IP_TRACKNUMBER")) - 1
  return track_info(tr, now)
end }

local SEND_MODES = { post_fader = 0, pre_fx = 1, post_fx = 3 }

-- a send from one track to another, with its level and where it taps the source (post_fader, pre_fx or post_fx)
COMMANDS["send.add"] = { mutates = true, run = function(a)
  local src = track_by_guid(need(a, "track", "string"))
  local dst = track_by_guid(need(a, "dest", "string"))
  if src == dst then error("bad_args: a track can't send to itself") end
  local mode = SEND_MODES[opt(a, "mode", "string") or "post_fader"]
  if not mode then error("bad_args: mode must be post_fader, pre_fx or post_fx") end
  local vol = opt(a, "volume_db", "number") or 0
  if not finite(vol) or vol < -150 or vol > 12 then error("bad_args: volume_db must be -150 to +12") end
  -- the first of the stereo pair of source channels to send, 0 for channels 1/2, 2 for 3/4 and so on, for the
  -- separate outputs of a multi-output instrument
  local srcch = opt(a, "src_channel", "number") or 0
  if srcch ~= math.floor(srcch) or srcch < 0 or srcch > 126 or srcch % 2 ~= 0 then
    error("bad_args: src_channel must be an even integer from 0 to 126")
  end
  local k = reaper.CreateTrackSend(src, dst)
  if k < 0 then error("failed: CreateTrackSend") end
  if not (reaper.SetTrackSendInfo_Value(src, 0, k, "D_VOL", 10 ^ (vol / 20))
          and reaper.SetTrackSendInfo_Value(src, 0, k, "I_SENDMODE", mode)
          and reaper.SetTrackSendInfo_Value(src, 0, k, "I_SRCCHAN", srcch)) then
    reaper.RemoveTrackSend(src, 0, k)
    error("failed: could not set the send, so it was removed")
  end
  local idx = math.floor(reaper.GetMediaTrackInfo_Value(src, "IP_TRACKNUMBER")) - 1
  return track_info(src, idx).sends[k + 1]
end }

-- a project marker, or a region when `end` is given, with an optional [r, g, b] color
COMMANDS["marker.add"] = { mutates = true, run = function(a)
  local name = need(a, "name", "string")
  local pos = need(a, "position", "number")
  local stop = opt(a, "end", "number")
  if not finite(pos) or pos < 0 or (stop and (not finite(stop) or stop <= pos)) then
    error("bad_args: position must be 0 or more, and end later than position")
  end
  local color = 0
  if a.color ~= nil and a.color ~= json.null then
    local c = a.color
    if type(c) ~= "table" or #c ~= 3 then error("bad_args: color must be [r, g, b]") end
    color = reaper.ColorToNative(c[1], c[2], c[3]) | 0x1000000
  end
  local k = reaper.AddProjectMarker2(0, stop ~= nil, pos, stop or 0, name, -1, color)
  if k < 0 then error("failed: AddProjectMarker2") end
  return { index = k, region = stop ~= nil, position = pos, ["end"] = stop or json.null, name = name }
end }

COMMANDS["item.add_midi"] = { mutates = true, run = function(a)
  local tr = track_by_guid(need(a, "track", "string"))
  local it = reaper.CreateNewMIDIItemInProj(tr, need(a, "start_qn", "number"), need(a, "end_qn", "number"), true)
  if not it then error("failed: CreateNewMIDIItemInProj") end
  local _, g = reaper.GetSetMediaItemInfo_String(it, "GUID", "", false)
  return { guid = g, position = reaper.GetMediaItemInfo_Value(it, "D_POSITION"),
           length = reaper.GetMediaItemInfo_Value(it, "D_LENGTH") }
end }

-- an audio file as an item, for re-amping a rendered DI through effect chains
COMMANDS["item.add_audio"] = { mutates = true, run = function(a)
  local tr = track_by_guid(need(a, "track", "string"))
  local path = need(a, "path", "string")
  if not reaper.file_exists(path) then error("not_found: " .. path) end
  local src = reaper.PCM_Source_CreateFromFile(path)
  if not src then error("failed: PCM_Source_CreateFromFile") end
  local len = reaper.GetMediaSourceLength(src)
  local it = reaper.AddMediaItemToTrack(tr)
  local take = reaper.AddTakeToMediaItem(it)
  reaper.SetMediaItemTake_Source(take, src)
  reaper.SetMediaItemInfo_Value(it, "D_POSITION", need(a, "position", "number"))
  reaper.SetMediaItemInfo_Value(it, "D_LENGTH", len)
  reaper.UpdateItemInProject(it)
  local _, g = reaper.GetSetMediaItemInfo_String(it, "GUID", "", false)
  return { guid = g, position = reaper.GetMediaItemInfo_Value(it, "D_POSITION"), length = len }
end }

COMMANDS["midi.write"] = { mutates = true, run = function(a)
  local take = reaper.GetActiveTake(item_by_guid(need(a, "item", "string")))
  if not take or not reaper.TakeIsMIDI(take) then error("bad_args: item has no MIDI take") end
  if a.replace then
    local _, nn, nc = reaper.MIDI_CountEvts(take)
    for k = nn - 1, 0, -1 do reaper.MIDI_DeleteNote(take, k) end
    for k = nc - 1, 0, -1 do reaper.MIDI_DeleteCC(take, k) end
  end
  for _, n in ipairs(a.notes or {}) do
    -- MIDI_InsertNote truncates fractional ticks (0.88 QN at 960 PPQ became 844, not 845), so round here
    local s = math.floor(reaper.MIDI_GetPPQPosFromProjQN(take, n.start_qn) + 0.5)
    local e = math.floor(reaper.MIDI_GetPPQPosFromProjQN(take, n.end_qn) + 0.5)
    if not reaper.MIDI_InsertNote(take, false, false, s, e, n.chan or 0, n.pitch, n.vel, true) then
      error("failed: MIDI_InsertNote")
    end
  end
  for _, c in ipairs(a.ccs or {}) do
    local pos = math.floor(reaper.MIDI_GetPPQPosFromProjQN(take, c.qn) + 0.5)
    -- status 0xB0 is a controller, 0xE0 pitch bend (msg2 low 7 bits, msg3 high 7 bits), 0xC0 program change
    if not reaper.MIDI_InsertCC(take, false, false, pos, c.status or 0xB0, c.chan or 0, c.msg2, c.msg3 or 0) then
      error("failed: MIDI_InsertCC")
    end
  end
  reaper.MIDI_Sort(take)
  return read_midi(take)
end }

COMMANDS["midi.read"] = { run = function(a)
  local take = reaper.GetActiveTake(item_by_guid(need(a, "item", "string")))
  if not take or not reaper.TakeIsMIDI(take) then error("bad_args: item has no MIDI take") end
  return read_midi(take)
end }

COMMANDS["fx.add"] = { mutates = true, run = function(a)
  local tr = track_by_guid(need(a, "track", "string"))
  local pos = a.position
  local inst = -1
  if pos and pos ~= json.null then inst = -1000 - pos end
  local idx = reaper.TrackFX_AddByName(tr, need(a, "name", "string"), false, inst)
  if idx < 0 then error("not_found: plugin " .. a.name) end
  return fx_info(tr, idx)
end }

COMMANDS["fx.delete"] = { mutates = true, run = function(a)
  local tr = track_by_guid(need(a, "track", "string"))
  local i = fx_index(tr, a)
  if not reaper.TrackFX_Delete(tr, i) then error("failed: TrackFX_Delete") end
  return { remaining = reaper.TrackFX_GetCount(tr) }
end }

COMMANDS["fx.params"] = { run = function(a)
  local tr = track_by_guid(need(a, "track", "string"))
  local i = fx_index(tr, a)
  local needle = (a.contains and a.contains ~= json.null) and a.contains:lower() or nil
  local out = json.array({})
  for p = 0, reaper.TrackFX_GetNumParams(tr, i) - 1 do
    local _, name = reaper.TrackFX_GetParamName(tr, i, p)
    if not needle or name:lower():find(needle, 1, true) then
      local _, fmt = reaper.TrackFX_GetFormattedParamValue(tr, i, p)
      local _, ident = reaper.TrackFX_GetParamIdent(tr, i, p)
      out[#out + 1] = { index = p, name = name, value = reaper.TrackFX_GetParamNormalized(tr, i, p),
                        text = fmt, ident = ident }
    end
  end
  return { fx = fx_info(tr, i), params = out }
end }

COMMANDS["fx.set_param"] = { mutates = true, run = function(a)
  local tr = track_by_guid(need(a, "track", "string"))
  local i = fx_index(tr, a)
  local p = need(a, "param", "number")
  local before = reaper.TrackFX_GetParamNormalized(tr, i, p)
  if not reaper.TrackFX_SetParamNormalized(tr, i, p, need(a, "value", "number")) then error("failed: set param") end
  local _, fmt = reaper.TrackFX_GetFormattedParamValue(tr, i, p)
  return { before = before, value = reaper.TrackFX_GetParamNormalized(tr, i, p), text = fmt }
end }

-- points of a track's volume envelope (values in dB) or of an effect parameter's envelope (normalized values),
-- replacing the points already there, read back after sorting

COMMANDS["envelope.set"] = { mutates = true, run = function(a)
  -- everything is checked before the first change, so a bad request leaves the envelope as it was
  local tr = track_by_guid(need(a, "track", "string"))
  local points = need(a, "points", "table")
  -- an object such as {"time": 1, "value": 0} is a table too, but has nothing for ipairs to check, so it would pass
  -- as an empty list. An empty list is refused as well, since this command replaces points and does not clear them.
  if not is_array(points) then error("bad_args: 'points' must be an array of point objects") end
  if #points == 0 then error("bad_args: 'points' is empty; envelope.set replaces points and does not clear envelopes") end
  local volume = a.fx == nil or a.fx == json.null
  -- a track's volume envelope comes in two places, after the effects ("volume") or before them ("volume_prefx")
  local target = opt(a, "target", "string") or "volume"
  local ENVS = { volume = { "Volume", 40406 }, volume_prefx = { "Volume (Pre-FX)", 40408 } }
  if not ENVS[target] then error("bad_args: target must be volume or volume_prefx") end
  if not volume and target ~= "volume" then error("bad_args: target applies to track volume, not to an effect") end
  local envname, show_action = ENVS[target][1], ENVS[target][2]
  local fxi, param
  if not volume then
    fxi = fx_index(tr, a)
    param = need(a, "param", "number")
    if param ~= math.floor(param) or param < 0 or param >= reaper.TrackFX_GetNumParams(tr, fxi) then
      error("bad_args: 'param' is not a parameter of this effect")
    end
  end
  for k, p in ipairs(points) do
    if type(p) ~= "table" then error("bad_args: point " .. k .. " is not an object") end
    if not finite(p.time) or p.time < 0 then error("bad_args: point " .. k .. " needs a finite time of 0 or more") end
    if not finite(p.value) then error("bad_args: point " .. k .. " needs a finite value") end
    if volume and (p.value < -150 or p.value > 6) then error("bad_args: point " .. k .. " volume must be -150 to +6 dB") end
    if not volume and (p.value < 0 or p.value > 1) then error("bad_args: point " .. k .. " value must be normalized, 0 to 1") end
    if p.shape ~= nil and p.shape ~= json.null and (type(p.shape) ~= "number" or p.shape ~= math.floor(p.shape)
        or p.shape < 0 or p.shape > 5) then
      error("bad_args: point " .. k .. " shape must be an integer from 0 to 5")
    end
  end
  local env
  if volume then env = reaper.GetTrackEnvelopeByName(tr, envname) else env = reaper.GetFXEnvelope(tr, fxi, param, false) end
  if env and reaper.CountAutomationItems(env) > 0 then
    error("refused: the envelope has automation items, which these points would not replace")
  end
  local created = env == nil
  if not volume then
    env = env or reaper.GetFXEnvelope(tr, fxi, param, true)
  else
    if not env then
      -- the API has no call that creates it, so show it with the native action on this track alone
      local saved = {}
      for i = 0, reaper.CountSelectedTracks(0) - 1 do saved[#saved + 1] = reaper.GetSelectedTrack(0, i) end
      reaper.SetOnlyTrackSelected(tr)
      reaper.Main_OnCommand(show_action, 0) -- Track: Toggle track (pre-FX) volume envelope visible
      for i = 0, reaper.CountTracks(0) - 1 do reaper.SetTrackSelected(reaper.GetTrack(0, i), false) end
      for _, t in ipairs(saved) do reaper.SetTrackSelected(t, true) end
      env = reaper.GetTrackEnvelopeByName(tr, envname)
    end
  end
  if not env then error("failed: no envelope") end
  local mode = reaper.GetEnvelopeScalingMode(env)
  local function scaled(p)
    if volume then return reaper.ScaleToEnvelopeMode(mode, 10 ^ (p.value / 20)) end
    return p.value
  end
  local function snapshot()
    local s = {}
    for i = 0, reaper.CountEnvelopePoints(env) - 1 do
      local _, t, v, shape, tension, selected = reaper.GetEnvelopePoint(env, i)
      s[#s + 1] = { t, v, shape, tension, selected }
    end
    return s
  end
  local saved = snapshot()
  local chunk_ok, chunk = reaper.GetEnvelopeStateChunk(env, "", false)
  if not chunk_ok then error("failed: could not read the envelope state before changing it") end
  local fault = FAULTS and a._fault or nil -- failure injection for the live tests, see the top of this file
  local function clear()
    if not reaper.DeleteEnvelopePointRange(env, -1, 1e9) then error("failed: DeleteEnvelopePointRange") end
    for i = reaper.CountEnvelopePoints(env) - 1, 0, -1 do
      if not reaper.DeleteEnvelopePointEx(env, -1, i) then error("failed: DeleteEnvelopePointEx") end
    end
  end
  local function replace()
    clear()
    -- a new envelope can keep a default point at time 0 (an effect parameter's at 1, its maximum), which would ramp
    -- into the first point given, so whatever is left takes the first value asked for
    if #points > 0 then
      for i = 0, reaper.CountEnvelopePoints(env) - 1 do
        local _, t = reaper.GetEnvelopePoint(env, i)
        if not reaper.SetEnvelopePoint(env, i, t, scaled(points[1]), 0, 0, false, true) then
          error("failed: SetEnvelopePoint")
        end
      end
    end
    for k, p in ipairs(points) do
      if fault and k == 2 then error("failed: injected fault after the first point") end
      local shape = (p.shape == nil or p.shape == json.null) and 0 or p.shape
      if not reaper.InsertEnvelopePoint(env, p.time, scaled(p), shape, 0, false, true) then
        error("failed: InsertEnvelopePoint")
      end
    end
    if not reaper.Envelope_SortPoints(env) then error("failed: Envelope_SortPoints") end
  end
  local ok, err = pcall(replace)
  if not ok then
    -- Put back the envelope state read before the change, then check the points against the snapshot. The error
    -- says whether that worked, since a failed recovery must not be reported as a restored envelope.
    local function same()
      local now = snapshot()
      if #now ~= #saved then return false end
      for i, s in ipairs(saved) do
        if math.abs(now[i][1] - s[1]) > 1e-9 or math.abs(now[i][2] - s[2]) > 1e-9 or now[i][3] ~= s[3] then
          return false
        end
      end
      return true
    end
    local restored = fault ~= "restore" and reaper.SetEnvelopeStateChunk(env, chunk, false) and same()
    if not restored and fault ~= "restore" then
      -- second attempt, point by point
      restored = pcall(function()
        clear()
        for _, s in ipairs(saved) do
          if not reaper.InsertEnvelopePoint(env, s[1], s[2], s[3], s[4], s[5], true) then error("insert") end
        end
        if not reaper.Envelope_SortPoints(env) then error("sort") end
      end) and same()
    end
    local note
    if not restored then
      note = "recovery failed, so the envelope may be left partly changed"
    elseif created then
      -- the points are back, but the envelope did not exist before this request. A new effect envelope starts at
      -- the parameter's maximum, so leave it inactive and hidden rather than driving the parameter.
      local off = chunk:gsub("\nACT 1", "\nACT 0"):gsub("\nVIS 1", "\nVIS 0")
      if reaper.SetEnvelopeStateChunk(env, off, false) then
        note = "the envelope did not exist before this request; it was created and left inactive and hidden"
      else
        note = "the envelope did not exist before this request; it was created and could not be deactivated"
      end
    else
      note = "the previous points were restored"
    end
    error(err .. " (" .. note .. ")", 0)
  end
  local back = json.array({})
  for i = 0, reaper.CountEnvelopePoints(env) - 1 do
    local _, t, v, shape = reaper.GetEnvelopePoint(env, i)
    if volume then v = 20 * math.log(math.max(reaper.ScaleFromEnvelopeMode(mode, v), 1e-10), 10) end
    back[#back + 1] = { time = t, value = v, shape = shape }
  end
  return { points = back }
end }

COMMANDS["fx.show"] = { run = function(a)
  local tr = track_by_guid(need(a, "track", "string"))
  reaper.TrackFX_Show(tr, fx_index(tr, a), a.show == false and 2 or 3) -- 3 shows the floating window, 2 hides it
  return {}
end }

COMMANDS["fx.state_get"] = { run = function(a)
  local tr = track_by_guid(need(a, "track", "string"))
  local i = fx_index(tr, a)
  local ok, chunk = reaper.TrackFX_GetNamedConfigParm(tr, i, "vst_chunk")
  if not ok then error("failed: plugin gives no vst_chunk") end
  return { fx = fx_info(tr, i), chunk = chunk, length = #chunk }
end }

COMMANDS["fx.state_set"] = { mutates = true, run = function(a)
  local tr = track_by_guid(need(a, "track", "string"))
  local i = fx_index(tr, a)
  local chunk = need(a, "chunk", "string")
  if not reaper.TrackFX_SetNamedConfigParm(tr, i, "vst_chunk", chunk) then error("failed: set vst_chunk") end
  local _, back = reaper.TrackFX_GetNamedConfigParm(tr, i, "vst_chunk")
  return { fx = fx_info(tr, i), length = #back, identical = back == chunk }
end }

-- Writes a saved state into a new instance of the same plugin, for plugins that ignore a state written into the
-- running instance (Kontakt, see skills/plugins). The new instance is added right after the old one and checked
-- before the old one is deleted, so a failure leaves the track as it was.
COMMANDS["fx.restore_fresh"] = { mutates = true, run = function(a)
  local tr = track_by_guid(need(a, "track", "string"))
  local i = fx_index(tr, a)
  local chunk = need(a, "chunk", "string")
  local old = fx_info(tr, i)
  local j = reaper.TrackFX_AddByName(tr, need(a, "name", "string"), false, -1000 - (i + 1))
  if j < 0 then error("not_found: plugin " .. a.name) end
  local new = fx_info(tr, j)
  if new.ident ~= old.ident then
    reaper.TrackFX_Delete(tr, j)
    error("refused: '" .. a.name .. "' added " .. tostring(new.ident) .. ", not the binary of the effect being replaced")
  end
  if not reaper.TrackFX_SetNamedConfigParm(tr, j, "vst_chunk", chunk) then
    reaper.TrackFX_Delete(tr, j)
    error("failed: set vst_chunk on the new instance")
  end
  local _, back = reaper.TrackFX_GetNamedConfigParm(tr, j, "vst_chunk")
  reaper.TrackFX_SetEnabled(tr, j, old.enabled)
  reaper.TrackFX_Delete(tr, i)
  return { replaced = old.guid, fx = fx_info(tr, i), length = #back, identical = back == chunk }
end }

COMMANDS["render.configure"] = { mutates = true, run = function(a)
  local fmt = RENDER_FORMATS[need(a, "format", "string")] or error("bad_args: format must be wav16, wav24 or wav32f")
  reaper.GetSetProjectInfo_String(0, "RENDER_FILE", need(a, "directory", "string"), true)
  reaper.GetSetProjectInfo_String(0, "RENDER_PATTERN", need(a, "pattern", "string"), true)
  reaper.GetSetProjectInfo_String(0, "RENDER_FORMAT", fmt, true)
  local tail_ms = opt(a, "tail_ms", "number") or 0
  local fx_delay = opt(a, "fx_delay", "number") or 0
  if tail_ms < 0 or fx_delay < 0 then error("bad_args: tail_ms and fx_delay can't be negative") end
  -- master mix only, plus the documented flag that waits fx_delay seconds for FX to load samples
  reaper.GetSetProjectInfo(0, "RENDER_SETTINGS", fx_delay > 0 and RENDER_DELAY_FLAG or 0, true)
  reaper.GetSetProjectInfo(0, "RENDER_DELAY", fx_delay, true)
  reaper.GetSetProjectInfo(0, "RENDER_BOUNDSFLAG", 0, true)      -- custom start and end
  reaper.GetSetProjectInfo(0, "RENDER_STARTPOS", need(a, "start", "number"), true)
  reaper.GetSetProjectInfo(0, "RENDER_ENDPOS", need(a, "end", "number"), true)
  reaper.GetSetProjectInfo(0, "RENDER_SRATE", need(a, "srate", "number"), true)
  reaper.GetSetProjectInfo(0, "RENDER_CHANNELS", need(a, "channels", "number"), true)
  -- the tail runs past `end` only when asked, so a render's length is always end - start + tail_ms
  reaper.GetSetProjectInfo(0, "RENDER_TAILFLAG", tail_ms > 0 and 1 or 0, true)
  reaper.GetSetProjectInfo(0, "RENDER_TAILMS", tail_ms, true)
  reaper.GetSetProjectInfo(0, "RENDER_ADDTOPROJ", 0, true)
  reaper.GetSetProjectInfo(0, "RENDER_DITHER", 0, true)
  reaper.GetSetProjectInfo(0, "RENDER_NORMALIZE", RENDER_NO_POSTPROCESSING, true)
  local _, targets = reaper.GetSetProjectInfo_String(0, "RENDER_TARGETS", "", false)
  local _, f = reaper.GetSetProjectInfo_String(0, "RENDER_FORMAT", "", false)
  local function get(key) return reaper.GetSetProjectInfo(0, key, 0, false) end
  return { targets = targets, format = f, start = get("RENDER_STARTPOS"), ["end"] = get("RENDER_ENDPOS"),
           srate = get("RENDER_SRATE"), channels = get("RENDER_CHANNELS"), settings = get("RENDER_SETTINGS"),
           fx_delay = get("RENDER_DELAY"), tail_flag = get("RENDER_TAILFLAG"), tail_ms = get("RENDER_TAILMS"),
           dither = get("RENDER_DITHER"), normalize = get("RENDER_NORMALIZE"),
           project_srate = get("PROJECT_SRATE"), project_srate_use = get("PROJECT_SRATE_USE") }
end }

---------------------------------------------------------------------------------------------------------------- loop
local function respond(id, body)
  body.id = id
  body.instance = IID
  body.finished = os.time()
  -- a result the encoder can't take still gets an answer, instead of an error that would stop the bridge
  local ok, text = pcall(json.encode, body)
  if not ok then
    text = json.encode({ id = id, instance = IID, finished = body.finished, status = "error",
                         error = "bad_response: " .. tostring(text), changed = body.changed })
  end
  publish(D.res, id .. ".json", text, D.tmp)
end

local function handle(name)
  local id = name:match("^(.+)%.json$")
  if not id then return end
  -- claim it. A failed rename means something else took the request, or the client withdrew it
  if not os.rename(D.req .. SEP .. name, D.work .. SEP .. name) then return end
  local raw = read_file(D.work .. SEP .. name)
  -- another process (an antivirus scanning the new file, it seems) sometimes held a just-claimed request for a moment,
  -- and the failed open was answered as an empty, malformed request, so the open is retried for up to a second
  local tries = 0
  while raw == nil and tries < 50 do
    local t = os.clock()
    while os.clock() - t < 0.02 do end
    raw = read_file(D.work .. SEP .. name)
    tries = tries + 1
  end
  local okp, req = pcall(json.decode, raw or "")
  local args = okp and type(req) == "table" and req.args
  if not okp or type(req) ~= "table" or getmetatable(req) == json.array_mt
     or (args ~= nil and (type(args) ~= "table" or getmetatable(args) == json.array_mt)) then
    local why = okp and "the request and its args must be JSON objects" or tostring(req):gsub("^.-%.lua:%d+: ", "")
    respond(id, { status = "error", error = "bad_request: " .. why })
    os.remove(D.work .. SEP .. name)
    return
  end
  if req.expires and req.expires ~= json.null and os.time() > req.expires then
    respond(id, { status = "expired", error = "request expired before it ran" })
    os.remove(D.work .. SEP .. name)
    return
  end
  local cmd = COMMANDS[req.cmd]
  if not cmd then
    respond(id, { status = "error", error = "unknown_command: " .. tostring(req.cmd) })
    os.remove(D.work .. SEP .. name)
    return
  end
  if req.expect_project and req.expect_project ~= json.null and project_path():lower() ~= req.expect_project:lower() then
    respond(id, { status = "error", error = "wrong_project: current is " .. project_path() })
    os.remove(D.work .. SEP .. name)
    return
  end
  local before = reaper.GetProjectStateChangeCount(0)
  if cmd.mutates then reaper.Undo_BeginBlock2(0); reaper.PreventUIRefresh(1) end
  local ok, result = pcall(cmd.run, req.args or {})
  -- measured before closing the undo block, which counts as a change of its own
  local changed = reaper.GetProjectStateChangeCount(0) ~= before
  if cmd.mutates then reaper.PreventUIRefresh(-1); reaper.Undo_EndBlock2(0, "mps: " .. req.cmd, -1) end
  if ok then
    respond(id, { status = "ok", result = result, project = project_path(), changed = changed })
  else
    local msg = tostring(result):gsub("^.-%.lua:%d+: ", "")
    respond(id, { status = "error", error = msg, project = project_path(), changed = changed })
  end
  os.remove(D.work .. SEP .. name)
end

local info = { instance = IID, bridge = VERSION, reaper = reaper.GetAppVersion(), started = os.time(),
               resource = reaper.GetResourcePath(), exe = reaper.GetExePath() }
publish(DIR, "info.json", json.encode(info), D.tmp)

-- One copy per REAPER process. The copy loaded by __startup.lua doesn't run as an action, so set_action_options
-- can't end it when `mps reaper start` launches another. The newest copy claims a non-persistent key instead, and
-- an older copy that sees someone else's id stops. Requests left in its req/ never run, which the client reports
-- as not_started.
reaper.SetExtState("mps_bridge", "owner", IID, false)

local last_beat = 0
local function loop()
  if reaper.GetExtState("mps_bridge", "owner") ~= IID then
    os.remove(DIR .. SEP .. "heartbeat")
    return
  end
  local now = reaper.time_precise()
  if now - last_beat >= 1 then
    local f = io.open(DIR .. SEP .. "heartbeat", "w")
    if f then f:write(tostring(os.time())); f:close() end
    last_beat = now
  end
  reaper.EnumerateFiles(D.req, -1) -- drop the cached listing of the folder
  local names, k = {}, 0
  while true do
    local n = reaper.EnumerateFiles(D.req, k)
    if not n then break end
    names[#names + 1] = n
    k = k + 1
  end
  table.sort(names)
  for _, n in ipairs(names) do
    -- an error outside a command (a malformed field, a full disk) answers that request and keeps the bridge running
    local ok, err = pcall(handle, n)
    if not ok then
      local id = n:match("^(.+)%.json$")
      if id then
        pcall(respond, id, { status = "error", error = "bridge: " .. tostring(err):gsub("^.-%.lua:%d+: ", "") })
      end
      os.remove(D.work .. SEP .. n)
    end
  end
  reaper.defer(loop)
end

reaper.atexit(function() os.remove(DIR .. SEP .. "heartbeat") end)
loop()
