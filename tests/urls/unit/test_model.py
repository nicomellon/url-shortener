from url_shortener.urls.domain import events, model


def test_creating_a_short_url_records_an_event():
    short_url = model.ShortURL.create("abc1234", "https://example.com/")
    assert short_url.events == [
        events.ShortURLCreated(short_code="abc1234", url="https://example.com/")
    ]


def test_new_short_codes_are_alphanumeric_and_fixed_length():
    code = model.new_short_code()
    assert len(code) == model.SHORT_CODE_LENGTH
    assert code.isalnum()


def test_new_short_codes_differ():
    assert len({model.new_short_code() for _ in range(100)}) == 100
