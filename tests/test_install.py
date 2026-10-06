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
    monkeypatch.setattr(installer.backend, "HOME", tmp_path / "home")
    monkeypatch.setattr(installer.backend, "TARGET", tmp_path / "data/backend")
    monkeypatch.setattr(installer.backend, "LAUNCHER", tmp_path / "home/.local/bin/portforward")
    monkeypatch.setattr(installer.backend, "UNIT", config / "systemd/user/portforward@.service")
    monkeypatch.setattr(installer.backend, "RECORD", state / "portforward-manager/backend.json")
    monkeypatch.setattr(installer.backend.tools, "require_ready", lambda: {})
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
    monkeypatch.setattr(
        installer.backend, "command", lambda *args: command("systemctl", "--user", *args)
    )
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


@pytest.mark.parametrize("placement", ["start", "center", "capsule", "base_capsule"])
@pytest.mark.parametrize("owned", [False, True])
def test_reinstall_preserves_a_moved_widget_and_removes_only_owned_placements(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, placement: str, owned: bool
) -> None:
    config = tmp_path / "config"
    state = tmp_path / "state"
    base = config / "noctalia/config.toml"
    overlay = state / "noctalia/settings.toml"
    base.parent.mkdir(parents=True)
    overlay.parent.mkdir(parents=True)
    layout = '[bar.main]\nend = ["tray"]\n'
    if "capsule" in placement:
        layout = '[bar.main]\nend = ["tray", "group:utilities"]\n'
        layout += '\n[[bar.main.capsule_group]]\nid = "utilities"\nradius = 4\n'
        layout += f'members = ["bluetooth", "{installer.WIDGET}", "network"]\n'
    else:
        layout += f'{placement} = ["clock", "{installer.WIDGET}"]\n'
    base.write_text(layout if placement == "base_capsule" else '[bar.main]\nend = ["tray"]\n')
    content = "" if placement == "base_capsule" else layout
    content += f"\n[plugins]\nenabled = {json.dumps([installer.PLUGIN])}\n"
    content += f'\n[widget."{installer.WIDGET}"]\ntype = "{installer.WIDGET}"\n'
    overlay.write_text(content)
    before = tomllib.loads(content)
    record = state / "portforward-manager/installation.json"
    if owned:
        record.parent.mkdir(parents=True)
        record.write_text(
            json.dumps({"desktop": {"owned_widget": True, "owned_definition": False}})
        )
    monkeypatch.setattr(installer, "CONFIG", config)
    monkeypatch.setattr(installer, "STATE", state)
    monkeypatch.setattr(installer, "RECORD", record)
    monkeypatch.setattr(installer.shutil, "which", lambda name: name)
    monkeypatch.setattr(installer.backend, "ensure", lambda _: {})
    monkeypatch.setattr(installer.backend, "stop_all", lambda: None)
    monkeypatch.setattr(installer.backend, "remove", lambda: None)

    def command(*args: str, **kwargs: Any) -> str:
        if args == ("noctalia", "msg", "plugins", "source", "list"):
            return f"{installer.SOURCE} path {installer.ROOT}\n"
        if args == ("noctalia", "msg", "plugins", "disable", installer.PLUGIN):
            overlay.write_text(
                overlay.read_text().replace(
                    f"enabled = {json.dumps([installer.PLUGIN])}", "enabled = []"
                )
            )
        return ""

    monkeypatch.setattr(installer, "command", command)
    installer.install(False)
    installer.install(False)
    installed = tomllib.loads(overlay.read_text())
    assert installed == before
    assert json.loads(record.read_text())["desktop"]["owned_widget"] is owned
    if placement != "base_capsule":
        installer.remove()
        removed_bar = tomllib.loads(overlay.read_text())["bar"]["main"]
        expected = tomllib.loads(layout)["bar"]["main"]
        if owned:
            if placement == "capsule":
                expected["capsule_group"][0]["members"] = ["bluetooth", "network"]
            else:
                expected[placement] = ["clock"]
        assert removed_bar == expected


def test_moved_widget_removal_preserves_other_bars_and_group_style() -> None:
    original = f'''# Keep this comment.
[bar.main]
start = ["{installer.WIDGET}", "workspaces"]
end = ["group:utilities"]
    [[bar.main.capsule_group]]
    id = "utilities"
    members = ["network", "{installer.WIDGET}", "volume"]
    radius = 4
[bar.other]
end = ["{installer.WIDGET}"]
[widget.clock]
format = "%H:%M"
'''
    changed = installer.remove_widget(original, "main")
    parsed = tomllib.loads(changed)
    assert parsed["bar"]["main"]["start"] == ["workspaces"]
    assert parsed["bar"]["main"]["end"] == ["group:utilities"]
    assert parsed["bar"]["main"]["capsule_group"] == [
        {"id": "utilities", "members": ["network", "volume"], "radius": 4}
    ]
    assert parsed["bar"]["other"] == {"end": [installer.WIDGET]}
    assert changed.startswith("# Keep this comment.")
    assert changed.endswith('[widget.clock]\nformat = "%H:%M"\n')


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
    target = tmp_path / "backend"
    target.mkdir()
    backend_record = tmp_path / "backend.json"
    backend_record.write_text(json.dumps({"target": str(target)}))
    monkeypatch.setattr(installer.backend, "RECORD", backend_record)
    monkeypatch.setattr(installer.backend, "UNIT", unit)
    monkeypatch.setattr(installer.backend, "TARGET", target)
    monkeypatch.setattr(installer.backend, "LAUNCHER", tmp_path / "portforward")
    events = []

    def command(*args: str, **kwargs: Any) -> str:
        events.append(args)
        if "list-units" in args:
            return "portforward@test.service loaded active running SSH forwarding profile test\n"
        if "reset-failed" in args:
            raise ValueError("Unit not loaded")
        return ""

    monkeypatch.setattr(installer, "command", command)
    monkeypatch.setattr(
        installer.backend, "command", lambda *args: command("systemctl", "--user", *args)
    )
    installer.remove()
    assert ("systemctl", "--user", "stop", "portforward@test.service") in events
    assert not unit.exists() and not record.exists()
    assert profiles.exists()
