import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.downloader.domain import (
    AudioBitrate,
    DownloadSelection,
    DownloadTask,
    OutputType,
    VideoQuality,
)
from app.downloader.executor import DownloadCancelled
from app.downloader.paths import DownloadPathPolicy
from app.downloader.yt_dlp_executor import (
    YtDlpDownloadExecutor,
    build_yt_dlp_download_options,
)
from app.models.media import Platform


def _task(
    output_type: OutputType = OutputType.VIDEO,
) -> DownloadTask:
    selection = (
        DownloadSelection(output_type, video_quality=VideoQuality.P720)
        if output_type is OutputType.VIDEO
        else DownloadSelection(output_type, audio_bitrate=AudioBitrate.KBPS192)
    )
    return DownloadTask.create(
        platform=Platform.YOUTUBE,
        media_id="example1234",
        title="Example",
        canonical_url="https://www.youtube.com/watch?v=example1234",
        selection=selection,
    )


def test_video_options_are_bounded_and_do_not_overwrite() -> None:
    options = build_yt_dlp_download_options(
        _task(), "/safe/task/media.%(ext)s", "/tools/node"
    )

    assert options["format"] == (
        "bestvideo[vcodec^=avc1][height<=720]+bestaudio[acodec^=mp4a]/"
        "bestvideo[vcodec^=avc1][height<=720]+bestaudio[acodec^=aac]/"
        "bestvideo[vcodec^=h264][height<=720]+bestaudio[acodec^=mp4a]/"
        "bestvideo[vcodec^=h264][height<=720]+bestaudio[acodec^=aac]/"
        "best[vcodec^=avc1][acodec^=mp4a][height<=720]/"
        "best[vcodec^=avc1][acodec^=aac][height<=720]/"
        "best[vcodec^=h264][acodec^=mp4a][height<=720]/"
        "best[vcodec^=h264][acodec^=aac][height<=720]/"
        "best[ext=mp4][height<=720]"
    )
    assert options["merge_output_format"] == "mp4"
    assert options["postprocessors"] == []
    assert options["overwrites"] is False
    assert options["noplaylist"] is True
    assert options["outtmpl"] == "/safe/task/media.%(ext)s"
    assert options["js_runtimes"] == {"node": {"path": "/tools/node"}}
    assert "shell" not in options


def test_audio_options_request_mp3_at_selected_bitrate() -> None:
    options = build_yt_dlp_download_options(
        _task(OutputType.AUDIO), "/safe/task/media.%(ext)s", "/tools/node"
    )

    assert options["format"] == "bestaudio/best"
    assert options["postprocessors"] == [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }
    ]


class FakeRunner:
    def __init__(self, temporary_root: Path) -> None:
        self.temporary_root = temporary_root
        self.calls: list[tuple[str, dict[str, Any], float]] = []

    def download(
        self,
        canonical_url: str,
        options: dict[str, Any],
        timeout_seconds: float,
        event_callback: Callable[[dict[str, Any]], None],
        cancelled: Callable[[], bool],
    ) -> dict[str, Any]:
        assert not cancelled()
        self.calls.append((canonical_url, options, timeout_seconds))
        event_callback(
            {
                "kind": "progress",
                "percentage": 50,
                "downloaded_bytes": 5,
                "total_bytes": 10,
            }
        )
        event_callback({"kind": "processing"})
        event_callback({"kind": "processing"})
        output = Path(options["outtmpl"].replace("%(ext)s", "mp4"))
        output.write_bytes(b"safe media")
        return {"filepath": str(output), "height": 720}


def test_executor_uses_isolated_workspace_and_maps_verified_result(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        temporary_root = tmp_path / "temporary"
        runner = FakeRunner(temporary_root)
        executor = YtDlpDownloadExecutor(
            DownloadPathPolicy(
                output_root=tmp_path / "downloads",
                temporary_root=temporary_root,
            ),
            runner=runner,
            node_binary="/tools/node",
        )

        progress = []
        processing = []
        result = await executor.execute(
            _task(),
            on_progress=lambda value: _append_async(progress, value),
            on_processing=lambda: _append_async(processing, True),
            cancel_event=asyncio.Event(),
        )

        assert result.filename == "Example.mp4"
        assert result.size_bytes == len(b"safe media")
        assert result.effective_quality == 720
        assert progress[0].percentage == 50
        assert processing == [True]
        assert (tmp_path / "downloads" / "Example.mp4").is_file()
        assert list(temporary_root.iterdir()) == []
        _, options, _ = runner.calls[0]
        output_parent = Path(options["outtmpl"]).parent.resolve()
        assert output_parent.is_relative_to(temporary_root.resolve())

    asyncio.run(scenario())


class CancellableRunner:
    def download(
        self,
        canonical_url: str,
        options: dict[str, Any],
        timeout_seconds: float,
        event_callback: Callable[[dict[str, Any]], None],
        cancelled: Callable[[], bool],
    ) -> dict[str, Any]:
        import time

        while not cancelled():
            time.sleep(0.005)
        raise DownloadCancelled


def test_executor_propagates_cancellation_and_cleans_staging(tmp_path: Path) -> None:
    async def scenario() -> None:
        temporary_root = tmp_path / "temporary"
        executor = YtDlpDownloadExecutor(
            DownloadPathPolicy(
                output_root=tmp_path / "downloads",
                temporary_root=temporary_root,
            ),
            runner=CancellableRunner(),
            node_binary="/tools/node",
        )
        cancel_event = asyncio.Event()
        execution = asyncio.create_task(
            executor.execute(
                _task(),
                on_progress=lambda value: _append_async([], value),
                on_processing=lambda: _append_async([], True),
                cancel_event=cancel_event,
            )
        )
        await asyncio.sleep(0.02)
        cancel_event.set()

        try:
            await execution
        except DownloadCancelled:
            pass
        else:
            raise AssertionError("cancellation was not propagated")
        assert list(temporary_root.iterdir()) == []
        assert list((tmp_path / "downloads").iterdir()) == []

    asyncio.run(scenario())


async def _append_async(target: list, value: Any) -> None:
    target.append(value)
