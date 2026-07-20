"""Safe operating-system actions for completed download files."""

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

FileLauncher = Callable[[list[str]], None]


class DownloadFileActionError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class DownloadFileActionService:
    def __init__(
        self,
        output_root: Path,
        *,
        launcher: FileLauncher | None = None,
        platform: str | None = None,
    ) -> None:
        self._output_root = output_root.expanduser().resolve()
        self._launcher = launcher or _launch_detached
        self._platform = platform or sys.platform

    def open(self, filename: str, output_root: str | Path | None = None) -> None:
        path = self._resolve_file(filename, output_root)
        self._launch(["/usr/bin/open", "--", str(path)])

    def reveal(self, filename: str, output_root: str | Path | None = None) -> None:
        path = self._resolve_file(filename, output_root)
        self._launch(["/usr/bin/open", "-R", "--", str(path)])

    def _resolve_file(
        self, filename: str, output_root: str | Path | None = None
    ) -> Path:
        if not filename or Path(filename).name != filename:
            raise DownloadFileActionError(
                "unsafe_output_path",
                "La ruta del archivo descargado no es segura.",
                status_code=409,
            )
        try:
            root = (
                Path(output_root).expanduser().resolve(strict=True)
                if output_root is not None
                else self._output_root
            )
            if root == Path(root.anchor) or not root.is_dir():
                raise ValueError("unsafe output root")
            path = (root / filename).resolve(strict=True)
            path.relative_to(root)
        except FileNotFoundError as error:
            raise DownloadFileActionError(
                "download_file_missing",
                "El archivo descargado ya no existe en la carpeta de destino.",
                status_code=404,
            ) from error
        except (OSError, ValueError) as error:
            raise DownloadFileActionError(
                "unsafe_output_path",
                "La ruta del archivo descargado no es segura.",
                status_code=409,
            ) from error
        if not path.is_file():
            raise DownloadFileActionError(
                "download_file_missing",
                "El archivo descargado ya no existe en la carpeta de destino.",
                status_code=404,
            )
        return path

    def _launch(self, arguments: list[str]) -> None:
        if self._platform != "darwin":
            raise DownloadFileActionError(
                "file_action_unsupported",
                "Esta acción todavía solo está disponible en macOS.",
                status_code=501,
            )
        try:
            self._launcher(arguments)
        except OSError as error:
            raise DownloadFileActionError(
                "file_action_failed",
                "No se ha podido abrir el archivo con macOS.",
                status_code=500,
            ) from error


def _launch_detached(arguments: list[str]) -> None:
    subprocess.Popen(
        arguments,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
