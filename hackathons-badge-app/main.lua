--[==[badge-app
slug=mlh_events
name=My Hackathons
icon=HUK
api=2
heap_kb=48
]==]

local screen
local build_index = 1
local VISIBLE_ROWS = 6
local top_idx = 1
local count_lbl, hint_lbl
local rows = {}

-- All 33 hackathons from Oscar Ryley's portfolio in exact order (#33 down to #1)
local hackathons = {
  {num = 33, name = "Hack the North 2026",    date = "18-20 Sep 2026"},
  {num = 32, name = "EasyA UK Parliament",   date = "4 Sep 2026"},
  {num = 31, name = "Google AI Summer School",date = "8 Jul 2026"},
  {num = 30, name = "Hackabury",              date = "1-2 Jun 2026"},
  {num = 29, name = "KentHackIt",             date = "9-10 May 2026"},
  {num = 28, name = "HackUPC 2026",           date = "24-26 Apr 2026"},
  {num = 27, name = "Hack Kosice 2026",       date = "18-19 Apr 2026"},
  {num = 26, name = "Dundee Quackathon 2026", date = "21-22 Mar 2026"},
  {num = 25, name = "DUWiT Hacks 2026",       date = "7-8 Mar 2026"},
  {num = 24, name = "HackSussex 2026",        date = "28 Feb-1 Mar 2026"},
  {num = 23, name = "HudHack",                date = "26 Feb 2026"},
  {num = 22, name = "HackEurope",             date = "21-22 Feb 2026"},
  {num = 21, name = "AstonHack 11",           date = "7-8 Feb 2026"},
  {num = 20, name = "IC Hack 26",             date = "31 Jan-1 Feb 2026"},
  {num = 19, name = "HackSussex Game Jam",    date = "6-7 Dec 2025"},
  {num = 18, name = "HackSheffield 10",       date = "29-30 Nov 2025"},
  {num = 17, name = "GreatUniHack 2025",      date = "8-9 Nov 2025"},
  {num = 16, name = "DurHack X",              date = "1-2 Nov 2025"},
  {num = 15, name = "HackNotts 25",           date = "25-26 Oct 2025"},
  {num = 14, name = "WHACK 2025",             date = "18-19 Oct 2025"},
  {num = 13, name = "UK Quantum Hackathon",   date = "21-23 Jul 2025"},
  {num = 12, name = "SpurHacks",              date = "20-22 Jun 2025"},
  {num = 11, name = "DragonHacks XI",         date = "26-27 Apr 2025"},
  {num = 10, name = "Dundee Quackathon 2025", date = "8-9 Mar 2025"},
  {num = 9,  name = "DUWiT Hacks 2025",       date = "1-2 Mar 2025"},
  {num = 8,  name = "AstonHack 10",           date = "22-23 Feb 2025"},
  {num = 7,  name = "LeedsHack 2025",         date = "8-9 Feb 2025"},
  {num = 6,  name = "hackSheffield 9",        date = "16-17 Nov 2024"},
  {num = 5,  name = "DurHack 2024",           date = "2-3 Nov 2024"},
  {num = 4,  name = "HackNotts 24",           date = "26-27 Oct 2024"},
  {num = 3,  name = "Dundee Quackathon 2024", date = "9-10 Mar 2024"},
  {num = 2,  name = "LanHack23",              date = "25-26 Nov 2023"},
  {num = 1,  name = "DurHack 2023",           date = "4-5 Nov 2023"}
}

local MAX_TOP = #hackathons - VISIBLE_ROWS + 1

local function render_rows()
  count_lbl:set_text(string.format("%d-%d of %d", top_idx, top_idx + VISIBLE_ROWS - 1, #hackathons))
  
  for i = 1, VISIBLE_ROWS do
    local r = rows[i]
    local item = hackathons[top_idx + i - 1]
    if item then
      r.box:hidden(false)
      r.num:set_text(string.format("#%d", item.num))
      r.name:set_text(item.name)
      r.date:set_text(item.date)
      r.date:align("right_mid", -6, 0)
    else
      r.box:hidden(true)
    end
  end

  -- Physical LED scrollbar: Top pair {1, 2}, Middle {6, 3}, Bottom {5, 4}
  badge.led.clear()
  local ratio = (top_idx - 1) / (MAX_TOP - 1)
  if ratio < 0.33 then
    badge.led.set(1, 0, 180, 255); badge.led.set(2, 0, 180, 255)
  elseif ratio < 0.67 then
    badge.led.set(6, 0, 180, 255); badge.led.set(3, 0, 180, 255)
  else
    badge.led.set(5, 0, 180, 255); badge.led.set(4, 0, 180, 255)
  end
  badge.led.show()
end

function on_enter(root)
  screen = root
  build_index = 1
  top_idx = 1

  local title = badge.ui.label(root, "Oscar's Hackathons")
  title:align("top_left", 8, 4)
  title:style({text_font = 16, text_color = 0xffffff})

  count_lbl = badge.ui.label(root, "Loading...")
  count_lbl:align("top_right", -8, 5)
  count_lbl:style({text_font = 14, text_color = 0x94a3b8})

  hint_lbl = badge.ui.label(root, "Loading list...")
  hint_lbl:align("bottom_mid", 0, -6)
  hint_lbl:style({text_font = 14, text_color = 0x64748b})

  badge.led.clear()
  badge.led.show()
end

function on_tick()
  -- Build the 6 row widgets over 6 ticks to stay well under the deadline
  if build_index <= VISIBLE_ROWS then
    local y = 24 + (build_index - 1) * 29

    local box = badge.ui.box(screen, 308, 26)
    box:set_pos(6, y)
    box:style({bg_color = 0x1e222b, radius = 4, border_width = 1, border_color = 0x334155})

    local num = badge.ui.label(box, "")
    num:set_pos(6, 4)
    num:style({text_font = 14, text_color = 0x38bdf8})

    local name = badge.ui.label(box, "")
    name:set_pos(38, 4)
    name:style({text_font = 14, text_color = 0xffffff})

    local date = badge.ui.label(box, "")
    date:align("right_mid", -6, 0)
    date:style({text_font = 14, text_color = 0x94a3b8})

    table.insert(rows, {box = box, num = num, name = name, date = date})

    -- Blue sweep progress
    badge.led.set(build_index, 0, 100, 255)
    badge.led.show()

    build_index = build_index + 1

    if build_index > VISIBLE_ROWS then
      hint_lbl:set_text("Up/Down: Scroll   L/R: Page   HOME: Exit")
      render_rows()
    end
  end
end

function on_button(btn, kind)
  if kind ~= badge.input.KIND.PRESSED then return end
  if build_index <= VISIBLE_ROWS then return end

  local B = badge.input.BUTTON
  if btn == B.DOWN then
    if top_idx < MAX_TOP then
      top_idx = top_idx + 1
      render_rows()
    end
  elseif btn == B.UP then
    if top_idx > 1 then
      top_idx = top_idx - 1
      render_rows()
    end
  elseif btn == B.RIGHT then
    top_idx = math.min(MAX_TOP, top_idx + VISIBLE_ROWS)
    render_rows()
  elseif btn == B.LEFT then
    top_idx = math.max(1, top_idx - VISIBLE_ROWS)
    render_rows()
  elseif btn == B.A then
    top_idx = 1
    render_rows()
  elseif btn == B.B then
    top_idx = MAX_TOP
    render_rows()
  end
end

function on_exit()
  badge.led.clear()
  badge.led.show()
end