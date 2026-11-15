-- Renders the project this REAPER process opened, with its saved render settings, then quits.
--
-- `mps render` starts a new REAPER process with the project and this script on the command line, and the variable
-- MPS_ROLE=render. Quitting right after a render with Kontakt loaded made the process end with exit code 0xC000000D
-- (docs/render-standard.md), so the script waits MPS_RENDER_SETTLE seconds (3 by default) before quitting.

if os.getenv("MPS_ROLE") ~= "render" then return end

local settle = tonumber(os.getenv("MPS_RENDER_SETTLE") or "") or 3
reaper.Main_OnCommand(42230, 0) -- File: Render project, using the most recent render settings, auto-close dialog
local t0 = reaper.time_precise()
local function quit_later()
  if reaper.time_precise() - t0 < settle then return reaper.defer(quit_later) end
  reaper.Main_OnCommand(40004, 0) -- File: Quit REAPER
end
quit_later()
