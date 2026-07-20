from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.config import Settings
from app.downloader.repository import InMemoryDownloadRepository
from app.downloader.service import DownloadTaskService
from app.main import create_app
from app.models.inspection import MediaInspectionResponse
from app.models.media import Platform, ValidatedMediaUrl


def _service() -> DownloadTaskService:
    validator = AsyncMock()
    validator.validate.return_value = ValidatedMediaUrl(
        platform=Platform.YOUTUBE,
        media_id="dQw4w9WgXcQ",
        canonical_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    )
    inspection = AsyncMock()
    inspection.inspect_validated.return_value = MediaInspectionResponse(
        platform=Platform.YOUTUBE,
        media_id="dQw4w9WgXcQ",
        title="Example",
        video_qualities=[1080, 720],
        audio_available=True,
    )
    return DownloadTaskService(InMemoryDownloadRepository(), validator, inspection)


def test_download_api_create_list_get_and_cancel() -> None:
    with TestClient(
        create_app(Settings(environment="test"), download_task_service=_service())
    ) as client:
        created_response = client.post(
            "/api/downloads",
            json={
                "url": "https://youtu.be/dQw4w9WgXcQ?private=secret",
                "output_type": "video",
                "video_quality": 1080,
            },
        )
        task_id = created_response.json()["id"]
        list_response = client.get("/api/downloads")
        get_response = client.get(f"/api/downloads/{task_id}")
        cancel_response = client.post(f"/api/downloads/{task_id}/cancel")

    assert created_response.status_code == 201
    assert created_response.json()["status"] == "queued"
    assert created_response.json()["queue_position"] == 1
    assert "url" not in created_response.json()
    assert "secret" not in created_response.text
    assert list_response.status_code == 200
    assert len(list_response.json()["items"]) == 1
    assert get_response.status_code == 200
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"


def test_download_api_rejects_contradictory_options() -> None:
    with TestClient(
        create_app(Settings(environment="test"), download_task_service=_service())
    ) as client:
        response = client.post(
            "/api/downloads",
            json={
                "url": "https://youtu.be/dQw4w9WgXcQ",
                "output_type": "video",
                "video_quality": 1080,
                "audio_bitrate": 192,
            },
        )

    assert response.status_code == 422


def test_download_api_returns_stable_not_found_error() -> None:
    with TestClient(
        create_app(Settings(environment="test"), download_task_service=_service())
    ) as client:
        response = client.get("/api/downloads/00000000-0000-4000-8000-000000000000")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "download_not_found",
            "message": "No se ha encontrado la descarga solicitada.",
        }
    }
