"""Application configuration with safe local defaults."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Environment = Literal["development", "test", "production"]
DownloadExecutorMode = Literal["simulated", "real"]
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings for one application instance."""

    app_name: str = "Video Downloader API"
    environment: Environment = "development"
    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "info"
    frontend_origin: str = "http://127.0.0.1:5173"
    download_executor: DownloadExecutorMode = "simulated"
    download_output_root: Path = _PROJECT_ROOT / "downloads"
    download_temporary_root: Path = _PROJECT_ROOT / "downloads" / ".temporary"

    @property
    def docs_enabled(self) -> bool:
        """Expose interactive API documentation outside production only."""
        return self.environment != "production"

    @classmethod
    def from_environment(cls) -> "Settings":
        """Build settings from non-sensitive environment variables."""
        environment = os.getenv("VD_ENV", "development")
        if environment not in {"development", "test", "production"}:
            raise ValueError("VD_ENV must be development, test, or production")
        download_executor = os.getenv("VD_DOWNLOAD_EXECUTOR", "simulated")
        if download_executor not in {"simulated", "real"}:
            raise ValueError("VD_DOWNLOAD_EXECUTOR must be simulated or real")

        return cls(
            environment=environment,
            port=_read_port(os.getenv("VD_PORT", "8000")),
            log_level=os.getenv("VD_LOG_LEVEL", "info"),
            frontend_origin=os.getenv("VD_FRONTEND_ORIGIN", "http://127.0.0.1:5173"),
            download_executor=download_executor,
            download_output_root=Path(
                os.getenv("VD_DOWNLOAD_OUTPUT_ROOT", str(_PROJECT_ROOT / "downloads"))
            ),
            download_temporary_root=Path(
                os.getenv(
                    "VD_DOWNLOAD_TEMPORARY_ROOT",
                    str(_PROJECT_ROOT / "downloads" / ".temporary"),
                )
            ),
        )


def _read_port(raw_port: str) -> int:
    """Parse and validate the local API port."""
    try:
        port = int(raw_port)
    except ValueError as error:
        raise ValueError("VD_PORT must be an integer") from error

    if not 1 <= port <= 65535:
        raise ValueError("VD_PORT must be between 1 and 65535")
    return port
