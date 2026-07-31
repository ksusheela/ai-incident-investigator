"""Unit tests for `Settings`, in particular `cors_origins`'s parsing --
previously untested even though a parsing bug here would silently break
every frontend request (see `tests/integration/test_cors.py`)."""

from app.config import Settings


def test_cors_origins_defaults_to_the_frontend_dev_server():
    settings = Settings(_env_file=None)

    assert settings.cors_origins == ["http://localhost:5173"]


def test_cors_origins_splits_a_comma_separated_list():
    settings = Settings(_env_file=None, cors_allowed_origins="http://a.example,http://b.example")

    assert settings.cors_origins == ["http://a.example", "http://b.example"]


def test_cors_origins_trims_whitespace_and_drops_blank_entries():
    settings = Settings(_env_file=None, cors_allowed_origins=" http://a.example ,, http://b.example")

    assert settings.cors_origins == ["http://a.example", "http://b.example"]


def test_cors_origins_empty_string_yields_no_origins():
    settings = Settings(_env_file=None, cors_allowed_origins="")

    assert settings.cors_origins == []
