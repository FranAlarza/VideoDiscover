import asyncio

from app.downloader.domain import (
    DownloadSelection,
    DownloadStatus,
    DownloadTask,
    OutputType,
    VideoQuality,
)
from app.downloader.repository import InMemoryDownloadRepository
from app.models.media import Platform


def _task(title: str = "Example") -> DownloadTask:
    return DownloadTask.create(
        platform=Platform.YOUTUBE,
        media_id="dQw4w9WgXcQ",
        title=title,
        canonical_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        selection=DownloadSelection(
            output_type=OutputType.VIDEO,
            video_quality=VideoQuality.P720,
        ),
    )


def test_repository_returns_isolated_copies() -> None:
    async def scenario() -> None:
        repository = InMemoryDownloadRepository()
        original = _task()
        await repository.create(original)

        loaded = await repository.get(original.id)
        assert loaded is not None
        loaded.title = "Mutated outside repository"

        reloaded = await repository.get(original.id)
        assert reloaded is not None
        assert reloaded.title == "Example"

    asyncio.run(scenario())


def test_repository_lists_creation_order_and_saves_state() -> None:
    async def scenario() -> None:
        repository = InMemoryDownloadRepository()
        first = await repository.create(_task("First"))
        await repository.create(_task("Second"))
        first.current_attempt.transition_to(DownloadStatus.CANCELLED)
        await repository.save(first)

        items = await repository.list()

        assert [item.title for item in items] == ["First", "Second"]
        assert items[0].status is DownloadStatus.CANCELLED

    asyncio.run(scenario())
