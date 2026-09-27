from url_shortener.domain import model


def test_new_short_codes_are_alphanumeric_and_fixed_length():
    code = model.new_short_code()
    assert len(code) == model.SHORT_CODE_LENGTH
    assert code.isalnum()


def test_new_short_codes_differ():
    assert len({model.new_short_code() for _ in range(100)}) == 100
