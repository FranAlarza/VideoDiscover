"""Native macOS directory selection without accepting command input."""

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path


class DirectoryChooserError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class MacOSDirectoryChooser:
    _SCRIPT = (
        'POSIX path of (choose folder with prompt "Selecciona la carpeta de descargas")'
    )

    def __init__(
        self,
        *,
        platform: str = sys.platform,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ) -> None:
        self._platform = platform
        self._runner = runner

    def choose(self) -> Path:
        if self._platform != "darwin":
            raise DirectoryChooserError(
                "directory_chooser_unavailable",
                "El selector nativo de carpetas solo está disponible en macOS.",
                status_code=501,
            )
        completed = self._runner(
            ["/usr/bin/osascript", "-e", self._SCRIPT],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            if "User canceled" in completed.stderr or "-128" in completed.stderr:
                raise DirectoryChooserError(
                    "directory_selection_cancelled",
                    "No se ha cambiado la carpeta de descargas.",
                    status_code=409,
                )
            raise DirectoryChooserError(
                "directory_chooser_failed",
                "No se ha podido abrir el selector de carpetas.",
                status_code=500,
            )
        selected = completed.stdout.strip()
        if not selected:
            raise DirectoryChooserError(
                "directory_chooser_failed",
                "El selector no ha devuelto una carpeta válida.",
                status_code=500,
            )
        return Path(selected)
