Manage named SSH tunnels from Noctalia or the standalone CLI.

- Profiles support multiple fixed, loopback-bound ports and browser/copy actions.
- Systemd keeps tunnels alive across bar restarts and reconnects after interruptions.
- The plugin bundles its backend; enabling it installs the CLI without pip or uv.
- Catalogue-ready packaging and installation fixes preserve existing bar layouts.

Requires Python 3.11+, OpenSSH 8.7+, systemd user services and Noctalia plugin API 24+.
Connections start manually; boot autoconnect is not supported.
