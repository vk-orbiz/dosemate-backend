import pytest

from app.core.config import Settings


@pytest.mark.parametrize(
    ("env", "override", "expected"),
    [
        ("development", None, True),
        ("test", None, True),
        ("production", None, False),
        ("production", True, True),
        ("development", False, False),
    ],
)
def test_migrate_on_startup_default_and_override(
    env: str, override: bool | None, expected: bool
) -> None:
    settings = Settings.model_validate(
        {
            "env": env,
            "run_migrations_on_startup": override,
            "jwt_secret": "x" * 40,
        }
    )
    assert settings.migrate_on_startup is expected
