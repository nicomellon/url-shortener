from url_shortener.urls.domain import model

from ...random_refs import random_suffix


def test_shorten_a_url_and_follow_it(client):
    url = f"https://example.com/{random_suffix()}"

    r = client.post("/urls", json={"url": url})
    assert r.status_code == 201
    body = r.json()
    assert body["url"] == url
    assert body["short_url"] == f"http://testserver/{body['short_code']}"

    r = client.get(f"/{body['short_code']}", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == url


def test_shortening_the_same_url_twice_gives_two_working_codes(client):
    url = f"https://example.com/{random_suffix()}"

    first = client.post("/urls", json={"url": url}).json()
    second = client.post("/urls", json={"url": url}).json()

    assert first["short_code"] != second["short_code"]
    for body in (first, second):
        r = client.get(f"/{body['short_code']}", follow_redirects=False)
        assert r.headers["location"] == url


def test_retries_when_a_short_code_is_taken(client, monkeypatch):
    monkeypatch.setattr(model, "new_short_code", lambda: "taken01")
    client.post("/urls", json={"url": "https://example.com/first"})

    codes = iter(["taken01", "free001"])
    monkeypatch.setattr(model, "new_short_code", lambda: next(codes))
    r = client.post("/urls", json={"url": "https://example.com/second"})

    assert r.status_code == 201
    assert r.json()["short_code"] == "free001"


def test_invalid_url_returns_422(client):
    r = client.post("/urls", json={"url": "not a url"})
    assert r.status_code == 422


def test_unknown_short_code_returns_404(client):
    r = client.get(f"/{random_suffix()}", follow_redirects=False)
    assert r.status_code == 404
