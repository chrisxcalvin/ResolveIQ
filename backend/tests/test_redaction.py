"""Phase 1: redaction pattern tests.

Covers the original phone-redaction bug (a 7-digit local-format number
slipping through unredacted), the fix, and non-collision checks against
the other numeric formats that actually appear in this codebase's data
(order IDs, dollar amounts, dates) — per the build spec's requirement
that broadening the phone pattern not create new false positives.
"""

from app.redaction.pii import redact


# --- the original bug, and its fix -----------------------------------------

def test_local_format_phone_is_redacted():
    """The original bug: 555-0142 has no area code, so the old 3-3-4-only
    pattern never matched it. This is the exact text that shipped
    unredacted in the live-verified run."""
    text = "My phone is 555-0142, please call me back."
    result = redact(text)
    assert "555-0142" not in result
    assert "[REDACTED_PHONE]" in result


def test_local_format_phone_with_dots_and_spaces_is_redacted():
    assert "[REDACTED_PHONE]" in redact("call 555.0142 anytime")
    assert "[REDACTED_PHONE]" in redact("call 555 0142 anytime")


def test_full_10_digit_phone_still_redacted():
    """The original pattern's happy path must keep working."""
    result = redact("Call me at 555-123-4567 tomorrow.")
    assert "555-123-4567" not in result
    assert "[REDACTED_PHONE]" in result


def test_10_digit_phone_with_country_code_still_redacted():
    result = redact("+1-555-123-4567 is my number")
    assert "555-123-4567" not in result
    assert "[REDACTED_PHONE]" in result


# --- other redaction categories, unaffected by the fix ----------------------

def test_email_redacted():
    result = redact("reach me at chris.test@example.com please")
    assert "chris.test@example.com" not in result
    assert "[REDACTED_EMAIL]" in result


def test_card_number_dashed_fully_redacted():
    """Regression test for the reorder: the broadened phone pattern must
    not carve a 3+4 digit slice out of the middle of a card number before
    the card pattern gets to see the whole thing."""
    result = redact("card 4412-5566-7788-9900 was declined")
    assert "4412" not in result
    assert "5566" not in result
    assert "[REDACTED_CARD]" in result
    assert "[REDACTED_PHONE]" not in result


def test_card_number_spaced_fully_redacted():
    result = redact("4412 5566 7788 9900 declined")
    assert "[REDACTED_CARD]" in result
    assert "[REDACTED_PHONE]" not in result


def test_card_number_unspaced_fully_redacted():
    result = redact("card ending 4412556677889900 was declined")
    assert "[REDACTED_CARD]" in result


def test_bare_account_number_redacted():
    result = redact("account number 883921 shows a hold")
    assert "883921" not in result
    assert "[REDACTED_ACCOUNT]" in result


def test_person_name_redacted():
    result = redact("This is John Smith, calling about my account.")
    assert "John Smith" not in result
    assert "[REDACTED_NAME]" in result


# --- false-positive guards: real formats used elsewhere in this codebase ----

def test_numeric_order_id_not_redacted():
    """Order IDs (app/ml/data.py _ORDER_IDS) are single unbroken digit
    runs, e.g. #48213 — five digits, no separator, under the 6-digit
    account-number floor. Must survive untouched.

    #A1092 is deliberately excluded here: spaCy's NER tags it as a PERSON
    (a false positive unrelated to this phase's regex changes — see the
    phase-1 checkpoint for that finding, left out of scope on purpose)."""
    for order_id in ["#48213", "#77281", "#9910", "#33456"]:
        result = redact(f"Payment for order {order_id} did not go through.")
        assert order_id in result


def test_dollar_amounts_not_redacted():
    """Dollar amounts (app/ml/data.py _AMOUNTS) must survive untouched —
    none of them are digit-dash-digit shaped, but this locks that in."""
    for amount in ["$12.50", "$45", "$99.99", "$230", "$1,200", "$15", "$68.20", "$500"]:
        result = redact(f"My payment of {amount} failed at checkout.")
        assert amount in result


def test_written_date_not_redacted():
    result = redact("Effective as of March 15, 2026, the policy changes.")
    assert "March 15, 2026" in result


def test_numeric_date_not_caught_by_local_phone_pattern():
    """MM-DD-YYYY is a 2-2-4 split, not 3-4, so the new local-phone
    alternative (which requires exactly 3 then 4 digits) must not match."""
    result = redact("the charge posted on 03-15-2026")
    assert "03-15-2026" in result
