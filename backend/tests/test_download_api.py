import asyncio
from unittest.mock import AsyncMock, Mock

from fastapi.testclient import TestClient

from app.config import Settings
from app.downloader.domain import (
    DownloadResult,
    DownloadSelection,
    DownloadStatus,
    DownloadTask,
    OutputType,
    VideoQuality,
)
from app.downloader.repository import InMemoryDownloadRepository
from app.downloader.service import DownloadApplicationError, DownloadTaskService
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
        delete_response = client.delete(f"/api/downloads/{task_id}")
        list_after_delete = client.get("/api/downloads")

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
    assert delete_response.status_code == 200
    assert delete_response.json() == {"deleted": True}
    assert list_after_delete.json()["items"] == []


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


def test_download_api_rejects_retry_for_non_retryable_task() -> None:
    with TestClient(
        create_app(Settings(environment="test"), download_task_service=_service())
    ) as client:
        created = client.post(
            "/api/downloads",
            json={
                "url": "https://youtu.be/dQw4w9WgXcQ",
                "output_type": "video",
                "video_quality": 720,
            },
        ).json()
        response = client.post(f"/api/downloads/{created['id']}/retry")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "retry_not_allowed"


def test_download_api_rejects_delete_for_active_or_queued_task() -> None:
    with TestClient(
        create_app(Settings(environment="test"), download_task_service=_service())
    ) as client:
        created = client.post(
            "/api/downloads",
            json={
                "url": "https://youtu.be/dQw4w9WgXcQ",
                "output_type": "video",
                "video_quality": 720,
            },
        ).json()
        response = client.delete(f"/api/downloads/{created['id']}")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "deletion_not_allowed"


def test_download_api_retries_interrupted_task_and_exposes_attempt_history() -> None:
    repository = InMemoryDownloadRepository()
    task = DownloadTask.create(
        platform=Platform.YOUTUBE,
        media_id="dQw4w9WgXcQ",
        title="Example",
        canonical_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        selection=DownloadSelection(OutputType.VIDEO, VideoQuality.P720),
    )
    task.current_attempt.transition_to(DownloadStatus.DOWNLOADING)
    task.current_attempt.transition_to(DownloadStatus.INTERRUPTED)
    asyncio.run(repository.create(task))
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
        title="Example refreshed",
        video_qualities=[720],
        audio_available=True,
    )
    service = DownloadTaskService(repository, validator, inspection)

    with TestClient(
        create_app(Settings(environment="test"), download_task_service=service)
    ) as client:
        response = client.post(f"/api/downloads/{task.id}/retry")

    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    assert response.json()["title"] == "Example refreshed"
    assert [attempt["status"] for attempt in response.json()["attempts"]] == [
        "interrupted",
        "queued",
    ]
    assert "url" not in response.json()


def test_download_api_opens_and_reveals_a_completed_file() -> None:
    task_service = AsyncMock()
    task_service.get_file_result.return_value = DownloadResult(
        "Example.mp4", "mp4", 100, 720, "/tmp/downloads"
    )
    file_actions = Mock()

    with TestClient(
        create_app(
            Settings(environment="test"),
            download_task_service=task_service,
            download_file_action_service=file_actions,
        )
    ) as client:
        open_response = client.post(
            "/api/downloads/00000000-0000-4000-8000-000000000001/open"
        )
        reveal_response = client.post(
            "/api/downloads/00000000-0000-4000-8000-000000000001/reveal"
        )

    assert open_response.status_code == 200
    assert open_response.json() == {"action": "opened"}
    assert reveal_response.status_code == 200
    assert reveal_response.json() == {"action": "revealed"}
    file_actions.open.assert_called_once_with("Example.mp4", "/tmp/downloads")
    file_actions.reveal.assert_called_once_with("Example.mp4", "/tmp/downloads")


def test_download_api_rejects_file_actions_before_completion() -> None:
    task_service = AsyncMock()
    task_service.get_file_result.side_effect = DownloadApplicationError(
        "download_file_not_ready",
        "La descarga todavía no tiene un archivo final disponible.",
        status_code=409,
    )

    with TestClient(
        create_app(
            Settings(environment="test"),
            download_task_service=task_service,
            download_file_action_service=Mock(),
        )
    ) as client:
        response = client.post(
            "/api/downloads/00000000-0000-4000-8000-000000000001/open"
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "download_file_not_ready"
