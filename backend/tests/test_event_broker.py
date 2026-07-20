import asyncio
import json

from app.api.events import _last_event_id, format_download_event
from app.downloader.domain import (
    DownloadProgress,
    DownloadResult,
    DownloadSelection,
    DownloadStatus,
    DownloadTask,
    OutputType,
    VideoQuality,
)
from app.events.broker import DownloadEventBroker
from app.models.media import Platform


def _task(title: str = "Example") -> DownloadTask:
    return DownloadTask.create(
        platform=Platform.YOUTUBE,
        media_id="example1234",
        title=title,
        canonical_url="https://www.youtube.com/watch?v=example1234&token=secret",
        selection=DownloadSelection(OutputType.VIDEO, VideoQuality.P720),
    )


def test_broker_subscribes_replays_and_unsubscribes() -> None:
    async def scenario() -> None:
        broker = DownloadEventBroker()
        first = await broker.publish(_task("First"), name="download.created")
        second = await broker.publish(_task("Second"), name="download.created")

        initial = await broker.subscribe()
        resumed = await broker.subscribe(last_event_id=first.id)

        assert initial.requires_snapshot
        assert resumed.requires_snapshot is False
        assert [event.id for event in resumed.replay] == [second.id]
        assert broker.subscriber_count == 2
        await broker.unsubscribe(initial)
        await broker.unsubscribe(resumed)
        assert broker.subscriber_count == 0

    asyncio.run(scenario())


def test_broker_requires_snapshot_when_history_gap_exists() -> None:
    async def scenario() -> None:
        broker = DownloadEventBroker(history_size=2)
        for title in ("First", "Second", "Third"):
            await broker.publish(_task(title))

        subscription = await broker.subscribe(last_event_id=0)

        assert subscription.requires_snapshot
        assert subscription.replay == ()

    asyncio.run(scenario())


def test_slow_subscriber_receives_resync_signal_when_queue_is_full() -> None:
    async def scenario() -> None:
        broker = DownloadEventBroker(subscriber_queue_size=2)
        subscription = await broker.subscribe()
        for title in ("First", "Second", "Third"):
            await broker.publish(_task(title))

        events = [subscription.queue.get_nowait()]

        assert [event.name for event in events] == ["downloads.resync"]
        assert events[0].data == {}

    asyncio.run(scenario())


def test_progress_is_throttled_but_terminal_event_is_forced() -> None:
    async def scenario() -> None:
        broker = DownloadEventBroker(progress_interval_seconds=60)
        task = _task()
        task.current_attempt.transition_to(DownloadStatus.DOWNLOADING)
        first = await broker.publish(task)
        task.current_attempt.update_progress(DownloadProgress(percentage=50))
        throttled = await broker.publish(task)
        task.current_attempt.transition_to(
            DownloadStatus.COMPLETED,
            result=DownloadResult("Example.mp4", "mp4", 100, 720),
        )
        terminal = await broker.publish(task, force=True)

        assert first is not None
        assert throttled is None
        assert terminal is not None
        assert terminal.data["status"] == "completed"

    asyncio.run(scenario())


def test_event_payload_and_sse_never_expose_url_or_paths() -> None:
    async def scenario() -> None:
        broker = DownloadEventBroker()
        event = await broker.publish(_task(), name="download.created")
        assert event is not None

        serialized = format_download_event(event)
        payload = json.loads(
            next(
                line.removeprefix("data: ")
                for line in serialized.splitlines()
                if line.startswith("data: ")
            )
        )

        assert serialized.startswith(f"id: {event.id}\nevent: download.created\n")
        assert "secret" not in serialized
        assert "canonical_url" not in serialized
        assert payload["task"]["status"] == "queued"

    asyncio.run(scenario())


def test_last_event_id_parser_is_defensive() -> None:
    assert _last_event_id("42") == 42
    assert _last_event_id("invalid") is None
    assert _last_event_id("-1") is None
