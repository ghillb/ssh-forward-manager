--!nonstrict
local editor = require("./editor.luau")
local tr = noctalia.tr
local snapshot = noctalia.state.get("snapshot") or { profiles = {} }
local busy = noctalia.state.get("busy") or false
local expanded, pendingDelete, form, logText = nil, nil, nil, nil
local sequence = 0
local pending = nil

local function request(args, kind)
  if busy then return end
  sequence += 1
  pending = { token = tostring(os.time()) .. ":" .. sequence, kind = kind }
  busy = true
  noctalia.state.set("request", { token = pending.token, args = args })
  render()
end

local function newMapping(key, mapping)
  mapping = mapping or {}
  return { key = key, local_port = mapping.local_port and tostring(mapping.local_port) or "",
    remote_host = mapping.remote_host or "localhost",
    remote_port = mapping.remote_port and tostring(mapping.remote_port) or "", scheme = mapping.scheme or "http" }
end

local function edit(profile)
  sequence += 1
  form = { session = tostring(sequence), id = profile and profile.id or "p-" .. os.time() .. "-" .. math.random(10000, 99999),
    existing = profile ~= nil, live = profile and (profile.state == "connected" or profile.state == "connecting" or profile.state == "reconnecting"),
    name = profile and profile.name or "", host = profile and profile.host or "", mappings = {} }
  if profile then
    for index, mapping in ipairs(profile.mappings) do table.insert(form.mappings, newMapping(index, mapping)) end
  else
    table.insert(form.mappings, newMapping(1))
  end
  form.nextKey = #form.mappings + 1
  render()
end

local function saveForm()
  local mappings = {}
  for _, mapping in ipairs(form.mappings) do
    table.insert(mappings, { local_port = tonumber(mapping.local_port) or 0,
      remote_host = mapping.remote_host, remote_port = tonumber(mapping.remote_port) or 0, scheme = mapping.scheme })
  end
  local value = { id = form.id, name = form.name, host = form.host, mappings = mappings }
  request({ "put", noctalia.json.encode(value) }, "save")
end

local function resolveHost()
  if form.host == "" then form.error = tr("editor.host_required"); render(); return end
  busy = true
  render()
  local accepted = noctalia.runAsync({ noctalia.expandPath("~/.local/bin/portforward"), "resolve", form.host }, function(result)
    busy = false
    if not form then return end
    if result.exitCode ~= 0 then form.error = result.stderr; render(); return end
    local settings = noctalia.json.decode(result.stdout)
    if settings then
      form.resolved = (settings.user or "") .. " @ " .. (settings.hostname or "") .. " · SSH " .. (settings.port or "22")
      if settings.proxyjump then form.resolved ..= " · " .. settings.proxyjump end
      form.error = nil
    else
      form.error = tr("backend.invalid")
    end
    render()
  end)
  if not accepted then busy = false; form.error = tr("backend.failed"); render() end
end

local function logs(profile)
  busy = true
  render()
  local accepted = noctalia.runAsync({ noctalia.expandPath("~/.local/bin/portforward"), "logs", profile.id }, function(result)
    busy = false
    logText = result.exitCode == 0 and result.stdout or result.stderr
    render()
  end)
  if not accepted then busy = false; logText = tr("backend.failed"); render() end
end

local function profileCard(profile)
  local open = expanded == profile.id
  local active = profile.state == "connected" or profile.state == "connecting" or profile.state == "reconnecting"
  local color = profile.state == "error" and "error" or profile.state == "connected" and "primary" or "on_surface_variant"
  local rows = {
    ui.row({ gap = 8, align = "center", paddingH = 10, paddingV = 10 }, {
      ui.button({ glyph = open and "chevron-down" or "chevron-right", variant = "ghost",
        tooltip = tr("expand"), width = 30, onClick = function()
          if open then expanded = nil else expanded = profile.id end
          pendingDelete = nil
          render()
        end }),
      ui.column({ flexGrow = 1, gap = 3 }, {
        ui.label({ text = profile.name, fontWeight = "medium" }),
        ui.label({ text = profile.host .. " · " .. #profile.mappings .. " " .. tr("ports"), color = "on_surface_variant", fontSize = 12 }),
        ui.label({ text = tr("state." .. profile.state), color = color, fontSize = 12 }),
      }),
      ui.button({ text = active and tr("disconnect") or profile.state == "error" and tr("retry") or tr("connect"),
        variant = active and "outline" or "primary", enabled = not busy,
        onClick = function() request({ active and "disconnect" or "connect", profile.id }, "control") end }),
    }),
  }
  if open then
    table.insert(rows, ui.separator({ color = "outline" }))
    if profile.error ~= "" then
      table.insert(rows, ui.column({ paddingH = 12, paddingV = 6 }, {
        ui.label({ text = profile.error, color = profile.state == "error" and "error" or "on_surface_variant", fontSize = 12 }),
      }))
    end
    if profile.state == "reconnecting" then
      table.insert(rows, ui.column({ paddingH = 12 }, {
        ui.label({ text = tr("reconnecting_hint"), color = "on_surface_variant", fontSize = 12 }),
      }))
    end
    for _, mapping in ipairs(profile.mappings) do
      local address = "127.0.0.1:" .. mapping.local_port
      table.insert(rows, ui.row({ key = profile.id .. ":" .. mapping.local_port, gap = 8, align = "center", paddingH = 12, paddingV = 6 }, {
        ui.column({ flexGrow = 1, gap = 3 }, {
          ui.label({ text = address, fontSize = 13 }),
          ui.label({ text = "→ " .. mapping.remote_host .. ":" .. mapping.remote_port, color = "on_surface_variant", fontSize = 12 }),
        }),
        ui.button({ text = tr("open"), glyph = "external-link", variant = "ghost", enabled = not busy and profile.state == "connected",
          onClick = function() request({ "open", profile.id, tostring(mapping.local_port) }, "control") end }),
        ui.button({ text = tr("copy"), glyph = "copy", variant = "ghost", onClick = function()
          if noctalia.copyToClipboard(address, "text/plain") then noctalia.notify(tr("title"), tr("copied")) end
        end }),
      }))
    end
    table.insert(rows, ui.row({ gap = 6, paddingH = 10, paddingV = 6, justify = "end" }, {
      ui.button({ text = tr("logs"), variant = "ghost", enabled = not busy, onClick = function() logs(profile) end }),
      ui.button({ text = tr("edit"), variant = "ghost", enabled = not busy, onClick = function() edit(profile) end }),
      ui.button({ text = pendingDelete == profile.id and tr(active and "disconnect_delete" or "confirm_delete") or tr("delete"),
        variant = pendingDelete == profile.id and "destructive" or "ghost", enabled = not busy,
        onClick = function()
          if pendingDelete == profile.id then request({ "delete", profile.id }, "delete")
          else pendingDelete = profile.id; render() end
        end }),
      ui.button({ text = tr("cancel"), variant = "ghost", visible = pendingDelete == profile.id,
        enabled = not busy, onClick = function() pendingDelete = nil; render() end }),
    }))
  end
  return ui.column({ key = profile.id, gap = 0, fill = "surface_variant", radius = 6,
    border = "outline", borderWidth = 1 }, rows)
end

function render()
  if form then
    panel.render(editor.render(form, busy, {
      cancel = function() form = nil; render() end, save = saveForm, resolve = resolveHost,
      addPort = function()
        table.insert(form.mappings, newMapping(form.nextKey)); form.nextKey += 1; render()
      end,
      removePort = function(index) table.remove(form.mappings, index); render() end,
    }))
    return
  end
  if logText then
    panel.render(ui.column({ flexGrow = 1, gap = 12, paddingH = 16, paddingV = 14 }, {
      ui.row({ gap = 8, align = "center" }, {
        ui.button({ glyph = "arrow-left", tooltip = tr("back"), variant = "ghost", onClick = function() logText = nil; render() end }),
        ui.label({ text = tr("logs"), fontSize = 17 }),
      }),
      ui.scroll({ flexGrow = 1 }, { ui.label({ text = logText, fontSize = 12 }) }),
    }))
    return
  end
  local cards = {}
  for _, profile in ipairs(snapshot.profiles or {}) do table.insert(cards, profileCard(profile)) end
  if snapshot.error then table.insert(cards, ui.label({ text = snapshot.error, color = "error" })) end
  if #cards == 0 then table.insert(cards, ui.label({ text = tr("empty"), color = "on_surface_variant" })) end
  panel.render(ui.column({ flexGrow = 1, gap = 0 }, {
    ui.row({ gap = 10, align = "center", paddingH = 16, paddingV = 16 }, {
      ui.glyph({ name = "arrows-left-right", size = 20 }),
      ui.label({ text = tr("title"), fontSize = 17, fontWeight = "medium", flexGrow = 1 }),
      ui.button({ text = tr("add"), glyph = "plus", variant = "primary", enabled = not busy, onClick = function() edit(nil) end }),
      ui.button({ glyph = "x", tooltip = tr("close"), variant = "ghost", onClick = function() panel.close() end }),
    }),
    ui.scroll({ flexGrow = 1 }, { ui.column({ gap = 10, paddingH = 16, paddingV = 4 }, cards) }),
    ui.separator({ color = "outline" }),
    ui.row({ gap = 8, align = "center", paddingH = 16, paddingV = 12 }, {
      ui.glyph({ name = "lock", size = 14 }),
      ui.label({ text = tr("loopback"), color = "on_surface_variant", fontSize = 12 }),
    }),
  }))
end

function onOpen()
  noctalia.state.set("refresh", os.time())
  render()
end

noctalia.state.watch("snapshot", function(value) snapshot = value or snapshot; render() end)
noctalia.state.watch("busy", function(value) busy = value or false; render() end)
noctalia.state.watch("result", function(result)
  if not pending or result.token ~= pending.token then return end
  if result.ok then
    if pending.kind == "save" then expanded = form.id; form = nil end
    pendingDelete = nil
  elseif form then
    form.error = result.error
  else
    noctalia.notifyError(tr("title"), result.error)
  end
  pending = nil
  render()
end)
render()
