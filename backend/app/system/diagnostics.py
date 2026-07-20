"""Safe checks for external downloader dependencies."""

import os
import re
import shutil
import subprocess
from collections.abc import Callable, Sequence
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from app.models.diagnostics import (
    DependencyDiagnostic,
    DependencyName,
    DependencyStatus,
    SystemDiagnostics,
)

CommandRunner = Callable[[Sequence[str]], str]
BinaryResolver = Callable[[str], str | None]
PackageVersionResolver = Callable[[str], str]

_VERSION_PATTERN = re.compile(r"(?P<version>\d+(?:\.\d+){1,3})")
_HOMEBREW_NODE_24 = Path("/opt/homebrew/opt/node@24/bin/node")


class DependencyDiagnosticsService:
    """Inspect required tools without leaking executable paths."""

    def __init__(
        self,
        *,
        runner: CommandRunner | None = None,
        resolver: BinaryResolver | None = None,
        package_version_resolver: PackageVersionResolver | None = None,
        node_binary: str | None = None,
    ) -> None:
        self._runner = runner or _run_version_command
        self._resolver = resolver or shutil.which
        self._package_version_resolver = package_version_resolver or version
        self._node_binary = node_binary

    def inspect(self) -> SystemDiagnostics:
        """Return one sanitized compatibility snapshot."""
        dependencies = [
            self._inspect_yt_dlp(),
            self._inspect_node(),
            self._inspect_binary(
                name=DependencyName.FFMPEG,
                command="ffmpeg",
                minimum_major=8,
                maximum_major=8,
            ),
            self._inspect_binary(
                name=DependencyName.FFPROBE,
                command="ffprobe",
                minimum_major=8,
                maximum_major=8,
            ),
        ]
        return SystemDiagnostics(
            ready=all(
                item.status is DependencyStatus.AVAILABLE for item in dependencies
            ),
            dependencies=dependencies,
        )

    def _inspect_yt_dlp(self) -> DependencyDiagnostic:
        try:
            installed_version = self._package_version_resolver("yt-dlp")
        except PackageNotFoundError:
            return _missing_dependency(DependencyName.YT_DLP)

        parsed_version = _extract_version(installed_version)
        if parsed_version is None or not parsed_version.startswith("2026."):
            return _incompatible_dependency(
                DependencyName.YT_DLP, parsed_version or installed_version
            )

        return DependencyDiagnostic(
            name=DependencyName.YT_DLP,
            status=DependencyStatus.AVAILABLE,
            version=parsed_version,
        )

    def _inspect_node(self) -> DependencyDiagnostic:
        binary = self._resolve_node_binary()
        return self._inspect_resolved_binary(
            name=DependencyName.NODE,
            binary=binary,
            minimum_major=24,
            maximum_major=24,
            version_argument="--version",
        )

    def _resolve_node_binary(self) -> str | None:
        if self._node_binary:
            return self._node_binary

        configured = os.getenv("VD_NODE_BINARY")
        if configured:
            return configured

        if _HOMEBREW_NODE_24.is_file():
            return str(_HOMEBREW_NODE_24)

        return self._resolver("node")

    def _inspect_binary(
        self,
        *,
        name: DependencyName,
        command: str,
        minimum_major: int,
        maximum_major: int,
        version_argument: str = "-version",
    ) -> DependencyDiagnostic:
        return self._inspect_resolved_binary(
            name=name,
            binary=self._resolver(command),
            minimum_major=minimum_major,
            maximum_major=maximum_major,
            version_argument=version_argument,
        )

    def _inspect_resolved_binary(
        self,
        *,
        name: DependencyName,
        binary: str | None,
        minimum_major: int,
        maximum_major: int,
        version_argument: str,
    ) -> DependencyDiagnostic:
        if binary is None:
            return _missing_dependency(name)

        try:
            output = self._runner([binary, version_argument])
        except (OSError, subprocess.SubprocessError):
            return _missing_dependency(name)

        version = _extract_version(output)
        if version is None:
            return _incompatible_dependency(name)

        major = int(version.split(".", maxsplit=1)[0])
        if not minimum_major <= major <= maximum_major:
            return _incompatible_dependency(name, version)

        return DependencyDiagnostic(
            name=name,
            status=DependencyStatus.AVAILABLE,
            version=version,
        )


def _run_version_command(arguments: Sequence[str]) -> str:
    """Run one fixed version command without a shell."""
    completed = subprocess.run(
        list(arguments),
        capture_output=True,
        check=True,
        shell=False,
        text=True,
        timeout=5,
    )
    return completed.stdout or completed.stderr


def _extract_version(output: str) -> str | None:
    match = _VERSION_PATTERN.search(output)
    return match.group("version") if match else None


def _missing_dependency(name: DependencyName) -> DependencyDiagnostic:
    return DependencyDiagnostic(
        name=name,
        status=DependencyStatus.MISSING,
        error_code=f"{name.value.replace('-', '_')}_missing",
    )


def _incompatible_dependency(
    name: DependencyName, version: str | None = None
) -> DependencyDiagnostic:
    return DependencyDiagnostic(
        name=name,
        status=DependencyStatus.INCOMPATIBLE,
        version=version,
        error_code=f"{name.value.replace('-', '_')}_incompatible",
    )
