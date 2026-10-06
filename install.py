"""Install or remove this checkout without replacing desktop configuration."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
HOME = Path.home()
CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", str(HOME / ".config")))
STATE = Path(os.environ.get("XDG_STATE_HOME", str(HOME / ".local/state")))
RECORD = STATE / "portforward-manager" / "installation.json"
UNIT = CONFIG / "systemd/user/portforward@.service"
PLUGIN = "ghillb/portforward"
SOURCE = "ssh-forward-manager"
WIDGET = f"{PLUGIN}:indicator"


def command(*argv: str, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(argv, capture_output=True, text=True, check=True, env=env)
    return result.stdout


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".portforward-new")
    try:
        temporary.write_text(content)
        temporary.chmod(path.stat().st_mode & 0o777 if path.exists() else 0o600)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def rewrite_widget(text: str, bar: str, items: list[str]) -> str:
    """Change one array, retaining every other byte and TOML comment."""
    if not re.fullmatch(r"[A-Za-z0-9_-]+", bar):
        raise ValueError("Add the widget manually for bar names containing special characters.")
    heading = f"[bar.{bar}]"
    block = re.search(r"(?ms)^" + re.escape(heading) + r"\s*\n(.*?)(?=^\[|\Z)", text)
    assignment = "end = " + json.dumps(items, ensure_ascii=False)
    if block is None:
        changed = text.rstrip() + f"\n\n{heading}\n{assignment}\n"
    else:
        body = block.group(1)
        existing = re.search(r"(?ms)^end\s*=\s*\[[^\]]*\]", body)
        if existing:
            body = body[: existing.start()] + assignment + body[existing.end() :]
        else:
            body = assignment + "\n" + body
        changed = text[: block.start(1)] + body + text[block.end(1) :]
    # Parsing before and after also prevents a partial or malformed edit.
    before = tomllib.loads(text)
    after = tomllib.loads(changed)
    expected: dict[str, Any] = before
    expected.setdefault("bar", {}).setdefault(bar, {})["end"] = items
    if after != expected:
        raise ValueError("Refusing a bar edit that changes unrelated settings.")
    return changed


def backup(path: Path, directory: Path) -> None:
    if path.exists():
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        target = directory / path.name
        if not target.exists():
            shutil.copy2(path, target)
            target.chmod(0o600)


def wait_export(predicate: Callable[[dict[str, Any]], bool]) -> None:
    overlay = STATE / "noctalia/settings.toml"
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if overlay.exists() and predicate(tomllib.loads(overlay.read_text())):
            return
        time.sleep(0.05)
    raise ValueError("Noctalia did not persist its plugin settings. Retry installation.")


def install(cli_only: bool) -> None:
    for executable in ("uv", "ssh", "systemctl"):
        if not shutil.which(executable):
            raise ValueError(f"Required command missing: {executable}")
    active = command(
        "systemctl",
        "--user",
        "list-units",
        "portforward@*.service",
        "--state=active,activating",
        "--no-legend",
        "--plain",
    )
    if active.strip():
        raise ValueError("Disconnect forwarding profiles before installing or upgrading.")
    record: dict[str, Any] = json.loads(RECORD.read_text()) if RECORD.exists() else {}
    desktop: dict[str, Any] | None = None
    bars: dict[str, Any] = {}
    if not cli_only:
        if not shutil.which("noctalia"):
            raise ValueError("Noctalia is missing. Use --cli-only for a standalone installation.")
        command("noctalia", "plugins", "lint", str(ROOT / "portforward"))
        base = CONFIG / "noctalia/config.toml"
        overlay = STATE / "noctalia/settings.toml"
        settings = tomllib.loads(base.read_text())
        bars = settings.get("bar", {})
        if not bars:
            raise ValueError("Configure a Noctalia bar before installing the widget.")
        bar = next(iter(bars))
        target = overlay
        current = target.read_text() if target.exists() else ""
        local = tomllib.loads(current)
        items: list[str] = local.get("bar", {}).get(bar, {}).get("end", bars[bar].get("end", []))
        owned = record.get("desktop", {}).get("owned_widget", WIDGET not in items)
        if WIDGET not in items:
            items = [*items, WIDGET]
        rewrite_widget(current, bar, items)
        directory = RECORD.parent / "installation-backups" / str(time.time_ns())
        backup(base, directory)
        backup(overlay, directory)
        desktop = {
            "config": str(target),
            "bar": bar,
            "owned_widget": owned,
            "backup": str(directory),
        }
    env = {**os.environ, "UV_TOOL_BIN_DIR": str(HOME / ".local/bin")}
    command("uv", "tool", "install", "--force", str(ROOT), env=env)
    write(UNIT, (ROOT / "systemd/portforward@.service").read_text())
    command("systemctl", "--user", "daemon-reload")
    record["checkout"] = str(ROOT)
    if desktop:
        record["desktop"] = desktop
    # Record ownership before desktop mutations so partial installs can be removed.
    write(RECORD, json.dumps(record, indent=2) + "\n")
    if desktop:
        sources = command("noctalia", "msg", "plugins", "source", "list")
        if not any(line.startswith(SOURCE + " ") for line in sources.splitlines()):
            command("noctalia", "msg", "plugins", "source", "add", SOURCE, "path", str(ROOT))
            wait_export(
                lambda value: any(
                    s.get("name") == SOURCE for s in value.get("plugins", {}).get("source", [])
                )
            )
        command("noctalia", "msg", "plugins", "enable", PLUGIN)
        wait_export(lambda value: PLUGIN in value.get("plugins", {}).get("enabled", []))
        target = Path(desktop["config"])
        current = target.read_text()
        parsed = tomllib.loads(current)
        items = parsed.get("bar", {}).get(desktop["bar"], {}).get("end", [])
        if WIDGET not in items:
            if not items:
                items = bars[desktop["bar"]].get("end", [])
            write(target, rewrite_widget(current, desktop["bar"], [*items, WIDGET]))
        command("noctalia", "msg", "config-reload")
    print("Installed. Profiles start only when you select Connect.")


def remove() -> None:
    if not RECORD.exists():
        raise ValueError("No installation record found; refusing to remove unowned files.")
    record: dict[str, Any] = json.loads(RECORD.read_text())
    units = command(
        "systemctl",
        "--user",
        "list-units",
        "portforward@*.service",
        "--all",
        "--no-legend",
        "--plain",
    )
    for line in units.splitlines():
        fields = line.lstrip("● ").split()
        name = fields[0]
        command("systemctl", "--user", "stop", name)
        if "failed" in fields[1:4]:
            command("systemctl", "--user", "reset-failed", name)
    desktop = record.get("desktop")
    if desktop:
        target = Path(desktop["config"])
        command("noctalia", "msg", "plugins", "disable", PLUGIN)
        wait_export(lambda value: PLUGIN not in value.get("plugins", {}).get("enabled", []))
        command("noctalia", "msg", "plugins", "source", "remove", SOURCE)
        wait_export(
            lambda value: all(
                s.get("name") != SOURCE for s in value.get("plugins", {}).get("source", [])
            )
        )
        if desktop["owned_widget"] and target.exists():
            text = target.read_text()
            items = tomllib.loads(text).get("bar", {}).get(desktop["bar"], {}).get("end", [])
            write(target, rewrite_widget(text, desktop["bar"], [x for x in items if x != WIDGET]))
        command("noctalia", "msg", "config-reload")
    UNIT.unlink(missing_ok=True)
    command("systemctl", "--user", "daemon-reload")
    command("uv", "tool", "uninstall", "ssh-forward-manager")
    RECORD.unlink()
    print("Removed. Saved profiles and configuration backups were retained.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    options = parser.add_mutually_exclusive_group()
    options.add_argument("--cli-only", action="store_true")
    options.add_argument("--remove", action="store_true")
    args = parser.parse_args()
    try:
        remove() if args.remove else install(args.cli_only)
        return 0
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        detail = error.stderr if isinstance(error, subprocess.CalledProcessError) else str(error)
        print(detail or str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
