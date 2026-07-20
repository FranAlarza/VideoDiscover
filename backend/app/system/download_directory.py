"""Validation for a user-selected local download directory."""

import tempfile
from pathlib import Path


class DownloadDirectoryError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class DownloadDirectoryValidator:
    def __init__(self, *, temporary_root: Path) -> None:
        self._temporary_root = temporary_root.expanduser().resolve()

    def validate(self, candidate: str | Path) -> Path:
        raw_path = str(candidate).strip()
        if not raw_path or "\x00" in raw_path:
            raise _invalid_directory()
        expanded = Path(raw_path).expanduser()
        if not expanded.is_absolute():
            raise _invalid_directory()
        try:
            resolved = expanded.resolve()
        except OSError as error:
            raise _invalid_directory() from error
        if resolved == Path(resolved.anchor) or _is_within(
            resolved, self._temporary_root
        ):
            raise DownloadDirectoryError(
                "unsafe_download_directory",
                "La carpeta seleccionada no es un destino de descarga seguro.",
            )
        try:
            resolved.mkdir(parents=True, exist_ok=True, mode=0o700)
            if not resolved.is_dir():
                raise NotADirectoryError(resolved)
            with tempfile.NamedTemporaryFile(
                prefix=".video-downloader-write-test-", dir=resolved
            ):
                pass
        except OSError as error:
            raise DownloadDirectoryError(
                "download_directory_not_writable",
                "No se puede escribir en la carpeta seleccionada.",
            ) from error
        return resolved


def _is_within(candidate: Path, root: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def _invalid_directory() -> DownloadDirectoryError:
    return DownloadDirectoryError(
        "invalid_download_directory",
        "La carpeta de descargas seleccionada no es válida.",
    )
