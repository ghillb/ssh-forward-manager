import os
import socket
from pathlib import Path

from portforward_manager import diagnostics


def test_live_listener_owner_is_identified_without_process_arguments() -> None:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        result = diagnostics.conflicts({port})
        assert result == [
            {"port": port, "processes": [Path(f"/proc/{os.getpid()}/comm").read_text().strip()]}
        ]
        listener.close()
        assert diagnostics.conflicts({port}) == []


def test_hidden_listener_owner_still_reports_port(tmp_path: Path) -> None:
    (tmp_path / "net").mkdir()
    (tmp_path / "net/tcp").write_text("header\n0: 0100007F:0BB8 00000000:0000 0A 0 0 0 0 0 123\n")
    assert diagnostics.conflicts({3000}, tmp_path) == [{"port": 3000, "processes": []}]
