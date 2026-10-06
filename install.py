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

if sys.version_info < (3, 11):  # noqa: UP036 -- direct execution needs an actionable error.
    print("Python 3.11 or newer is required.", file=sys.stderr)
    sys.exit(1)

import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
HOME = Path.home()
CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", str(HOME / ".config")))
STATE = Path(os.environ.get("XDG_STATE_HOME", str(HOME / ".local/state")))
RECORD = STATE / "portforward-manager" / "installation.json"
PLUGIN = "ghillb/portforward"
SOURCE = "ssh-forward-manager"
WIDGET = f"{PLUGIN}:indicator"
sys.path.insert(0, str(ROOT / "portforward/backend"))
from portforward_manager import installation as backend  # noqa: E402


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


def rewrite_widget_definition(text: str, *, remove: bool = False) -> str:
    """Register the bar reference as a plugin instance, preserving other config."""
    expected = tomllib.loads(text)
    widgets = expected.get("widget", {})
    existing = widgets.get(WIDGET)
    if existing is not None and existing.get("type") != WIDGET:
        raise ValueError("The forwarding widget name is already used by another widget.")
    if remove:
        if existing is None:
            return text
        name = rf'(?:"{re.escape(WIDGET)}"|\'{re.escape(WIDGET)}\')'
        blocks = rf"(?ms)^\[widget\.{name}(?:\.[^\n]*)?\][ \t]*\n.*?(?=^\[|\Z)"
        changed = re.sub(blocks, "", text)
        del widgets[WIDGET]
        if not widgets:
            expected.pop("widget")
    else:
        if existing is not None:
            return text
        changed = (
            text.rstrip() + f"\n\n[widget.{json.dumps(WIDGET)}]\ntype = {json.dumps(WIDGET)}\n"
        )
        expected.setdefault("widget", {})[WIDGET] = {"type": WIDGET}
    if tomllib.loads(changed) != expected:
        raise ValueError("Refusing a widget declaration edit that changes unrelated settings.")
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
    for executable in ("ssh", "systemctl"):
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
        definition = local.get("widget", {}).get(WIDGET, settings.get("widget", {}).get(WIDGET))
        if definition is not None and definition.get("type") != WIDGET:
            raise ValueError("The forwarding widget name is already used by another widget.")
        owned_definition = record.get("desktop", {}).get("owned_definition", definition is None)
        if owned_definition:
            rewrite_widget_definition(current)
        directory = RECORD.parent / "installation-backups" / str(time.time_ns())
        backup(base, directory)
        backup(overlay, directory)
        desktop = {
            "config": str(target),
            "bar": bar,
            "owned_widget": owned,
            "owned_definition": owned_definition,
            "backup": str(directory),
        }
    backend.ensure(ROOT / "portforward/backend")
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
            current = rewrite_widget(current, desktop["bar"], [*items, WIDGET])
        if desktop["owned_definition"]:
            current = rewrite_widget_definition(current)
        if current != target.read_text():
            write(target, current)
        command("noctalia", "msg", "config-reload")
    print("Installed. Profiles start only when you select Connect.")


def remove() -> None:
    if not RECORD.exists():
        raise ValueError("No installation record found; refusing to remove unowned files.")
    record: dict[str, Any] = json.loads(RECORD.read_text())
    backend.stop_all()
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
        if desktop.get("owned_definition") and target.exists():
            write(target, rewrite_widget_definition(target.read_text(), remove=True))
        command("noctalia", "msg", "config-reload")
    backend.remove()
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
