from concurrent.futures import ThreadPoolExecutor

from ..random_refs import random_suffix


def test_concurrent_writes_all_succeed(client):
    # FastAPI runs sync routes in a thread pool, so these really do overlap
    urls = [f"https://example.com/{random_suffix()}" for _ in range(50)]

    with ThreadPoolExecutor(max_workers=20) as pool:
        responses = list(
            pool.map(lambda url: client.post("/urls", json={"url": url}), urls)
        )

    assert [r.status_code for r in responses] == [201] * len(urls)
    for url, r in zip(urls, responses, strict=True):
        redirect = client.get(f"/{r.json()['short_code']}", follow_redirects=False)
        assert redirect.headers["location"] == url
