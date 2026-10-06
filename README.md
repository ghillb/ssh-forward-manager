# SSH Forward Manager

Manage named SSH port forwards for any application from your Noctalia bar or
the command line. OpenSSH carries traffic, and systemd keeps connections running
and reconnects after interruptions. The CLI works independently of Noctalia.
Saving a profile does not connect it. Autoconnect is not currently supported.

## Demo

Watch the 24-second walkthrough or expand the screenshots below.

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
