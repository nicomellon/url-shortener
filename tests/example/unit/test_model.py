from my_project.example.domain import events
from my_project.example.domain.model import Thing


def test_creating_a_thing_records_an_event():
    thing = Thing.create("t1", "First thing")
    assert thing.events == [events.ThingCreated(ref="t1")]
