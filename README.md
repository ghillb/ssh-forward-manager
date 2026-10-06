# SSH Forward Manager

Named local TCP forwards for any application. OpenSSH carries traffic; one
systemd user service per connected profile owns retries and shutdown. The CLI
works without Noctalia. An optional native Noctalia v5 panel provides the same
profile controls. Saving a profile does not connect it. There is no autoconnect
in this release.

## Install

Requires Linux with systemd user services, OpenSSH, Python 3.12+ and uv. The panel
requires Noctalia v5 with plugin API 24. Browser opening uses xdg-open; CLI copy
uses wl-copy on Wayland.

```sh
git clone git@github.com:ghillb/ssh-forward-manager.git
cd ssh-forward-manager
python3 install.py
```

This installs the CLI and user service template, registers the repository as a
local Noctalia plugin source, enables `ghillb/portforward`, and adds its widget
to the first configured bar. Existing settings and widgets are preserved;
changed configuration files are backed up outside the repository. Use
`python3 install.py --cli-only` to omit desktop integration. No root access is
needed. Keep the checkout available while using the local plugin source.
Run desktop installation and removal while Noctalia is running, so its own
plugin controls can persist the changes. CLI-only installation needs no bar.

## Use

Click the forwarding icon in the bar. Add a name, SSH alias or `user@host`, and
one or more local-port → remote-host:remote-port mappings. Remote hosts are
resolved from the SSH server. Use Check host to preview OpenSSH's resolved
destination. Expand a profile for its ports, browser opening and copy-address
actions. The native Actions dropdown contains Edit, Details & logs, and Delete.
Its popup leaves port rows in place. A sole profile expands automatically.
Delete requires an inline confirmation. The panel uses a stable fixed height
with scrolling; Noctalia owns its dimensions and placement. Editing a connected
profile restarts its tunnel with the saved mappings; if the new settings fail,
the saved profile remains available for correction.

Equivalent CLI controls:

```sh
portforward add development --name Development --host devbox \
  --map 3000:localhost:3000 --map 5432:localhost:5432
portforward resolve devbox
portforward connect development
portforward status
portforward address development 3000
portforward copy development 3000
portforward open development 3000
portforward edit development --map 3000:localhost:8080
portforward logs development
portforward disconnect development
portforward delete development
```

`status` and `list` return JSON. `put '<profile JSON>'` creates or replaces a
complete profile, using the same validation as the editor. IPv6 remote hosts
use brackets in `--map`, for example `8080:[::1]:80`. `--scheme https` sets the
browser scheme when replacing mappings. Forwarding itself is protocol-agnostic.

## Connection behavior

Listeners bind to `127.0.0.1` only. Configured local ports are preserved. A
conflict reports the requested port instead of assigning a replacement. The
panel identifies current listening processes when Linux allows inspection;
process arguments are never collected. All mappings must be established before
the profile reports Connected. This means
the tunnel is ready, not that the destination application is healthy; a remote
connection refusal is shown as a diagnostic without stopping other ports.

SSH uses the existing config, keys, known-host policy and ssh-agent. No passwords
or keys are stored by this project. Unlock encrypted keys with your normal
ssh-agent before connecting. First-time host-key confirmation and changes to
trusted host keys must be resolved with ordinary SSH in a terminal. The panel
never requests credentials or weakens host-key verification.

The SSH connection is dedicated to the profile. Existing config forwards are
cleared from that connection; only the profile's mappings are then added through
OpenSSH's control socket. Other SSH sessions and config files are untouched.

Keepalives detect an unresponsive SSH peer in roughly 20–30 seconds. Systemd then
retries every five seconds. Authentication, host-key and local-port errors pause
retries until corrected and Connect is selected again. Disconnect cancels all
retries. Connections survive Noctalia reload, shutdown and restart; user-session
shutdown and machine shutdown still stop user services. Established application
TCP sessions cannot survive a lost SSH transport; applications must reconnect.

## Storage and removal

Profiles: `$XDG_CONFIG_HOME/portforward/profiles.json` (default `~/.config`).
Diagnostics: `$XDG_STATE_HOME/portforward-manager` (default `~/.local/state`).
Control sockets and agent socket references: `$XDG_RUNTIME_DIR/portforward-manager`.
Directories are private and profile files are mode 0600. Profiles, credentials,
logs and machine-specific test evidence do not belong in this repository.

```sh
python3 install.py --remove
```

Removal stops the project's tunnels, removes its widget, plugin source, service
template and CLI. Other desktop settings remain intact. Saved profiles and
configuration backups are retained; remove those directories yourself if no
longer needed. Upgrades use the same install command and require tunnels to be
disconnected first.

## Build and verify

```sh
uv sync
uv run pre-commit install
uv run ruff check src tests install.py
uv run pyright
uv run pytest
noctalia plugins lint portforward
uv build
```

Desktop acceptance testing uses the real Noctalia panel: add/edit/delete,
connect/disconnect, browser opening, copy-address, visible errors, and a live
forward that survives a Noctalia restart. Reconnection tests interrupt only
the test tunnel, never the workstation's network. Keep captures and test host
details outside Git. License: MIT.

## Noctalia integration

The plugin ID follows Noctalia's `<author>/<plugin>` convention. This repository's
catalog exposes `ghillb/portforward`; its panel is
`ghillb/portforward:panel` and its bar widget is `ghillb/portforward:indicator`.
The native Luau entries observe status and invoke the CLI with argument arrays;
they never own a tunnel. OpenSSH resolves aliases through `ssh -G`, so there is
no separate SSH config parser to maintain.

The current catalog's PortCtl manages local listening processes and SSH Launcher
opens terminal sessions. Neither supplies supervised forwarding profiles, so
this is a small dedicated plugin. It uses a local path source while developing;
Git plugin sources distribute plugin directories, so the backend installer is
still required. See Noctalia's [development workflow](https://docs.noctalia.dev/noctalia/plugins/development/workflow/),
[runtime API](https://docs.noctalia.dev/noctalia/plugins/development/runtime-api/),
and [community catalog](https://github.com/noctalia-dev/community-plugins/blob/main/catalog.toml).
