# SSH Forward Manager

Manage named SSH port forwards for any application from your Noctalia bar or
the command line. OpenSSH carries traffic, and systemd keeps connections running
and reconnects after interruptions. The CLI works independently of Noctalia.
Saving a profile does not connect it. Autoconnect is not currently supported.

## Demo

Watch the 24-second walkthrough or expand the screenshots below.

https://github.com/user-attachments/assets/d8ccfb2f-2f86-4247-9c19-1b2305d6e1bb

<details>
<summary>Profiles and controls</summary>

#### Profile overview

Manage multiple connections.

![Profile overview](https://github.com/user-attachments/assets/0d4cfff7-b084-4e7d-bbe6-1191d68d62ee)

#### Connected profile

Open forwarded addresses in your browser or copy them.

![Connected profile](https://github.com/user-attachments/assets/e2bfbc62-eeed-4cf2-b821-e20ed10c09e1)

#### Disconnected profile

Connect a saved profile when you need it.

![Disconnected profile](https://github.com/user-attachments/assets/ef16f47b-350b-43ff-ad3a-d3c4c9f8c309)

#### Profile actions

Edit a profile, view logs, or delete it from the Actions menu.

![Profile actions](https://github.com/user-attachments/assets/ddae9c94-58ea-4030-a1be-ed8ce8bcf952)

#### Copy feedback

Copy an address to the clipboard.

![Copy feedback](https://github.com/user-attachments/assets/5a2c0884-605a-4a19-8b39-9a55305ba1d1)

#### Delete confirmation

Confirm before deleting a profile.

![Delete confirmation](https://github.com/user-attachments/assets/438df889-40ce-4203-a47d-08291747fb7c)

</details>

<details>
<summary>Creating and editing profiles</summary>

#### New profile

Choose a name, SSH destination, and ports.

![New profile](https://github.com/user-attachments/assets/0f6eb59b-c787-475a-950b-3124d5c4214c)

#### Edit profile

Check your SSH destination and apply changes to a running connection.

![Edit profile](https://github.com/user-attachments/assets/320e7f8d-488d-4477-8ed4-4552f39aba8a)

#### Port mappings

Forward different local and remote ports, with HTTP or HTTPS browser links.

![Port mappings](https://github.com/user-attachments/assets/54018fbb-7a52-49eb-88ff-db8b2c14863c)

#### Form validation

Missing or invalid fields are highlighted before saving.

![Form validation](https://github.com/user-attachments/assets/b523b64a-5b40-4aab-bc52-c9c08315f6a9)

</details>

<details>
<summary>Connection recovery and diagnostics</summary>

#### Reconnecting

Reconnect automatically after a connection interruption.

![Reconnecting](https://github.com/user-attachments/assets/4c6095e5-9f21-4f56-9624-5714ba806302)

#### Port conflict

See which application is using a port and how to resolve the conflict.

![Port conflict](https://github.com/user-attachments/assets/3002976b-8167-4935-8477-7cc94c1191e8)

#### Authentication failure

Find help with SSH user, key, and agent errors.

![Authentication failure](https://github.com/user-attachments/assets/9cbfa46f-dbd2-4241-9d5f-87452fd5d032)

#### Host verification

See when an SSH host key needs verification.

![Host verification](https://github.com/user-attachments/assets/ea15c612-6acd-417d-b0cf-5133dbed7e78)

#### Details and logs

View SSH connection logs.

![Details and logs](https://github.com/user-attachments/assets/1e92d5a3-7869-4fa1-b0ed-61c12ab162c6)

</details>

<details>
<summary>Empty state</summary>

#### Empty state

Create your first profile.

![Empty state](https://github.com/user-attachments/assets/c9038e68-0a00-4197-b9b4-19e2ad9ca7ef)

</details>

## Install

Requires Linux with systemd user services, Python 3.11+ and OpenSSH 8.7+.
The panel requires Noctalia v5 with plugin API 24 or newer. The plugin includes
its CLI; installation needs no root access or separate Python packages.

Optional tools: `xdg-open` for browser opening, `wl-copy` for CLI clipboard
copying, and `journalctl` for logs.

```sh
git clone https://github.com/ghillb/ssh-forward-manager.git
cd ssh-forward-manager
python3 install.py
```

The installer enables the plugin and adds its widget to your first configured
bar, preserving existing settings and backing up changed files. Keep Noctalia
running during installation and removal, and retain the checkout while using
this local plugin source. Use `python3 install.py --cli-only` for CLI-only use.

Add `~/.local/bin` to your shell's PATH if needed. Run `portforward doctor` to
check setup. If the panel reports a setup error, correct it and re-enable the
plugin. Before upgrading a uv-based installation, remove it using its original
installer; saved profiles are retained.

Disconnect profiles before rerunning the installer to update. Plugin-manager
updates also wait until profiles are disconnected; the panel shows pending updates.

## Use

Click the bar widget, add a profile name, SSH alias or `user@host`, and one or
more port mappings, then select Connect. Remote hosts are resolved from the SSH
server. Check host previews your SSH destination. Expand a profile to open or
copy its addresses; use Actions to edit, view logs, or delete it.

Saving a new profile leaves it disconnected. Editing a connected profile
briefly restarts its tunnel with the saved mappings.

Equivalent CLI controls:

```sh
portforward add development --name Development --host devbox \
  --map 3000:localhost:3000 --map 5432:localhost:5432
portforward resolve devbox
portforward doctor
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

Listeners bind to `127.0.0.1`. Port conflicts are reported without changing your
configured ports. Connected confirms that all local listeners are ready; remote
applications must also be running. Each connection forwards only its profile's
mappings, ignoring any forwards defined in SSH config.

SSH reuses your config, keys, known hosts and agent. No passwords or keys are
stored. Unlock encrypted keys with your SSH agent and confirm new or changed
host keys through SSH in a terminal before connecting.

Connections survive Noctalia restarts. Systemd reconnects after interruptions;
authentication, host-key and port errors require correction before retrying.
Disconnect cancels retries. Tunnels stop when your systemd user session or
machine shuts down. Applications must reconnect after a lost SSH transport.

## Storage and removal

Profiles: `$XDG_CONFIG_HOME/portforward/profiles.json` (default `~/.config`).
Diagnostics: `$XDG_STATE_HOME/portforward-manager` (default `~/.local/state`).
Control sockets and agent socket references: `$XDG_RUNTIME_DIR/portforward-manager`.
Backend source: `$XDG_DATA_HOME/portforward-manager/backend` (default `~/.local/share`).
CLI: `~/.local/bin/portforward`. Service: `$XDG_CONFIG_HOME/systemd/user/portforward@.service`.
Directories are private and profile files are mode 0600.

```sh
python3 install.py --remove
```

Checkout removal stops tunnels and removes the CLI, service, widget and local
plugin source. Saved profiles and configuration backups are retained.

For plugin-manager installations, disable the plugin, run
`~/.local/bin/portforward uninstall`, then remove the plugin in Noctalia.
Removing the plugin alone leaves the CLI and any tunnels running. Backend
removal stops tunnels and retains saved profiles.

## Development

```sh
uv sync
uv run pre-commit install
uv run ruff check portforward/backend tests install.py
uv run pyright
uv run pytest
noctalia plugins lint portforward
uv build
```

The CLI source is in `portforward/backend`. The plugin uses the CLI for controls
and status; systemd supervises SSH independently of Noctalia.
See the [Noctalia plugin API](https://docs.noctalia.dev/noctalia/plugins/development/runtime-api/)
for integration details.

CI checks pushes and pull requests. To release, align the versions in
`pyproject.toml`, `catalog.toml` and `portforward/plugin.toml`, update
`.github/release-notes.md`, then push a matching `vX.Y.Z` tag after checks pass.
The tag publishes a GitHub release; ordinary commits do not.
