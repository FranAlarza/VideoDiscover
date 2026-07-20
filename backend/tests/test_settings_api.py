from pathlib import Path
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.config import Settings
from app.database.settings_repository import LocalSettings
from app.main import create_app
from app.system.download_directory import DownloadDirectoryError


def test_settings_api_gets_and_updates_download_directory(tmp_path: Path) -> None:
    service = AsyncMock()
    initial = tmp_path / "downloads"
    selected = tmp_path / "selected"
    service.get.return_value = LocalSettings(initial)
    service.update_download_output_root.return_value = LocalSettings(selected)

    with TestClient(
        create_app(
            Settings(environment="test"),
            local_settings_service=service,
        )
    ) as client:
        current = client.get("/api/settings")
        updated = client.put(
            "/api/settings/download-directory", json={"path": str(selected)}
        )

    assert current.status_code == 200
    assert current.json() == {"download_output_root": str(initial)}
    assert updated.status_code == 200
    assert updated.json() == {"download_output_root": str(selected)}
    service.update_download_output_root.assert_awaited_once_with(str(selected))


def test_settings_api_preserves_stable_directory_errors(tmp_path: Path) -> None:
    service = AsyncMock()
    service.get.return_value = LocalSettings(tmp_path / "downloads")
    service.update_download_output_root.side_effect = DownloadDirectoryError(
        "download_directory_change_blocked",
        "Espera a que terminen las descargas.",
        status_code=409,
    )

    with TestClient(
        create_app(
            Settings(environment="test"),
            local_settings_service=service,
        )
    ) as client:
        response = client.put(
            "/api/settings/download-directory", json={"path": str(tmp_path)}
        )

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "download_directory_change_blocked",
            "message": "Espera a que terminen las descargas.",
        }
    }


def test_settings_api_reports_unavailable_service() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        response = client.get("/api/settings")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "settings_unavailable"
