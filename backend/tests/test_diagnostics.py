import subprocess
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError
from unittest.mock import Mock

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models.diagnostics import (
    DependencyDiagnostic,
    DependencyName,
    DependencyStatus,
    SystemDiagnostics,
)
from app.system.diagnostics import DependencyDiagnosticsService


def test_diagnostics_reports_compatible_dependencies() -> None:
    outputs = {
        "/tools/node": "v24.18.0",
        "/tools/ffmpeg": "ffmpeg version 8.1.2 Copyright",
        "/tools/ffprobe": "ffprobe version 8.1.2 Copyright",
    }
    received_arguments: list[Sequence[str]] = []

    def runner(arguments: Sequence[str]) -> str:
        received_arguments.append(arguments)
        return outputs[arguments[0]]

    service = DependencyDiagnosticsService(
        runner=runner,
        resolver=lambda command: f"/tools/{command}",
        node_binary="/tools/node",
    )

    result = service.inspect()

    assert result.ready is True
    assert [item.status for item in result.dependencies] == [
        DependencyStatus.AVAILABLE,
        DependencyStatus.AVAILABLE,
        DependencyStatus.AVAILABLE,
        DependencyStatus.AVAILABLE,
    ]
    assert result.dependencies[1].version == "24.18.0"
    assert result.dependencies[2].version == "8.1.2"
    assert received_arguments == [
        ["/tools/node", "--version"],
        ["/tools/ffmpeg", "-version"],
        ["/tools/ffprobe", "-version"],
    ]


def test_diagnostics_translates_missing_binary_to_stable_error() -> None:
    def failing_runner(arguments: Sequence[str]) -> str:
        if arguments[0] == "/missing/node":
            raise FileNotFoundError
        return "version 8.1.2"

    service = DependencyDiagnosticsService(
        runner=failing_runner,
        resolver=lambda command: f"/tools/{command}",
        node_binary="/missing/node",
    )

    result = service.inspect()
    node = result.dependencies[1]

    assert result.ready is False
    assert node.status is DependencyStatus.MISSING
    assert node.version is None
    assert node.error_code == "node_missing"


def test_diagnostics_translates_missing_yt_dlp_to_stable_error() -> None:
    def missing_package(_package: str) -> str:
        raise PackageNotFoundError

    service = DependencyDiagnosticsService(
        runner=lambda _arguments: "version 8.1.2",
        resolver=lambda command: f"/tools/{command}",
        package_version_resolver=missing_package,
        node_binary="/tools/node",
    )

    result = service.inspect()
    yt_dlp = result.dependencies[0]

    assert result.ready is False
    assert yt_dlp.status is DependencyStatus.MISSING
    assert yt_dlp.version is None
    assert yt_dlp.error_code == "yt_dlp_missing"


def test_diagnostics_rejects_incompatible_ffmpeg() -> None:
    def runner(arguments: Sequence[str]) -> str:
        if arguments[0].endswith("ffmpeg"):
            return "ffmpeg version 7.1.1"
        if arguments[0].endswith("node"):
            return "v24.18.0"
        return "ffprobe version 8.1.2"

    service = DependencyDiagnosticsService(
        runner=runner,
        resolver=lambda command: f"/tools/{command}",
        node_binary="/tools/node",
    )

    ffmpeg = service.inspect().dependencies[2]

    assert ffmpeg.status is DependencyStatus.INCOMPATIBLE
    assert ffmpeg.version == "7.1.1"
    assert ffmpeg.error_code == "ffmpeg_incompatible"


def test_diagnostics_handles_failed_version_command() -> None:
    def runner(arguments: Sequence[str]) -> str:
        if arguments[0].endswith("ffprobe"):
            raise subprocess.TimeoutExpired(arguments, timeout=5)
        return "version 24.0.0" if arguments[0].endswith("node") else "version 8.0"

    service = DependencyDiagnosticsService(
        runner=runner,
        resolver=lambda command: f"/tools/{command}",
        node_binary="/tools/node",
    )

    ffprobe = service.inspect().dependencies[3]

    assert ffprobe.status is DependencyStatus.MISSING
    assert ffprobe.error_code == "ffprobe_missing"


def test_diagnostics_endpoint_returns_startup_snapshot_without_paths() -> None:
    snapshot = SystemDiagnostics(
        ready=False,
        dependencies=[
            DependencyDiagnostic(
                name=DependencyName.NODE,
                status=DependencyStatus.MISSING,
                error_code="node_missing",
            )
        ],
    )
    service = Mock(spec=DependencyDiagnosticsService)
    service.inspect.return_value = snapshot

    with TestClient(
        create_app(Settings(environment="test"), diagnostics_service=service)
    ) as client:
        response = client.get("/api/system/diagnostics")
        health_response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "ready": False,
        "dependencies": [
            {
                "name": "node",
                "status": "missing",
                "version": None,
                "error_code": "node_missing",
            }
        ],
    }
    assert "/tools/" not in response.text
    assert health_response.json() == {
        "status": "ok",
        "service": "video-downloader-api",
    }
    service.inspect.assert_called_once_with()
