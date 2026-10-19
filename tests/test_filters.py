import pytest

from filters import get_skip_reason


@pytest.mark.parametrize("subject, sender, expected_start", [
    ("RE: printer broken", "client@example.com", "reply/forward"),
    ("Re : imprimante en panne", "client@example.com", "reply/forward"),
    ("FW: invoice", "client@example.com", "reply/forward"),
    ("FWD: invoice", "client@example.com", "reply/forward"),
    ("TR: facture", "client@example.com", "reply/forward"),
    ("Password reset", "noreply@example.com", "automated sender"),
    ("Your order", "do-not-reply@shop.com", "automated sender"),
    ("Delivery failure", "MAILER-DAEMON@example.com", "automated sender"),
    ("Automatic reply: Out of office", "client@example.com", "automatic message"),
    ("Réponse automatique : absent", "client@example.com", "automatic message"),
    ("Undeliverable: hello", "client@example.com", "automatic message"),
    ("You have won a prize!", "client@example.com", "possible spam"),
    ("Félicitations !", "client@example.com", "possible spam"),
    ("", "client@example.com", "empty subject"),
    ("   ", "client@example.com", "empty subject"),
])
def test_noise_is_skipped(subject, sender, expected_start):
    reason = get_skip_reason(subject, sender)
    assert reason is not None and reason.startswith(expected_start)


@pytest.mark.parametrize("subject", [
    "Cannot log in to the app",
    "Reset password",            # starts with "Re" but no colon
    "Treasury report",           # starts with "Tr" but no colon
    "Request: new laptop",       # has a colon, but "Request" is not a prefix
    "Imprimante en panne au 2e étage",
])
def test_real_requests_pass(subject):
    assert get_skip_reason(subject, "client@example.com") is None


def test_missing_values_do_not_crash():
    assert get_skip_reason(None, None) == "empty subject"
