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
    assert "db_pool_checked_out" in r.text
