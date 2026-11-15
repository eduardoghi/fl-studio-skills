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

if os.getenv("MPS_ROLE") == "render" then return end

local VERSION = "0.1.4"

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
  return { index = i, guid = reaper.GetTrackGUID(tr), name = name, fx = fx, items = items,
           volume = reaper.GetMediaTrackInfo_Value(tr, "D_VOL"), pan = reaper.GetMediaTrackInfo_Value(tr, "D_PAN"),
           mute = reaper.GetMediaTrackInfo_Value(tr, "B_MUTE") == 1 }
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
  return { project = project_path(), dirty = reaper.IsProjectDirty(0) ~= 0, bpm = bpm, beats_per_measure = bpi,
           srate = reaper.GetSetProjectInfo(0, "PROJECT_SRATE", 0, false), tracks = tracks }
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

COMMANDS["item.add_midi"] = { mutates = true, run = function(a)
  local tr = track_by_guid(need(a, "track", "string"))
  local it = reaper.CreateNewMIDIItemInProj(tr, need(a, "start_qn", "number"), need(a, "end_qn", "number"), true)
  if not it then error("failed: CreateNewMIDIItemInProj") end
  local _, g = reaper.GetSetMediaItemInfo_String(it, "GUID", "", false)
  return { guid = g, position = reaper.GetMediaItemInfo_Value(it, "D_POSITION"),
           length = reaper.GetMediaItemInfo_Value(it, "D_LENGTH") }
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

COMMANDS["render.configure"] = { mutates = true, run = function(a)
  local fmt = RENDER_FORMATS[need(a, "format", "string")] or error("bad_args: format must be wav16, wav24 or wav32f")
  reaper.GetSetProjectInfo_String(0, "RENDER_FILE", need(a, "directory", "string"), true)
  reaper.GetSetProjectInfo_String(0, "RENDER_PATTERN", need(a, "pattern", "string"), true)
  reaper.GetSetProjectInfo_String(0, "RENDER_FORMAT", fmt, true)
  reaper.GetSetProjectInfo(0, "RENDER_SETTINGS", 0, true)       -- master mix only
  reaper.GetSetProjectInfo(0, "RENDER_BOUNDSFLAG", 0, true)      -- custom start and end
  reaper.GetSetProjectInfo(0, "RENDER_STARTPOS", need(a, "start", "number"), true)
  reaper.GetSetProjectInfo(0, "RENDER_ENDPOS", need(a, "end", "number"), true)
  reaper.GetSetProjectInfo(0, "RENDER_SRATE", need(a, "srate", "number"), true)
  reaper.GetSetProjectInfo(0, "RENDER_CHANNELS", need(a, "channels", "number"), true)
  reaper.GetSetProjectInfo(0, "RENDER_TAILFLAG", 0, true)
  reaper.GetSetProjectInfo(0, "RENDER_ADDTOPROJ", 0, true)
  local _, targets = reaper.GetSetProjectInfo_String(0, "RENDER_TARGETS", "", false)
  local _, f = reaper.GetSetProjectInfo_String(0, "RENDER_FORMAT", "", false)
  return { targets = targets, format = f, start = reaper.GetSetProjectInfo(0, "RENDER_STARTPOS", 0, false),
           ["end"] = reaper.GetSetProjectInfo(0, "RENDER_ENDPOS", 0, false),
           srate = reaper.GetSetProjectInfo(0, "RENDER_SRATE", 0, false),
           channels = reaper.GetSetProjectInfo(0, "RENDER_CHANNELS", 0, false) }
end }

---------------------------------------------------------------------------------------------------------------- loop
local function respond(id, body)
  body.id = id
  body.instance = IID
  body.finished = os.time()
  publish(D.res, id .. ".json", json.encode(body), D.tmp)
end

local function handle(name)
  local id = name:match("^(.+)%.json$")
  if not id then return end
  -- claim it. A failed rename means something else took the request, or the client withdrew it
  if not os.rename(D.req .. SEP .. name, D.work .. SEP .. name) then return end
  local raw = read_file(D.work .. SEP .. name)
  local okp, req = pcall(json.decode, raw or "")
  if not okp or type(req) ~= "table" then
    respond(id, { status = "error", error = "bad_request: " .. tostring(req) })
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

local last_beat = 0
local function loop()
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
  for _, n in ipairs(names) do handle(n) end
  reaper.defer(loop)
end

reaper.atexit(function() os.remove(DIR .. SEP .. "heartbeat") end)
loop()
