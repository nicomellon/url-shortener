from ...random_refs import random_ref


def test_create_and_get_a_thing(client):
    ref = random_ref()

    r = client.post("/things", json={"ref": ref, "name": "First thing"})
    assert r.status_code == 201

    r = client.get(f"/things/{ref}")
    assert r.status_code == 200
    assert r.json() == {"ref": ref, "name": "First thing"}


def test_creating_a_duplicate_thing_returns_409(client):
    ref = random_ref()
    client.post("/things", json={"ref": ref, "name": "First thing"})

    r = client.post("/things", json={"ref": ref, "name": "Another thing"})
    assert r.status_code == 409


def test_unknown_thing_returns_404(client):
    r = client.get(f"/things/{random_ref()}")
    assert r.status_code == 404
