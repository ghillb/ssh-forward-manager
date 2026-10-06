import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from portforward_manager import installation, runner, tools


def test_missing_optional_tool_explains_the_affected_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tools, "REGISTRY", Path("/nonexistent/portforward-tools.json"))
    monkeypatch.setattr(tools.shutil, "which", lambda _: None)
    with pytest.raises(ValueError, match="wl-copy.*CLI clipboard"):
        tools.executable("wl-copy")


def test_no_user_manager_has_an_actionable_diagnostic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tools, "executable", lambda name: name)

    def run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if argv[0] == "ssh":
            return subprocess.CompletedProcess(argv, 0, "", "OpenSSH_9.2p1")
        return subprocess.CompletedProcess(argv, 1, "", "Failed to connect to bus")

    monkeypatch.setattr(tools.subprocess, "run", run)
    report = tools.doctor()
    assert not report["ok"]
    assert any("systemd user" in error for error in report["errors"])
    assert "Failed to connect to bus" not in json.dumps(report)


def test_restricted_proc_reports_inspection_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def denied(_: Path) -> str:
        raise PermissionError("restricted proc")

    monkeypatch.setattr(Path, "read_text", denied)
    with pytest.raises(ValueError, match="Cannot inspect.*loopback listeners"):
        runner.owns_listeners(os.getpid(), {3000})


@pytest.mark.parametrize("tools_available", [False, True])
def test_bootstrap_leaves_plugin_source_untouched(tmp_path: Path, tools_available: bool) -> None:
    plugin = tmp_path / "plugin"
    source = plugin / "backend"
    shutil.copytree(
        Path(__file__).parents[1] / "portforward",
        plugin,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.egg-info"),
    )
    before = {
        path.relative_to(plugin): (path.read_bytes() if path.is_file() else None)
        for path in plugin.rglob("*")
    }
    commands = tmp_path / "commands"
    if tools_available:
        commands.mkdir()
        ssh = shutil.which("ssh")
        assert ssh is not None
        (commands / "ssh").symlink_to(ssh)
        # Simulate an empty user manager; do not touch the desktop's services.
        manager = commands / "systemctl"
        manager.write_text("#!/bin/sh\nexit 0\n")
        manager.chmod(0o700)
    env = {
        **os.environ,
        "HOME": str(tmp_path / "home"),
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
        "XDG_DATA_HOME": str(tmp_path / "data"),
        "XDG_STATE_HOME": str(tmp_path / "state"),
        "XDG_RUNTIME_DIR": str(tmp_path / "runtime"),
        "PATH": str(commands),
    }
    result = subprocess.run(
        [sys.executable, "-I", str(source / "bootstrap.py")],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    after = {
        path.relative_to(plugin): (path.read_bytes() if path.is_file() else None)
        for path in plugin.rglob("*")
    }
    assert after == before
    assert not list(source.rglob("__pycache__"))
    assert not list(source.rglob("*.pyc"))
    if not tools_available:
        assert result.returncode == 1
        assert "Required command missing: ssh" in result.stderr
        return
    assert result.returncode == 0, result.stderr
    launcher = tmp_path / "home/.local/bin/portforward"
    assert json.loads(result.stdout)["cli"] == str(launcher)
    assert (tmp_path / "config/systemd/user/portforward@.service").is_file()
    installed = tmp_path / "data/portforward-manager/backend"
    assert (installed / "portforward_manager/cli.py").is_file()
    shutil.rmtree(plugin)
    cli = subprocess.run([str(launcher), "--help"], env=env, capture_output=True, text=True)
    assert cli.returncode == 0, cli.stderr
    assert "Named, loopback-only SSH forwards supervised by systemd." in cli.stdout
    assert list(installed.rglob("*.pyc"))


def test_bundle_survives_source_removal_and_a_minimal_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    original = Path(__file__).parents[1] / "portforward/backend"
    shutil.copytree(original, source, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    home = tmp_path / "home"
    monkeypatch.setattr(installation, "HOME", home)
    monkeypatch.setattr(installation, "TARGET", home / "data/portforward-manager/backend")
    monkeypatch.setattr(installation, "LAUNCHER", home / ".local/bin/portforward")
    monkeypatch.setattr(installation, "UNIT", home / "config/systemd/user/portforward@.service")
    monkeypatch.setattr(installation, "RECORD", home / "state/portforward-manager/backend.json")
    monkeypatch.setattr(installation, "command", lambda *args: "")
    monkeypatch.setattr(tools, "require_ready", lambda: {"ssh": shutil.which("ssh")})
    result = installation.ensure(source)
    assert result["cli"] == str(installation.LAUNCHER)
    assert installation.LAUNCHER.stat().st_mode & 0o777 == 0o700
    installed = installation.TARGET / "portforward_manager/cli.py"
    assert installed.exists()
    mtime = installed.stat().st_mtime_ns
    installation.ensure(source)
    assert installed.stat().st_mtime_ns == mtime
    shutil.rmtree(source)
    env = {
        **os.environ,
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(home / "config"),
        "XDG_STATE_HOME": str(home / "state"),
        "XDG_RUNTIME_DIR": str(home / "runtime"),
        "PATH": "/nonexistent",
        "PYTHONPATH": "",
    }
    subprocess.run(
        [
            str(installation.LAUNCHER),
            "add",
            "development",
            "--host",
            "devbox",
            "--map",
            "3000:localhost:8080",
        ],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    resolved = subprocess.run(
        [str(installation.LAUNCHER), "resolve", "localhost"],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(resolved.stdout)["hostname"] == "localhost"
    assert (
        json.loads((home / "config/portforward/profiles.json").read_text())["profiles"][0][
            "mappings"
        ][0]["local_port"]
        == 3000
    )
    assert str(Path(sys.executable).resolve()) in installation.LAUNCHER.read_text()


def test_unowned_launcher_is_never_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    launcher = tmp_path / "portforward"
    launcher.write_text("another program")
    monkeypatch.setattr(installation, "LAUNCHER", launcher)
    monkeypatch.setattr(installation, "RECORD", tmp_path / "missing.json")
    monkeypatch.setattr(tools, "require_ready", lambda: {})
    with pytest.raises(ValueError, match="already exists"):
        installation.ensure(Path(__file__).parents[1] / "portforward/backend")
    assert launcher.read_text() == "another program"


@pytest.fixture
def bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    source = tmp_path / "source"
    shutil.copytree(
        Path(__file__).parents[1] / "portforward/backend",
        source,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    monkeypatch.setattr(installation, "TARGET", tmp_path / "data/backend")
    monkeypatch.setattr(installation, "LAUNCHER", tmp_path / "bin/portforward")
    monkeypatch.setattr(installation, "UNIT", tmp_path / "config/portforward@.service")
    monkeypatch.setattr(installation, "RECORD", tmp_path / "state/backend.json")
    monkeypatch.setattr(installation, "command", lambda *args: "")
    monkeypatch.setattr(tools, "require_ready", lambda: {})
    installation.ensure(source)
    return source


def test_update_waits_for_disconnect_without_changing_running_backend(
    bundle: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    installed = installation.TARGET / "entry.py"
    before = installed.read_bytes()
    (bundle / "entry.py").write_text((bundle / "entry.py").read_text() + "\n# Updated release.\n")
    monkeypatch.setattr(installation, "command", lambda *args: "portforward@test.service active")
    pending = installation.ensure(bundle)
    assert "Disconnect" in pending["warning"]
    assert installed.read_bytes() == before
    monkeypatch.setattr(installation, "command", lambda *args: "")
    assert "warning" not in installation.ensure(bundle)
    assert installed.read_bytes() != before


def test_session_path_changes_do_not_trigger_a_backend_update(
    bundle: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = installation.RECORD.read_bytes()
    monkeypatch.setenv("PATH", "/another/session/path")
    result = installation.ensure(bundle)
    assert "warning" not in result
    assert installation.RECORD.read_bytes() == before


def test_failed_update_rolls_back_backend_launcher_unit_and_record(
    bundle: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    files = [
        installation.TARGET / "entry.py",
        installation.LAUNCHER,
        installation.UNIT,
        installation.RECORD,
    ]
    originals = {path: path.read_bytes() for path in files}
    (bundle / "entry.py").write_text((bundle / "entry.py").read_text() + "\n# Updated release.\n")

    def fail_reload(*args: str) -> str:
        if args == ("daemon-reload",):
            raise ValueError("reload failed")
        return ""

    monkeypatch.setattr(installation, "command", fail_reload)
    with pytest.raises(ValueError, match="reload failed"):
        installation.ensure(bundle)
    assert {path: path.read_bytes() for path in files} == originals


def test_backend_removal_stops_owned_units_and_retains_profiles(
    bundle: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    profiles = tmp_path / "profiles.json"
    profiles.write_text('{"version": 1, "profiles": []}')
    events: list[tuple[str, ...]] = []

    def record(*args: str) -> str:
        events.append(args)
        if args[0] == "list-units":
            return "portforward@test.service loaded active running\n"
        return ""

    monkeypatch.setattr(installation, "command", record)
    installation.remove()
    assert ("stop", "portforward@test.service") in events
    assert not installation.TARGET.exists()
    assert not installation.UNIT.exists() and not installation.LAUNCHER.exists()
    assert profiles.read_text() == '{"version": 1, "profiles": []}'
