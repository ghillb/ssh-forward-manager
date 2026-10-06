# SSH Forward Manager

Manage named SSH port forwards for any application from your Noctalia bar or
the command line. OpenSSH carries traffic, and systemd keeps connections running
and reconnects after interruptions. The CLI works independently of Noctalia.
Saving a profile does not connect it. Autoconnect is not currently supported.

## Demo

Create profiles, manage connections, and access forwarded ports from your
Noctalia bar. Watch the 24-second walkthrough or expand the screenshots below.

https://github.com/user-attachments/assets/a760432b-5c6e-403a-b22f-cb1039b051eb

<details>
<summary>Profiles and controls</summary>

#### Profile overview

Manage multiple connections.

![Profile overview](https://github.com/user-attachments/assets/529f87f1-08f4-47fd-8771-e53e741e991d)

#### Connected profile

Open forwarded addresses in your browser or copy them.

![Connected profile](https://github.com/user-attachments/assets/c1a5fb42-b0e3-477a-844a-b84f6f117414)

#### Disconnected profile

Connect a saved profile when you need it.

![Disconnected profile](https://github.com/user-attachments/assets/018e1b36-08cb-48eb-be52-9b2b568a963b)

#### Profile actions

Edit a profile, view logs, or delete it from the Actions menu.

![Profile actions](https://github.com/user-attachments/assets/b6d31101-a5a7-47a8-b902-1dc076f9d839)

#### Copy feedback

Copy an address to the clipboard.

![Copy feedback](https://github.com/user-attachments/assets/14b78b38-2373-4b71-bae4-bd4ca9e08930)

#### Delete confirmation

Confirm before deleting a profile.

![Delete confirmation](https://github.com/user-attachments/assets/00c2f4a1-c82a-4164-910c-895da576f71d)

</details>

<details>
<summary>Creating and editing profiles</summary>

#### New profile

Choose a name, SSH destination, and ports.

![New profile](https://github.com/user-attachments/assets/8fe7db99-1f56-4edb-a69c-bfe33088757c)

#### Edit profile

Check your SSH destination and apply changes to a running connection.

![Edit profile](https://github.com/user-attachments/assets/6f980310-7be2-4f5c-9a8b-079e96b64ac9)

#### Port mappings

Forward different local and remote ports, with HTTP or HTTPS browser links.

![Port mappings](https://github.com/user-attachments/assets/421aee0c-9193-40d2-807e-171567a27db3)

#### Form validation

Missing or invalid fields are highlighted before saving.

![Form validation](https://github.com/user-attachments/assets/48deb651-006e-463a-93dd-312821a5c20f)

</details>

<details>
<summary>Connection recovery and diagnostics</summary>

#### Reconnecting

Reconnect automatically after a connection interruption.

![Reconnecting](https://github.com/user-attachments/assets/bbccaa20-49d1-40e3-99b7-8e1b0626db2d)

#### Port conflict

See which application is using a port and how to resolve the conflict.

![Port conflict](https://github.com/user-attachments/assets/3ecfbe4e-369a-4cf5-9a2c-a98359e79231)

#### Authentication failure

Find help with SSH user, key, and agent errors.

![Authentication failure](https://github.com/user-attachments/assets/b80d9678-f5b6-48c6-a848-84c50ee993a4)

#### Host verification

See when an SSH host key needs verification.

![Host verification](https://github.com/user-attachments/assets/55abdfb1-cd37-4b53-88f9-f69dc520e03e)

#### Details and logs

View SSH connection logs.

![Details and logs](https://github.com/user-attachments/assets/1417aa86-ce25-438a-a4e7-33d288792677)

</details>

<details>
<summary>Empty state</summary>

#### Empty state

Create your first profile.

![Empty state](https://github.com/user-attachments/assets/b8c778fa-3394-4e4e-8aa4-3e39104c46eb)

</details>

## Install

Requires Linux with systemd user services, OpenSSH, Python 3.12+ and uv. The panel
requires Noctalia v5 with plugin API 24. Browser opening uses xdg-open; CLI copy
uses wl-copy on Wayland.

```sh
git clone https://github.com/ghillb/ssh-forward-manager.git
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
actions. The Actions menu contains Edit, Details & logs, and Delete. A sole
profile expands automatically. Deleting a profile requires confirmation.
The panel adjusts its initial height to your profiles and keeps its position
and size while you navigate. Forms and logs scroll within the panel.
Editing a connected profile restarts its tunnel with the saved mappings; if the
new settings fail, the saved profile remains available for correction.

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
Directories are private and profile files are mode 0600.

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

## Noctalia integration

The plugin ID follows Noctalia's `<author>/<plugin>` convention. This repository's
catalog exposes `ghillb/portforward`; its panel is
`ghillb/portforward:panel` and its bar widget is `ghillb/portforward:indicator`.
The Noctalia plugin uses the CLI to manage profiles and display connection
status. Systemd supervises the SSH connections independently of the bar.
OpenSSH resolves SSH aliases through `ssh -G`.

The plugin requires the backend installed by `python3 install.py`.
See Noctalia's [development workflow](https://docs.noctalia.dev/noctalia/plugins/development/workflow/),
[runtime API](https://docs.noctalia.dev/noctalia/plugins/development/runtime-api/),
and [community catalog](https://github.com/noctalia-dev/community-plugins/blob/main/catalog.toml).
