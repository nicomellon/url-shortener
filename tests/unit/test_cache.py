from url_shortener.adapters import cache


def test_returns_what_was_put():
    read_cache = cache.LRUCache(maxsize=2)
    read_cache.put("a", "https://a.example/")

    assert read_cache.get("a") == "https://a.example/"
    assert read_cache.get("b") is None


def test_evicts_the_least_recently_used_entry():
    read_cache = cache.LRUCache(maxsize=2)
    read_cache.put("a", "https://a.example/")
    read_cache.put("b", "https://b.example/")
    read_cache.get("a")  # now b is the least recently used

    read_cache.put("c", "https://c.example/")

    assert read_cache.get("a") == "https://a.example/"
    assert read_cache.get("b") is None
    assert read_cache.get("c") == "https://c.example/"


def test_size_zero_stores_nothing():
    read_cache = cache.LRUCache(maxsize=0)
    read_cache.put("a", "https://a.example/")

    assert read_cache.get("a") is None
