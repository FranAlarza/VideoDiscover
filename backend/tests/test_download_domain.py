from datetime import UTC

import pytest

from app.downloader.domain import (
    AudioBitrate,
    DownloadAttempt,
    DownloadDomainError,
    DownloadFailure,
    DownloadProgress,
    DownloadResult,
    DownloadSelection,
    DownloadStatus,
    DownloadTask,
    OutputType,
    VideoQuality,
)
from app.models.media import Platform


def _task() -> DownloadTask:
    return DownloadTask.create(
        platform=Platform.YOUTUBE,
        media_id="dQw4w9WgXcQ",
        title="Example",
        canonical_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        selection=DownloadSelection(
            output_type=OutputType.VIDEO,
            video_quality=VideoQuality.P1080,
        ),
    )


def test_video_and_audio_selections_enforce_exclusive_options() -> None:
    video = DownloadSelection(
        output_type=OutputType.VIDEO,
        video_quality=VideoQuality.P1080,
    )
    audio = DownloadSelection(
        output_type=OutputType.AUDIO,
        audio_bitrate=AudioBitrate.KBPS192,
    )

    assert video.video_quality is VideoQuality.P1080
    assert audio.audio_bitrate is AudioBitrate.KBPS192

    with pytest.raises(DownloadDomainError, match="requiere calidad"):
        DownloadSelection(output_type=OutputType.VIDEO)
    with pytest.raises(DownloadDomainError, match="requiere bitrate"):
        DownloadSelection(output_type=OutputType.AUDIO)


def test_task_uses_uuid_utc_time_and_first_queued_attempt() -> None:
    task = _task()

    assert task.id.version == 4
    assert task.created_at.tzinfo is UTC
    assert task.status is DownloadStatus.QUEUED
    assert task.current_attempt.number == 1


def test_valid_download_state_path() -> None:
    attempt = DownloadAttempt(number=1)

    attempt.transition_to(DownloadStatus.DOWNLOADING)
    attempt.update_progress(
        DownloadProgress(
            percentage=50,
            downloaded_bytes=500,
            total_bytes=1000,
            speed_bytes_per_second=100,
            eta_seconds=5,
        )
    )
    attempt.transition_to(DownloadStatus.PROCESSING)
    attempt.transition_to(
        DownloadStatus.COMPLETED,
        result=DownloadResult(
            filename="Example.mp4",
            extension="mp4",
            size_bytes=1000,
            effective_quality=1080,
        ),
    )

    assert attempt.status is DownloadStatus.COMPLETED
    assert attempt.started_at is not None
    assert attempt.finished_at is not None
    assert attempt.result is not None


@pytest.mark.parametrize(
    ("initial", "target"),
    [
        (DownloadStatus.QUEUED, DownloadStatus.PROCESSING),
        (DownloadStatus.QUEUED, DownloadStatus.COMPLETED),
        (DownloadStatus.COMPLETED, DownloadStatus.DOWNLOADING),
        (DownloadStatus.CANCELLED, DownloadStatus.COMPLETED),
        (DownloadStatus.FAILED, DownloadStatus.DOWNLOADING),
        (DownloadStatus.INTERRUPTED, DownloadStatus.DOWNLOADING),
    ],
)
def test_invalid_transitions_are_rejected(
    initial: DownloadStatus, target: DownloadStatus
) -> None:
    attempt = DownloadAttempt(number=1, status=initial)

    with pytest.raises(DownloadDomainError) as captured:
        attempt.transition_to(target)

    assert captured.value.code == "invalid_status_transition"


def test_failure_and_completion_require_terminal_details() -> None:
    failed = DownloadAttempt(number=1, status=DownloadStatus.DOWNLOADING)
    completed = DownloadAttempt(number=1, status=DownloadStatus.DOWNLOADING)

    with pytest.raises(DownloadDomainError, match="requiere un error"):
        failed.transition_to(DownloadStatus.FAILED)
    with pytest.raises(DownloadDomainError, match="requiere resultado"):
        completed.transition_to(DownloadStatus.COMPLETED)


def test_progress_rejects_invalid_values_and_inactive_state() -> None:
    with pytest.raises(DownloadDomainError):
        DownloadProgress(percentage=101)
    with pytest.raises(DownloadDomainError):
        DownloadProgress(downloaded_bytes=-1)

    attempt = DownloadAttempt(number=1)
    with pytest.raises(DownloadDomainError) as captured:
        attempt.update_progress(DownloadProgress(percentage=10))
    assert captured.value.code == "invalid_progress_state"


def test_retry_creates_a_new_attempt_without_mutating_history() -> None:
    task = _task()
    first = task.current_attempt
    first.transition_to(DownloadStatus.DOWNLOADING)
    first.transition_to(
        DownloadStatus.FAILED,
        failure=DownloadFailure(code="network_error", message="Network failed"),
    )

    second = task.start_new_attempt()

    assert len(task.attempts) == 2
    assert task.attempts[0].status is DownloadStatus.FAILED
    assert task.attempts[0].failure is not None
    assert second.number == 2
    assert second.status is DownloadStatus.QUEUED


def test_retry_is_rejected_for_non_retryable_status() -> None:
    with pytest.raises(DownloadDomainError) as captured:
        _task().start_new_attempt()
    assert captured.value.code == "retry_not_allowed"
