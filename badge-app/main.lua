local profiles = {{name="Oscar Ryley",linkedin="linkedin.com/in/oscar-ryley/",posts=3,average=0.6713,classification="unknown",posts_data={{text="A realistic mock post from oscar-ryley: shipping useful work beats shipping noise.",probability=0.013802968541523646,class="unknown",report="Your free credit is reserved for Memory & RAG, so it can't cover LLM chat. Add credits or start a subscription on the Billing page to continue \u2014 and turn on auto-reload so your balance tops up automatically and you're never interrupted mid-conversation."},{text="We learned more from one customer conversation than from a week of dashboards.",probability=1,class="unknown",report="Your free credit is reserved for Memory & RAG, so it can't cover LLM chat. Add credits or start a subscription on the Billing page to continue \u2014 and turn on auto-reload so your balance tops up automatically and you're never interrupted mid-conversation."},{text="Small teams move faster when the next decision is visible to everyone.",probability=1,class="unknown",report="Your free credit is reserved for Memory & RAG, so it can't cover LLM chat. Add credits or start a subscription on the Billing page to continue \u2014 and turn on auto-reload so your balance tops up automatically and you're never interrupted mid-conversation."}}}}

local mode = "list"
local selected = 1
local page = 0
local title
local body
local status
local hint
local contact_count = 0

local function percent(value)
	return math.floor(value * 100 + 0.5) .. "%"
end

local function set_leds(r, g, b)
	badge.led.set_all(r, g, b)
	badge.led.show()
end

local function csv_cell(value)
	local text = tostring(value or "")
	return '"' .. string.gsub(text, '"', '""') .. '"'
end

local function snapshot_contacts()
	contact_count = badge.contacts.count()
	local lines = {"name,role,badge_id,received_unix"}
	for index = 1, contact_count do
		local contact = badge.contacts.get(index)
		if contact then
			lines[#lines + 1] = table.concat({
				csv_cell(contact.name),
				csv_cell(contact.role),
				csv_cell(contact.badge_id),
				csv_cell(contact.received_unix)
			}, ",")
		end
	end
	badge.fs.write("appdata/contacts.csv", table.concat(lines, "\n"))
end

local function paint_list()
	mode = "list"
	page = 0
	title:set_text("Slop Scanner  " .. selected .. "/" .. #profiles)
	local lines = {}
	for index = 1, #profiles do
		local mark = index == selected and "> " or "  "
		local profile = profiles[index]
		lines[#lines + 1] = mark .. profile.name .. "  " .. percent(profile.average)
	end
	body:set_text(table.concat(lines, "\n"))
	status:set_text("A open / " .. contact_count .. " contacts snapshotted")
	hint:set_text("UP/DOWN select   A open\nHOME exit")
	set_leds(0, 48, 96)
end

local function paint_detail()
	local profile = profiles[selected]
	mode = "detail"
	if page == 0 then
		title:set_text(profile.name .. "  " .. percent(profile.average))
		body:set_text(profile.linkedin .. "\n\nGPTZero: " .. profile.classification ..
			"\nPosts analyzed: " .. profile.posts ..
			"\nAverage AI probability: " .. percent(profile.average) ..
			"\n\nThis is a review aid, not proof of authorship.")
		status:set_text("Profile report")
		set_leds(255, 150, 0)
	else
		local post = profile.posts_data[page]
		title:set_text(profile.name .. "  POST " .. page .. "/3")
		body:set_text("GPTZero: " .. percent(post.probability) .. " " .. post.class ..
			"\n\n" .. post.text .. "\n\nBackboard:\n" .. post.report)
		status:set_text("Full post report")
		if post.probability >= 0.7 then
			set_leds(180, 24, 24)
		elseif post.probability >= 0.45 then
			set_leds(255, 150, 0)
		else
			set_leds(24, 180, 90)
		end
	end
	hint:set_text("A next page   L/R post\nB back   HOME exit")
end

function on_enter(root)
	snapshot_contacts()
	local background = badge.ui.box(root, 312, 232)
	background:set_pos(4, 4)
	background:style({bg_color = 0x101820, radius = 6})
	title = badge.ui.label(background, "Slop Scanner")
	title:style({text_font = 20, text_color = 0xffffff})
	title:set_pos(12, 10)
	body = badge.ui.label(background, "")
	body:style({text_font = 16, text_color = 0xd7e6f2})
	body:set_pos(12, 42)
	body:set_size(288, 118)
	status = badge.ui.label(background, "")
	status:style({text_font = 14, text_color = 0xffc857})
	status:set_pos(12, 166)
	hint = badge.ui.label(background, "")
	hint:style({text_font = 14, text_color = 0xaec4d4})
	hint:set_pos(12, 190)
	paint_list()
end

function on_button(button, kind)
	if kind ~= badge.input.KIND.PRESSED then return end
	local B = badge.input.BUTTON
	if mode == "list" then
		if button == B.UP then
			selected = (selected - 2) % #profiles + 1
			paint_list()
		elseif button == B.DOWN then
			selected = selected % #profiles + 1
			paint_list()
		elseif button == B.A then
			paint_detail()
		end
	else
		if button == B.B then
			paint_list()
		elseif button == B.A then
			page = (page + 1) % 4
			paint_detail()
		elseif button == B.LEFT then
			page = page == 0 and 3 or (page - 2) % 3 + 1
			paint_detail()
		elseif button == B.RIGHT then
			page = page == 0 and 1 or page % 3 + 1
			paint_detail()
		end
	end
end

function on_exit()
	badge.led.clear()
	badge.led.show()
end
