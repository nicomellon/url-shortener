import argparse

from sqlalchemy import create_engine, text

from url_shortener import config
from url_shortener.entrypoints import admin


def test_seed_short_codes_count_up_in_base_62():
    assert admin.seed_short_code(0) == "0000000"
    assert admin.seed_short_code(61) == "000000Z"
    assert admin.seed_short_code(62) == "0000010"


def test_seed_short_codes_are_unique():
    codes = {admin.seed_short_code(i) for i in range(10_000)}
    assert len(codes) == 10_000


def test_seeding_twice_does_not_duplicate_urls(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    config.get_settings.cache_clear()
    args = argparse.Namespace(count=25_000)

    admin.seed_urls(args)
    admin.seed_urls(args)

    with create_engine(database_url).connect() as connection:
        count = connection.execute(text("SELECT count(*) FROM short_urls")).scalar()
    assert count == 25_000
    config.get_settings.cache_clear()
