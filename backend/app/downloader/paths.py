"""Safe filesystem policy for download staging and final output."""

import os
import re
import shutil
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from app.downloader.executor import DownloadExecutionError

_UNSAFE_FILENAME = re.compile(r"[\x00-\x1f/:\\]+")
_REPEATED_SPACE = re.compile(r"\s+")
_MAX_STEM_LENGTH = 160


@dataclass(frozen=True, slots=True)
class DownloadWorkspace:
    staging_directory: Path
    output_root: Path

    @property
    def output_template(self) -> str:
        return str(self.staging_directory / "media.%(ext)s")


class DownloadPathPolicy:
    def __init__(self, *, output_root: Path, temporary_root: Path) -> None:
        self.output_root = output_root.expanduser().resolve()
        self.temporary_root = temporary_root.expanduser().resolve()

    def prepare(self, task_id: UUID) -> DownloadWorkspace:
        self._ensure_directory(self.output_root)
        self._ensure_directory(self.temporary_root)
        staging = Path(
            tempfile.mkdtemp(prefix=f"{task_id}-", dir=self.temporary_root)
        ).resolve()
        _require_contained(staging, self.temporary_root)
        return DownloadWorkspace(staging, self.output_root)

    @staticmethod
    def _ensure_directory(path: Path) -> None:
        try:
            path.mkdir(parents=True, exist_ok=True, mode=0o700)
        except OSError as error:
            raise DownloadExecutionError(
                "output_not_writable",
                "No se puede escribir en la carpeta seleccionada.",
            ) from error
        if not path.is_dir():
            raise DownloadExecutionError(
                "output_not_writable",
                "No se puede escribir en la carpeta seleccionada.",
            )


def sanitize_filename_stem(title: str) -> str:
    normalized = unicodedata.normalize("NFC", title)
    cleaned = _UNSAFE_FILENAME.sub(" ", normalized)
    cleaned = _REPEATED_SPACE.sub(" ", cleaned).strip(" .")
    if cleaned in {"", ".", ".."}:
        cleaned = "video"
    return cleaned[:_MAX_STEM_LENGTH].rstrip(" .") or "video"


def choose_available_path(root: Path, stem: str, extension: str) -> Path:
    safe_root = root.resolve(strict=True)
    safe_stem = sanitize_filename_stem(stem)
    safe_extension = extension.lower().lstrip(".")
    if not safe_extension.isalnum():
        raise DownloadExecutionError("unknown_error", "La extensión no es válida.")
    for suffix in range(10_000):
        label = safe_stem if suffix == 0 else f"{safe_stem} ({suffix})"
        candidate = safe_root / f"{label}.{safe_extension}"
        _require_contained(candidate, safe_root)
        if not candidate.exists():
            return candidate
    raise DownloadExecutionError(
        "output_not_writable", "No se puede reservar un nombre de archivo."
    )


def publish_file(source: Path, root: Path, stem: str, extension: str) -> Path:
    """Move a completed staging file without replacing an existing output."""
    if not source.is_file():
        raise DownloadExecutionError("unknown_error", "No existe el archivo final.")
    destination = choose_available_path(root, stem, extension)
    try:
        descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(descriptor)
        os.replace(source, destination)
    except FileExistsError:
        return publish_file(source, root, stem, extension)
    except OSError as error:
        destination.unlink(missing_ok=True)
        raise DownloadExecutionError(
            "output_not_writable",
            "No se puede escribir en la carpeta seleccionada.",
        ) from error
    return destination


def cleanup_workspace(workspace: DownloadWorkspace) -> None:
    """Remove only the task-scoped temporary directory."""
    _require_contained(workspace.staging_directory, workspace.staging_directory.parent)
    shutil.rmtree(workspace.staging_directory, ignore_errors=False)


def _require_contained(candidate: Path, root: Path) -> None:
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise DownloadExecutionError(
            "output_not_writable", "La ruta de salida no es segura."
        ) from error
