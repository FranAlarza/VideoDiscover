import pytest

from app.config import Settings


def test_production_disables_api_documentation() -> None:
    settings = Settings(environment="production")

    assert settings.docs_enabled is False


def test_invalid_port_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VD_PORT", "70000")

    with pytest.raises(ValueError, match="between 1 and 65535"):
        Settings.from_environment()
