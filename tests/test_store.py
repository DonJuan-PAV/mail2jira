from conftest import make_email
from store import Store


def test_new_email_is_not_processed(store):
    assert not store.is_processed(make_email())


def test_processed_email_is_remembered(store):
    email = make_email()
    store.mark_processed(email, ticket_created=True, ticket_key="SUP-1")
    assert store.is_processed(email)


def test_memory_survives_a_restart(tmp_path):
    path = str(tmp_path / "db.sqlite")
    email = make_email()
    Store(path).mark_processed(email, ticket_created=True)
    assert Store(path).is_processed(email)  # new object = like a restart


def test_counts(store):
    store.mark_processed(make_email(id="1"), ticket_created=True)
    store.mark_processed(make_email(id="2"), ticket_created=True)
    store.mark_processed(make_email(id="3", subject="RE: x"), ticket_created=False,
                         skip_reason="reply")
    assert store.count(ticket_created=True) == 2
    assert store.count(ticket_created=False) == 1


def test_marking_twice_does_not_double_count(store):
    email = make_email()
    store.mark_processed(email, ticket_created=True)
    store.mark_processed(email, ticket_created=True)
    assert store.count(ticket_created=True) == 1
