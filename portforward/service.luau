--!nonstrict
-- This entry observes the backend; it never owns or stops SSH processes.
local cli = noctalia.expandPath("~/.local/bin/portforward")
local reading = false
local busy = false
local lastRequest = nil
noctalia.setUpdateInterval(2000)

local function publishError(message)
  noctalia.state.set("snapshot", { profiles = {}, error = message })
end

local function refresh()
  if reading or busy then return end
  if not noctalia.fileExists(cli) then
    publishError(noctalia.tr("backend.missing"))
    return
  end
  reading = true
  local accepted = noctalia.runAsync({ cli, "status" }, function(result)
    reading = false
    if result.exitCode ~= 0 then
      publishError(result.stderr ~= "" and result.stderr or noctalia.tr("backend.failed"))
      return
    end
    local value, err = noctalia.json.decode(result.stdout)
    if value == nil or type(value.profiles) ~= "table" then
      publishError(err or noctalia.tr("backend.invalid"))
      return
    end
    noctalia.state.set("snapshot", value)
  end)
  if not accepted then
    reading = false
    publishError(noctalia.tr("backend.failed"))
  end
end

noctalia.state.watch("request", function(request)
  if request == nil or request.token == lastRequest or busy then return end
  lastRequest = request.token
  busy = true
  noctalia.state.set("busy", true)
  local argv = { cli }
  for _, arg in ipairs(request.args) do table.insert(argv, arg) end
  local function finished(ok, error)
    busy = false
    noctalia.state.set("busy", false)
    noctalia.state.set("result", { token = request.token, ok = ok, error = error })
    refresh()
  end
  local accepted = noctalia.runAsync(argv, function(result)
    finished(result.exitCode == 0, result.stderr or "")
  end)
  if not accepted then finished(false, noctalia.tr("backend.failed")) end
end)

noctalia.state.watch("refresh", function() refresh() end)
function update() refresh() end
refresh()
