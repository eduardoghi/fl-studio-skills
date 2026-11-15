-- Renders the project this REAPER process opened, with its saved render settings, then quits.
--
-- `mps render` starts a new REAPER process with the project and this script on the command line, and the variables
-- MPS_ROLE=render, MPS_RENDER_PROJECT (the project's path), MPS_RENDER_LOG (where to write what the render saw) and
-- MPS_RENDER_SETTLE. Two waits matter (docs/render-standard.md):
--
-- - Before rendering. When this script starts, the project's tempo isn't applied yet (a 90 BPM project still read
--   120), and a render then played the MIDI at the wrong tempo. The script waits until the project is the current
--   one and a second has passed, and records the tempo it renders with, for mps render to check.
-- - After rendering. Quitting right after a render with Kontakt loaded ended the process with exit code 0xC000000D,
--   so the script waits MPS_RENDER_SETTLE seconds (3 by default) before quitting.

if os.getenv("MPS_ROLE") ~= "render" then return end

local want = (os.getenv("MPS_RENDER_PROJECT") or ""):lower()
local log_path = os.getenv("MPS_RENDER_LOG")
local settle = tonumber(os.getenv("MPS_RENDER_SETTLE") or "") or 3
local BEFORE = 1.0

local function current_project()
  local _, path = reaper.EnumProjects(-1)
  return (path or ""):lower()
end

local function log(fields)
  if not log_path then return end
  local f = io.open(log_path, "w")
  if not f then return end
  local parts = {}
  for k, v in pairs(fields) do
    local value = type(v) == "number" and string.format("%.10g", v) or string.format("%q", tostring(v))
    parts[#parts + 1] = string.format("%q:%s", k, value)
  end
  f:write("{", table.concat(parts, ","), "}")
  f:close()
end

local t0 = reaper.time_precise()
local rendered_at

local function step()
  local now = reaper.time_precise()
  if not rendered_at then
    if now - t0 < BEFORE or (want ~= "" and current_project() ~= want) then
      if now - t0 > 120 then
        log({ error = "the project never became current", current = current_project() })
        reaper.Main_OnCommand(40004, 0)
        return
      end
      return reaper.defer(step)
    end
    -- Master_GetTempo rounds to three decimals (104.4858 read 104.486), so the length of the first quarter note is
    -- recorded too, which mps render checks against the saved tempo
    log({ tempo = reaper.Master_GetTempo(), qn_seconds = reaper.TimeMap2_QNToTime(0, 1),
          project = current_project(), waited = now - t0 })
    reaper.Main_OnCommand(42230, 0) -- File: Render project, using the most recent render settings, auto-close dialog
    rendered_at = reaper.time_precise()
    return reaper.defer(step)
  end
  if now - rendered_at < settle then return reaper.defer(step) end
  -- Loading can mark the project as changed (it did with Kontakt and a load delay), and Quit would then ask whether to
  -- save. Opening an empty project without the prompt drops those changes in memory and leaves the file alone.
  if log_path then
    local empty = log_path .. ".empty.rpp"
    local f = io.open(empty, "w")
    if f then
      f:write("<REAPER_PROJECT 0.1\n>\n")
      f:close()
      reaper.Main_openProject("noprompt:" .. empty)
      os.remove(empty)
    end
  end
  reaper.Main_OnCommand(40004, 0) -- File: Quit REAPER
end

step()
