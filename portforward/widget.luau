--!nonstrict
local function apply(snapshot)
  local connected, errors, retrying = 0, 0, 0
  for _, profile in ipairs(snapshot.profiles or {}) do
    if profile.state == "connected" then connected += 1 end
    if profile.state == "error" or profile.error ~= "" then errors += 1 end
    if profile.state == "connecting" or profile.state == "reconnecting" then retrying += 1 end
  end
  if snapshot.error then errors += 1 end
  barWidget.setGlyph(errors > 0 and "alert-circle" or "arrows-left-right")
  barWidget.setText(tostring(connected) .. (retrying > 0 and " …" or ""))
end

noctalia.state.watch("snapshot", function(snapshot) apply(snapshot or {}) end)
apply(noctalia.state.get("snapshot") or {})
function onClick() noctalia.togglePanel("ghillb/portforward:panel") end
