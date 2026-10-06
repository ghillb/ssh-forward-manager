import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from portforward_manager import model, runner, supervisor


@pytest.mark.parametrize(
    ("message", "exit_code", "phase"),
    [
        ("Permission denied (publickey).", 78, "error"),
        ("Host key verification failed.", 78, "error"),
        ("Connection timed out", 1, "reconnecting"),
        ("Connection reset by peer", 1, "reconnecting"),
    ],
)
def test_transport_errors_publish_actionable_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, message: str, exit_code: int, phase: str
) -> None:
    with socket.socket() as free:
        free.bind(("127.0.0.1", 0))
        local_port = free.getsockname()[1]
    profile = model.validate(
        {
            "id": "test",
            "name": "Test",
            "host": "devbox",
            "mappings": [
                {
                    "local_port": local_port,
                    "remote_host": "localhost",
                    "remote_port": 8080,
                    "scheme": "http",
                }
            ],
        }
    )
    destination = tmp_path / "state/test.json"
    monkeypatch.setattr(runner, "RUNTIME", tmp_path / "runtime")
    monkeypatch.setattr(runner, "load", lambda: {"test": profile})
    monkeypatch.setattr(runner, "state_file", lambda _: destination)
    monkeypatch.setattr(runner.signal, "signal", lambda *args: None)
    notifications = []
    monkeypatch.setattr(runner, "notify", notifications.append)
    code = "import sys; print(sys.argv[1], file=sys.stderr); sys.exit(255)"
    monkeypatch.setattr(runner, "master_argv", lambda *args: [sys.executable, "-c", code, message])
    assert runner.run("test") == exit_code
    state = json.loads(destination.read_text())
    assert state["state"] == phase
    assert message in state["error"]
    assert "READY=1" not in notifications
    assert not (tmp_path / "runtime/test.sock").exists()


def test_readiness_requires_ssh_owned_loopback_listeners() -> None:
    with socket.socket() as own, socket.socket() as other:
        own.bind(("127.0.0.1", 0))
        own.listen()
        other.bind(("127.0.0.1", 0))
        missing = other.getsockname()[1]
        other.close()
        assert runner.owns_listeners(os.getpid(), {own.getsockname()[1]})
        assert not runner.owns_listeners(os.getpid(), {own.getsockname()[1], missing})


def test_agent_is_private_and_does_not_modify_global_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(supervisor, "RUNTIME", tmp_path)
    monkeypatch.setenv("SSH_AUTH_SOCK", '/run/user/1000/agent with "quotes"')
    supervisor.agent_environment("test")
    path = tmp_path / "agent-test.env"
    assert path.stat().st_mode & 0o777 == 0o600
    assert '\\"quotes\\"' in path.read_text()
    monkeypatch.delenv("SSH_AUTH_SOCK")
    supervisor.agent_environment("test")
    assert not path.exists()


def test_control_socket_timeout_requests_reconnection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile = model.validate(
        {
            "id": "test",
            "name": "Test",
            "host": "devbox",
            "mappings": [
                {
                    "local_port": 3000,
                    "remote_host": "localhost",
                    "remote_port": 8080,
                    "scheme": "http",
                }
            ],
        }
    )
    destination = tmp_path / "state.json"
    monkeypatch.setattr(runner, "RUNTIME", tmp_path)
    monkeypatch.setattr(runner, "load", lambda: {"test": profile})
    monkeypatch.setattr(runner, "state_file", lambda _: destination)
    monkeypatch.setattr(runner.signal, "signal", lambda *args: None)
    monkeypatch.setattr(runner, "check_ports", lambda _: None)
    monkeypatch.setattr(runner, "notify", lambda _: None)
    code = "import pathlib,sys,time; pathlib.Path(sys.argv[1]).touch(); time.sleep(10)"
    monkeypatch.setattr(
        runner, "master_argv", lambda p, path: [sys.executable, "-c", code, str(path)]
    )

    def timeout(argv: list[str], **kwargs: Any) -> None:
        raise subprocess.TimeoutExpired(argv, 3)

    monkeypatch.setattr(runner.subprocess, "run", timeout)
    assert runner.run("test") == 1
    assert json.loads(destination.read_text())["state"] == "reconnecting"
