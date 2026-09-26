import uuid


def random_suffix():
    return uuid.uuid4().hex[:6]


def random_ref(name=""):
    return f"ref-{name}-{random_suffix()}"
