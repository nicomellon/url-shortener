from ..random_refs import random_suffix


def test_metrics_are_labelled_by_route_not_by_path(client):
    client.get(f"/{random_suffix()}", follow_redirects=False)

    r = client.get("/metrics")

    assert r.status_code == 200
    assert (
        'http_requests_total{handler="/{short_code}",method="GET",status="404"}'
        in r.text
    )
    assert "http_request_duration_seconds_bucket" in r.text


def test_metrics_include_the_connection_pool_and_the_process(client):
    client.get(f"/{random_suffix()}", follow_redirects=False)

    r = client.get("/metrics")

    for name in (
        "db_pool_checked_out",
        "db_pool_connections_open",
        "app_process_cpu_seconds",
        "app_process_resident_memory_bytes",
    ):
        assert f"\n{name} " in r.text
