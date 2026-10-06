import json
import socket
from pathlib import Path
from typing import Any

import pytest

from portforward_manager import cli, model, supervisor


@pytest.fixture
def profile() -> model.Profile:
    return model.validate(
        {
            "id": "development",
            "name": "Development",
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


@pytest.mark.parametrize(
    "host",
    [
        "-oProxyCommand=bad",
        "devbox;whoami",
        "user name@host",
        "[::1",
        "::1]",
        "localhost\n",
        "::1%$(id)",
        "::1% bad",
    ],
)
def test_rejects_unsafe_or_malformed_hosts(host: str) -> None:
    with pytest.raises(ValueError):
        model.valid_host(host, destination=True)


def test_ports_remain_fixed_and_conflict_is_reported(profile: model.Profile) -> None:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        configured = listener.getsockname()[1]
        profile["mappings"][0]["local_port"] = configured
        with pytest.raises(ValueError, match=f"local port {configured}"):
            model.check_ports(profile)
        assert profile["mappings"][0]["local_port"] == configured


def test_storage_is_private_and_invalid_save_is_atomic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile: model.Profile
) -> None:
    path = tmp_path / "config" / "profiles.json"
    monkeypatch.setattr(model, "PROFILES", path)
    model.save({profile["id"]: profile})
    original = path.read_bytes()
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.parent.stat().st_mode & 0o777 == 0o700
    assert model.load() == {profile["id"]: profile}
    with pytest.raises(TypeError):
        model.atomic_json(path, {"invalid": object()})
    assert path.read_bytes() == original
    assert list(path.parent.glob(".write-*")) == []


def test_profile_validation_rejects_duplicate_ports_and_passwords(profile: model.Profile) -> None:
    profile["mappings"].append(profile["mappings"][0].copy())
    with pytest.raises(ValueError, match="unique"):
        model.validate(profile)
    profile["mappings"].pop()
    with pytest.raises(ValueError, match="only"):
        model.validate({**profile, "password": "must-not-be-stored"})


def test_active_service_with_stale_readiness_is_connecting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile: model.Profile
) -> None:
    monkeypatch.setattr(supervisor, "STATE", tmp_path)
    model.atomic_json(
        tmp_path / "development.json",
        {
            "state": "connected",
            "pid": 111,
            "error": "",
        },
    )
    monkeypatch.setattr(
        supervisor,
        "properties",
        lambda _: {
            supervisor.unit("development"): {"ActiveState": "active", "MainPID": "222"},
        },
    )
    result = supervisor.status({profile["id"]: profile})["profiles"][0]
    assert result["state"] == "connecting"


def test_create_stays_disconnected_and_live_edit_restarts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile: model.Profile
) -> None:
    monkeypatch.setattr(model, "PROFILES", tmp_path / "profiles.json")
    monkeypatch.setattr(supervisor, "STATE", tmp_path)
    events = []
    monkeypatch.setattr(cli, "control", lambda *args: events.append(args))
    monkeypatch.setattr(cli, "connect", lambda p: events.append(("connect", p["id"])))
    monkeypatch.setattr(cli, "running", lambda _: True)
    profiles = {}
    cli.put(profiles, profile)
    assert events == []
    updated = model.validate(json.loads(json.dumps(profile)))
    updated["mappings"][0]["remote_port"] = 9090
    cli.put(profiles, updated)
    assert events == [("stop", profile["id"]), ("connect", profile["id"])]
    assert model.load()[profile["id"]]["mappings"][0]["remote_port"] == 9090


def test_first_connect_does_not_reset_an_unloaded_unit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile: model.Profile
) -> None:
    monkeypatch.setattr(supervisor, "RUNTIME", tmp_path)
    monkeypatch.setattr(supervisor, "running", lambda _: False)
    monkeypatch.setattr(supervisor, "check_ports", lambda _: None)
    monkeypatch.setattr(supervisor, "agent_environment", lambda _: None)
    events = []

    def control(action: str, profile_id: str, **kwargs: Any) -> None:
        if action == "reset-failed":
            raise ValueError("Unit not loaded")
        events.append((action, profile_id, kwargs))

    monkeypatch.setattr(supervisor, "control", control)
    supervisor.connect(profile)
    assert events == [("start", profile["id"], {"asynchronous": True})]
