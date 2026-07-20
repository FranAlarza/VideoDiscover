"""Isolated yt-dlp executor foundations for real downloads."""

import asyncio
import multiprocessing
import time
from collections.abc import Callable
from contextlib import suppress
from multiprocessing.connection import Connection
from pathlib import Path
from typing import Any, Protocol

from app.downloader.domain import DownloadResult, DownloadTask, OutputType
from app.downloader.executor import (
    DownloadCancelled,
    DownloadExecutionError,
    ProcessingCallback,
    ProgressCallback,
)
from app.downloader.paths import (
    DownloadPathPolicy,
    cleanup_workspace,
    publish_file,
)


class ProcessDownloadRunnerProtocol(Protocol):
    def download(
        self,
        canonical_url: str,
        options: dict[str, Any],
        timeout_seconds: float,
        event_callback: Callable[[dict[str, Any]], None],
        cancelled: Callable[[], bool],
    ) -> dict[str, Any]: ...


class ProcessDownloadRunner:
    """Run yt-dlp in a spawned process with a hard timeout."""

    def __init__(
        self,
        *,
        worker_target: Callable[[Connection, str, dict[str, Any]], None] | None = None,
    ) -> None:
        self._worker_target = worker_target or _yt_dlp_download_worker

    def download(
        self,
        canonical_url: str,
        options: dict[str, Any],
        timeout_seconds: float,
        event_callback: Callable[[dict[str, Any]], None],
        cancelled: Callable[[], bool],
    ) -> dict[str, Any]:
        context = multiprocessing.get_context("spawn")
        parent, child = context.Pipe(duplex=False)
        process = context.Process(
            target=self._worker_target,
            args=(child, canonical_url, options),
            daemon=True,
        )
        process.start()
        child.close()
        deadline = time.monotonic() + timeout_seconds
        outcome: dict[str, Any] | None = None
        try:
            while outcome is None:
                if cancelled():
                    _stop_process(process)
                    raise DownloadCancelled
                if time.monotonic() >= deadline:
                    _stop_process(process)
                    raise DownloadExecutionError(
                        "network_error", "La descarga ha superado el tiempo permitido."
                    )
                if parent.poll(0.1):
                    message = parent.recv()
                    if message.get("type") == "event":
                        event_callback(message["event"])
                    else:
                        outcome = message
                elif not process.is_alive():
                    raise DownloadExecutionError(
                        "unknown_error", "No se pudo completar la descarga."
                    )
            process.join(timeout=1)
        except EOFError as error:
            raise DownloadExecutionError(
                "unknown_error", "No se pudo completar la descarga."
            ) from error
        finally:
            parent.close()
            if process.is_alive():
                _stop_process(process)
        if outcome.get("status") != "ok":
            raise _classify_download_error(str(outcome.get("message", "")))
        result = outcome.get("result")
        if not isinstance(result, dict):
            raise DownloadExecutionError(
                "unknown_error", "No se pudo completar la descarga."
            )
        return result


class YtDlpDownloadExecutor:
    """Real executor kept opt-in until lifecycle cleanup is completed in 2.3B."""

    def __init__(
        self,
        path_policy: DownloadPathPolicy,
        *,
        runner: ProcessDownloadRunnerProtocol | None = None,
        node_binary: str,
        timeout_seconds: float = 3600,
    ) -> None:
        self._path_policy = path_policy
        self._runner = runner or ProcessDownloadRunner()
        self._node_binary = node_binary
        self._timeout_seconds = timeout_seconds

    async def execute(
        self,
        task: DownloadTask,
        *,
        on_progress: ProgressCallback,
        on_processing: ProcessingCallback,
        cancel_event: asyncio.Event,
    ) -> DownloadResult:
        if cancel_event.is_set():
            raise DownloadCancelled
        workspace = self._path_policy.prepare(task.id)
        options = build_yt_dlp_download_options(
            task, workspace.output_template, self._node_binary
        )
        loop = asyncio.get_running_loop()
        events: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

        def receive_event(event: dict[str, Any]) -> None:
            loop.call_soon_threadsafe(events.put_nowait, event)

        execution = asyncio.create_task(
            asyncio.to_thread(
                self._runner.download,
                task.canonical_url,
                options,
                self._timeout_seconds,
                receive_event,
                cancel_event.is_set,
            )
        )
        processing_started = False
        try:
            while not execution.done():
                try:
                    event = await asyncio.wait_for(events.get(), timeout=0.1)
                except TimeoutError:
                    continue
                processing_started = await _dispatch_event(
                    event, on_progress, on_processing, processing_started
                )
            raw_result = await execution
            while not events.empty():
                processing_started = await _dispatch_event(
                    events.get_nowait(),
                    on_progress,
                    on_processing,
                    processing_started,
                )
            source = _verified_output_path(raw_result, workspace.staging_directory)
            extension = (
                "mp4" if task.selection.output_type is OutputType.VIDEO else "mp3"
            )
            published = publish_file(
                source, workspace.output_root, task.title, extension
            )
            return _map_download_result(raw_result, published, task)
        finally:
            with suppress(OSError):
                cleanup_workspace(workspace)


def build_yt_dlp_download_options(
    task: DownloadTask, output_template: str, node_binary: str
) -> dict[str, Any]:
    common: dict[str, Any] = {
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "overwrites": False,
        "continuedl": False,
        "nopart": False,
        "socket_timeout": 15,
        "retries": 2,
        "fragment_retries": 2,
        "js_runtimes": {"node": {"path": node_binary}},
        "remote_components": set(),
    }
    if task.selection.output_type is OutputType.VIDEO:
        quality = task.selection.video_quality.value
        common.update(
            {
                "format": (
                    f"bestvideo[vcodec^=avc1][height<={quality}]"
                    "+bestaudio[acodec^=mp4a]/"
                    f"best[vcodec^=avc1][acodec^=mp4a][height<={quality}]"
                ),
                "merge_output_format": "mp4",
                "postprocessors": [],
            }
        )
    else:
        bitrate = task.selection.audio_bitrate.value
        common.update(
            {
                "format": "bestaudio/best",
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": str(bitrate),
                    }
                ],
            }
        )
    return common


def _yt_dlp_download_worker(
    connection: Connection, canonical_url: str, options: dict[str, Any]
) -> None:
    try:
        from yt_dlp import YoutubeDL

        def progress_hook(data: dict[str, Any]) -> None:
            if data.get("status") == "downloading":
                connection.send({"type": "event", "event": _progress_event(data)})

        def postprocessor_hook(data: dict[str, Any]) -> None:
            if data.get("status") == "started":
                connection.send({"type": "event", "event": {"kind": "processing"}})

        worker_options = dict(options)
        worker_options["progress_hooks"] = [progress_hook]
        worker_options["postprocessor_hooks"] = [postprocessor_hook]
        with YoutubeDL(worker_options) as downloader:
            info = downloader.extract_info(canonical_url, download=True)
            requested = info.get("requested_downloads") or []
            paths = [
                item.get("filepath") for item in requested if isinstance(item, dict)
            ]
            connection.send(
                {
                    "type": "result",
                    "status": "ok",
                    "result": {
                        "filepath": next((path for path in paths if path), None),
                        "filesize": info.get("filesize") or info.get("filesize_approx"),
                        "height": info.get("height"),
                    },
                }
            )
    except Exception as error:
        connection.send(
            {"type": "result", "status": "error", "message": str(error)[:1000]}
        )
    finally:
        connection.close()


def _verified_output_path(raw: dict[str, Any], staging_directory: Path) -> Path:
    raw_path = raw.get("filepath")
    if not isinstance(raw_path, str):
        matches = list(staging_directory.glob("media.*"))
        matches = [path for path in matches if path.suffix not in {".part", ".ytdl"}]
        if len(matches) != 1:
            raise DownloadExecutionError(
                "unknown_error", "No se encontró el archivo descargado."
            )
        path = matches[0]
    else:
        path = Path(raw_path).resolve()
    try:
        path.relative_to(staging_directory.resolve())
    except ValueError as error:
        raise DownloadExecutionError(
            "output_not_writable", "La ruta producida no es segura."
        ) from error
    if not path.is_file():
        matches = list(staging_directory.glob("media.*"))
        matches = [path for path in matches if path.suffix not in {".part", ".ytdl"}]
        if len(matches) == 1:
            path = matches[0]
    if not path.is_file():
        raise DownloadExecutionError(
            "unknown_error", "No se encontró el archivo descargado."
        )
    return path


def _map_download_result(
    raw: dict[str, Any], path: Path, task: DownloadTask
) -> DownloadResult:
    return DownloadResult(
        filename=path.name,
        extension=path.suffix.lstrip(".").lower(),
        size_bytes=path.stat().st_size,
        effective_quality=(
            int(raw["height"])
            if isinstance(raw.get("height"), int)
            else (
                task.selection.video_quality.value
                if task.selection.video_quality is not None
                else None
            )
        ),
    )


async def _dispatch_event(
    event: dict[str, Any],
    on_progress: ProgressCallback,
    on_processing: ProcessingCallback,
    processing_started: bool,
) -> bool:
    if event.get("kind") == "processing":
        if not processing_started:
            await on_processing()
        return True
    if event.get("kind") != "progress":
        return processing_started
    from app.downloader.domain import DownloadProgress

    await on_progress(
        DownloadProgress(
            percentage=_optional_number(event.get("percentage")),
            downloaded_bytes=_optional_int(event.get("downloaded_bytes")),
            total_bytes=_optional_int(event.get("total_bytes")),
            speed_bytes_per_second=_optional_number(event.get("speed")),
            eta_seconds=_optional_int(event.get("eta")),
        )
    )
    return processing_started


def _progress_event(data: dict[str, Any]) -> dict[str, Any]:
    downloaded = _optional_int(data.get("downloaded_bytes"))
    total = _optional_int(data.get("total_bytes")) or _optional_int(
        data.get("total_bytes_estimate")
    )
    percentage = (
        min(downloaded * 100 / total, 100) if downloaded is not None and total else None
    )
    return {
        "kind": "progress",
        "percentage": percentage,
        "downloaded_bytes": downloaded,
        "total_bytes": total,
        "speed": data.get("speed"),
        "eta": data.get("eta"),
    }


def _optional_int(value: Any) -> int | None:
    return int(value) if isinstance(value, int | float) and value >= 0 else None


def _optional_number(value: Any) -> float | None:
    return float(value) if isinstance(value, int | float) and value >= 0 else None


def _classify_download_error(message: str) -> DownloadExecutionError:
    lowered = message.lower()
    if "no space left" in lowered or "disk full" in lowered:
        return DownloadExecutionError(
            "disk_full", "No hay suficiente espacio en el disco."
        )
    if "permission denied" in lowered:
        return DownloadExecutionError(
            "output_not_writable", "No se puede escribir en la carpeta seleccionada."
        )
    if "requested format" in lowered or "format is not available" in lowered:
        return DownloadExecutionError(
            "format_unavailable", "La calidad seleccionada ya no está disponible."
        )
    if "ffmpeg" in lowered:
        return DownloadExecutionError(
            "ffmpeg_missing", "FFmpeg no está instalado o no se encuentra."
        )
    if any(token in lowered for token in ("timed out", "network", "connection")):
        return DownloadExecutionError(
            "network_error", "La conexión se interrumpió durante la descarga."
        )
    return DownloadExecutionError("unknown_error", "No se pudo completar la descarga.")


def _stop_process(process: multiprocessing.Process) -> None:
    process.terminate()
    process.join(timeout=1)
    if process.is_alive():
        process.kill()
        process.join(timeout=1)
