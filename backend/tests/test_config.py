import pytest

from app.config import Settings


def test_production_disables_api_documentation() -> None:
    settings = Settings(environment="production")

    assert settings.docs_enabled is False


def test_invalid_port_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VD_PORT", "70000")

    with pytest.raises(ValueError, match="between 1 and 65535"):
        Settings.from_environment()


def test_real_download_executor_and_paths_are_explicitly_configurable(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("VD_DOWNLOAD_EXECUTOR", "real")
    monkeypatch.setenv("VD_DOWNLOAD_OUTPUT_ROOT", str(tmp_path / "output"))
    monkeypatch.setenv("VD_DOWNLOAD_TEMPORARY_ROOT", str(tmp_path / "temporary"))

    settings = Settings.from_environment()

    assert settings.download_executor == "real"
    assert settings.download_output_root == tmp_path / "output"
    assert settings.download_temporary_root == tmp_path / "temporary"


def test_invalid_download_executor_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VD_DOWNLOAD_EXECUTOR", "unsafe")

    with pytest.raises(ValueError, match="simulated or real"):
        Settings.from_environment()
