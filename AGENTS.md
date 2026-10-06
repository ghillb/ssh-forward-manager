# Repository guidance

## Architecture boundaries

`portforward/backend` is the canonical Python source and systemd unit bundle.
The Luau plugin calls the same CLI as terminal users; do not introduce a second
profile store or connection implementation. `install.py` handles checkout
installation and desktop registration; backend setup also runs from the plugin.
Edit repository sources, not copies in the user's installed backend directory.

- Keep the backend independent of Noctalia, its plugin source directory and VS Code.
  Systemd user services own the SSH lifecycle; plugin shutdown must not stop tunnels.
- Preserve configured ports and loopback binding. Report conflicts; never select
  replacement ports. Report Connected only after every listener belongs to this
  profile's SSH process. This does not prove remote application availability.
- Reuse OpenSSH configuration, keys, known hosts and agent. Never store passwords,
  weaken host verification or import unrelated SSH-config forwarding rules.
- Saving a new profile leaves it disconnected. Autoconnect is outside current scope.
  Disconnect must stop the service and cancel reconnection attempts.
- Keep CLI JSON responses and panel consumers consistent when changing status,
  errors or profile validation. Use argv lists for subprocesses, not shell interpolation.

## Installation and portability

- The runtime uses the Python standard library; uv is development tooling. Follow
  the Python minimum in `pyproject.toml`, including bootstrap code that may execute
  before version validation. Do not require pip or uv for plugin-manager installation.
- Maintain one self-contained plugin package. Keep dependency declarations in
  `catalog.toml` and `portforward/plugin.toml` aligned; optional action tools must
  not prevent forwarding. Keep the bundled LICENSE aligned with the root LICENSE.
- Preserve unrelated desktop settings, user profiles and files this installer does
  not own. Retain ownership checks, private permissions and rollback on setup failure.
- Installed backend copies must survive plugin removal. Defer backend replacement
  while profiles run. Explicit backend removal stops tunnels but retains profiles.
- Distinguish supported prerequisites from tested environments. Do not claim
  distribution compatibility from a successful test on one machine.

## Validation

Run commands from the repository root. Development setup:

```sh
uv sync
uv run pre-commit install
```

For a backend bug, reproduce the failure with a focused regression test before
fixing it. Assert observable behavior rather than copying implementation logic.
Start with the affected tests:

```sh
uv run pytest tests/test_portability.py -q
```

Before committing, stage the intended files and run `uv run pre-commit run`.
The hooks cover Ruff, strict Pyright, Noctalia plugin lint and Python lifecycle
tests. Never use `--all-files`, bypass hooks or modify unrelated files to satisfy
them. Run `uv build` when packaging changes and inspect both wheel and source
archive for the required bundle files.

Tests use temporary storage, mocked service controls and local sockets; they do
not install into the real desktop or connect to remote SSH hosts. Installation
and live-desktop verification are separate operations. Within the authorized
scope, use temporary profiles and fixtures, preserve existing configuration and
restore it afterward. For UI changes, verify the native panel alongside Noctalia
components, including Actions/Edit staying on the same panel. For lifecycle
changes, verify real forwarding, reconnection, disconnect, occupied ports and
survival across a full Noctalia restart. Keep machine-specific evidence outside Git.

## Public repository and documentation

- Never commit real profiles, SSH destinations, private network names, local
  usernames or home paths, credentials, runtime state, logs or identifying captures.
  Use neutral examples and inspect media for identifying content before publishing.
- Screenshots and clips belong on asset hosting, linked from the README; do not
  add them to Git. Keep README screenshots in collapsible sections.
- Keep user-facing READMEs focused on requirements, installation, usage and removal.
  Omit session history, research/testing narratives and implementation rationale.
  Describe behavior directly, without explaining that examples are generic.
- Retain lifecycle consequences, especially what remains running after plugin
  removal. Put contributor commands in a Development section; avoid duplicating
  the CLI reference and storage details in the plugin README.
- Keep `portforward/README.md` plain Markdown for the plugin catalogue. Keep this
  file limited to durable project constraints and useful commands; remove obsolete
  rules instead of accumulating a session diary or duplicating tool configuration.

## Git

Preserve unrelated working-tree and staged changes. Use conventional commit
messages without agent attribution or added co-authors. Commit when requested;
do not push, rewrite history or delete branches/tags without explicit authorization.
