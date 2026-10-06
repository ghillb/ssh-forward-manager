--!nonstrict
local M = {}
local tr = noctalia.tr

function M.render(form, busy, callbacks)
  local rows = {
    ui.label({ text = tr("editor.name"), fontSize = 12, color = "on_surface_variant" }),
    ui.input({ key = "name-" .. form.session, value = form.name, placeholder = tr("editor.name_hint"),
      enabled = not busy, onChange = function(value) form.name = value end }),
    ui.label({ text = tr("editor.host"), fontSize = 12, color = "on_surface_variant" }),
    ui.row({ gap = 8 }, {
      ui.input({ key = "host-" .. form.session, value = form.host, placeholder = tr("editor.host_hint"),
        flexGrow = 1, enabled = not busy, onChange = function(value)
          form.host = value
          form.resolved = nil
        end }),
      ui.button({ text = tr("editor.check_host"), enabled = not busy, onClick = callbacks.resolve }),
    }),
  }
  if form.resolved then
    table.insert(rows, ui.label({ text = form.resolved, fontSize = 12, color = "primary" }))
  end
  table.insert(rows, ui.row({ gap = 8, align = "center" }, {
    ui.label({ text = tr("editor.ports"), flexGrow = 1, fontWeight = "medium" }),
    ui.button({ text = tr("editor.add_port"), glyph = "plus", variant = "ghost",
      enabled = not busy and #form.mappings < 32, onClick = callbacks.addPort }),
  }))
  for index, mapping in ipairs(form.mappings) do
    local key = form.session .. "-" .. mapping.key
    table.insert(rows, ui.column({ key = "mapping-" .. key, gap = 6 }, {
      ui.row({ gap = 8 }, {
        ui.column({ width = 98, gap = 4 }, {
          ui.label({ text = tr("editor.local_port"), fontSize = 12, color = "on_surface_variant" }),
          ui.input({ key = "local-" .. key, value = mapping.local_port, placeholder = "3000",
            enabled = not busy, onChange = function(value) mapping.local_port = value end }),
        }),
        ui.column({ flexGrow = 1, gap = 4 }, {
          ui.label({ text = tr("editor.remote_host"), fontSize = 12, color = "on_surface_variant" }),
          ui.input({ key = "remote-host-" .. key, value = mapping.remote_host, placeholder = "localhost",
            enabled = not busy, onChange = function(value) mapping.remote_host = value end }),
        }),
        ui.column({ width = 98, gap = 4 }, {
          ui.label({ text = tr("editor.remote_port"), fontSize = 12, color = "on_surface_variant" }),
          ui.input({ key = "remote-port-" .. key, value = mapping.remote_port, placeholder = "3000",
            enabled = not busy, onChange = function(value) mapping.remote_port = value end }),
        }),
        ui.button({ glyph = "x", tooltip = tr("editor.remove_port"), width = 34,
          variant = "ghost", enabled = not busy and #form.mappings > 1,
          onClick = function() callbacks.removePort(index) end }),
      }),
      ui.row({ gap = 8, align = "center" }, {
        ui.label({ text = tr("editor.browser"), fontSize = 12, color = "on_surface_variant" }),
        ui.select({ key = "scheme-" .. key, width = 106, options = { "HTTP", "HTTPS" },
          selectedIndex = mapping.scheme == "https" and 1 or 0, enabled = not busy,
          onChange = function(value) mapping.scheme = tonumber(value) == 1 and "https" or "http" end }),
      }),
    }))
  end
  table.insert(rows, ui.label({ text = tr(form.live and "editor.live_hint" or "editor.loopback"), color = "on_surface_variant", fontSize = 12 }))
  if form.error and form.error ~= "" then
    table.insert(rows, ui.label({ text = form.error, color = "error" }))
  end
  return ui.column({ flexGrow = 1, gap = 0 }, {
    ui.row({ gap = 8, align = "center", paddingH = 16, paddingV = 14 }, {
      ui.button({ glyph = "arrow-left", tooltip = tr("cancel"), variant = "ghost",
        enabled = not busy, onClick = callbacks.cancel }),
      ui.label({ text = form.existing and tr("editor.edit") or tr("editor.new"), fontSize = 17, fontWeight = "medium" }),
    }),
    ui.scroll({ flexGrow = 1 }, { ui.column({ gap = 12, paddingH = 20, paddingV = 8 }, rows) }),
    ui.separator({ color = "outline" }),
    ui.row({ gap = 8, paddingH = 16, paddingV = 12, justify = "end" }, {
      ui.button({ text = tr("cancel"), variant = "ghost", enabled = not busy, onClick = callbacks.cancel }),
      ui.button({ text = tr(form.live and "save_reconnect" or "save"), variant = "primary", enabled = not busy, onClick = callbacks.save }),
    }),
  })
end

return M
