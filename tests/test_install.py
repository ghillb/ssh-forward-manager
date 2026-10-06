import importlib.util
import json
import threading
import tomllib
from pathlib import Path
from typing import Any

import pytest

spec = importlib.util.spec_from_file_location("installer", Path(__file__).parents[1] / "install.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


def test_widget_edit_preserves_unrelated_settings_and_comments() -> None:
    original = """# Keep this comment.
[bar.main]
end = [
  "tray", # Keep this widget.
  "group:utilities",
]
start = ["workspaces"]
radius = 4

    [[bar.main.capsule_group]]
    id = "utilities"
    members = ["volume", "battery"]

[plugins]
enabled = ["example/existing"]
"""
    changed = installer.rewrite_widget(
        original, "main", ["tray", "group:utilities", installer.WIDGET]
    )
    before = tomllib.loads(original)
    after = tomllib.loads(changed)
    assert after["plugins"] == before["plugins"]
    assert after["bar"]["main"]["capsule_group"] == before["bar"]["main"]["capsule_group"]
    assert after["bar"]["main"]["start"] == ["workspaces"]
    assert changed.startswith("# Keep this comment.")
    removed = installer.rewrite_widget(changed, "main", ["tray", "group:utilities"])
    assert tomllib.loads(removed) == before


def test_widget_overlay_can_be_added_without_copying_base_settings() -> None:
    original = '[plugins]\nenabled = ["example/existing"]\n'
    changed = installer.rewrite_widget(original, "main", ["tray", installer.WIDGET])
    assert tomllib.loads(changed) == {
        "plugins": {"enabled": ["example/existing"]},
        "bar": {"main": {"end": ["tray", installer.WIDGET]}},
    }


def test_malformed_config_is_not_written(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    original = "[bar.main]\nend = [\n"
    path.write_text(original)
    with pytest.raises(tomllib.TOMLDecodeError):
        installer.rewrite_widget(original, "main", [installer.WIDGET])
    assert path.read_text() == original


@pytest.mark.parametrize("quote", ['"', "'"])
def test_widget_definition_preserves_existing_settings_and_removes_owned_blocks(quote: str) -> None:
    original = '# Keep this comment.\n[widget.clock]\nformat = "%H:%M"\n'
    registered = installer.rewrite_widget_definition(original)
    assert tomllib.loads(registered)["widget"][installer.WIDGET]["type"] == installer.WIDGET
    assert installer.rewrite_widget_definition(registered) == registered
    customized = registered.replace(f'"{installer.WIDGET}"', f"{quote}{installer.WIDGET}{quote}")
    customized += f'\n[widget.{quote}{installer.WIDGET}{quote}.actions]\nright = "none"\n'
    customized += '\n[theme]\nmode = "dark"\n'
    assert installer.rewrite_widget_definition(customized) == customized
    removed = installer.rewrite_widget_definition(customized, remove=True)
    assert tomllib.loads(removed) == {**tomllib.loads(original), "theme": {"mode": "dark"}}
    assert removed.startswith("# Keep this comment.")


def test_widget_definition_refuses_to_overwrite_another_widget() -> None:
    original = f'[widget."{installer.WIDGET}"]\ntype = "clock"\n'
    with pytest.raises(ValueError, match="already used"):
        installer.rewrite_widget_definition(original)


@pytest.mark.parametrize("existing_definition", [False, True])
def test_install_waits_for_noctalia_export_before_reloading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, existing_definition: bool
) -> None:
    config = tmp_path / "config"
    state = tmp_path / "state"
    base = config / "noctalia/config.toml"
    overlay = state / "noctalia/settings.toml"
    base.parent.mkdir(parents=True)
    overlay.parent.mkdir(parents=True)
    base.write_text('[bar.main]\nend = ["tray"]\n')
    content = '[bar.main]\nend = ["tray"]\n[plugins]\nenabled = []\n'
    content += '\n[widget.clock]\nformat = "%H:%M"\n'
    if existing_definition:
        content += f'\n[widget."{installer.WIDGET}"]\ntype = "{installer.WIDGET}"\n'
    overlay.write_text(content)
    original_widgets = tomllib.loads(content)["widget"]
    record = state / "portforward-manager/installation.json"
    monkeypatch.setattr(installer, "CONFIG", config)
    monkeypatch.setattr(installer, "STATE", state)
    monkeypatch.setattr(installer, "RECORD", record)
    monkeypatch.setattr(installer, "UNIT", config / "systemd/user/portforward@.service")
    monkeypatch.setattr(installer.shutil, "which", lambda name: name)
    exports = []

    def command(*args: str, **kwargs: Any) -> str:
        if args == ("noctalia", "msg", "plugins", "source", "list"):
            return f"{installer.SOURCE} path {installer.ROOT}\n"
        if args == ("noctalia", "msg", "plugins", "enable", installer.PLUGIN):
            content = overlay.read_text()
            timer = threading.Timer(
                0.05,
                lambda: overlay.write_text(
                    content.replace("enabled = []", f"enabled = {json.dumps([installer.PLUGIN])}")
                ),
            )
            exports.append(timer)
            timer.start()
        if args == ("noctalia", "msg", "config-reload"):
            settings = tomllib.loads(overlay.read_text())
            if installer.PLUGIN in settings["plugins"]["enabled"]:
                assert settings["widget"][installer.WIDGET]["type"] == installer.WIDGET
        if args == ("noctalia", "msg", "plugins", "disable", installer.PLUGIN):
            overlay.write_text(
                overlay.read_text().replace(
                    f"enabled = {json.dumps([installer.PLUGIN])}", "enabled = []"
                )
            )
        return ""

    monkeypatch.setattr(installer, "command", command)
    try:
        installer.install(False)
    finally:
        for timer in exports:
            timer.join()
    settings = tomllib.loads(overlay.read_text())
    assert installer.PLUGIN in settings["plugins"]["enabled"]
    assert settings["bar"]["main"]["end"] == ["tray", installer.WIDGET]
    assert settings["widget"][installer.WIDGET]["type"] == installer.WIDGET
    assert json.loads(record.read_text())["desktop"]["owned_definition"] is not existing_definition
    installer.install(False)
    for timer in exports:
        timer.join()
    assert tomllib.loads(overlay.read_text())["bar"]["main"]["end"].count(installer.WIDGET) == 1
    installer.remove()
    removed = tomllib.loads(overlay.read_text())
    assert removed["bar"]["main"]["end"] == ["tray"]
    assert removed["widget"] == original_widgets


def test_removal_handles_a_service_unloading_after_stop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    record = tmp_path / "installation.json"
    record.write_text("{}")
    unit = tmp_path / "portforward@.service"
    unit.write_text("[Service]\n")
    profiles = tmp_path / "profiles.json"
    profiles.write_text('{"version": 1, "profiles": []}')
    monkeypatch.setattr(installer, "RECORD", record)
    monkeypatch.setattr(installer, "UNIT", unit)
    events = []

    def command(*args: str, **kwargs: Any) -> str:
        events.append(args)
        if "list-units" in args:
            return "portforward@test.service loaded active running SSH forwarding profile test\n"
        if "reset-failed" in args:
            raise ValueError("Unit not loaded")
        return ""

    monkeypatch.setattr(installer, "command", command)
    installer.remove()
    assert ("systemctl", "--user", "stop", "portforward@test.service") in events
    assert not unit.exists() and not record.exists()
    assert profiles.exists()
