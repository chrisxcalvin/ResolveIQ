"""Phase 2: decision-agent thresholds (app/decision/decide.py).

Pure function, no DB needed. Covers both threshold boundaries exactly
(< vs >=) and confirms which rule wins when more than one could apply.
"""

from app.decision.decide import (
    HIGH_URGENCY_THRESHOLD,
    LOW_CONFIDENCE_THRESHOLD,
    decide,
)


def test_low_confidence_flags_for_specialist_review():
    d = decide(category="general_query", urgency_score=0.1, confidence=0.1)
    assert d.needs_review is True
    assert d.specialist_flagged is True
    assert "Low draft confidence" in d.reason


def test_low_confidence_boundary_just_below_threshold_flags():
    d = decide(category="general_query", urgency_score=0.1, confidence=LOW_CONFIDENCE_THRESHOLD - 0.01)
    assert d.specialist_flagged is True


def test_confidence_exactly_at_threshold_does_not_trigger_low_confidence_rule():
    """The check is `< threshold`, so a confidence exactly equal to it must
    NOT trigger the low-confidence branch."""
    d = decide(category="general_query", urgency_score=0.1, confidence=LOW_CONFIDENCE_THRESHOLD)
    assert "Low draft confidence" not in d.reason


def test_dispute_at_high_urgency_flags_for_specialist_review():
    d = decide(category="dispute", urgency_score=HIGH_URGENCY_THRESHOLD, confidence=0.9)
    assert d.specialist_flagged is True
    assert "specialist attention" in d.reason


def test_dispute_urgency_boundary_just_below_threshold_does_not_flag():
    """The check is `>= threshold`, so urgency just under it must not flag."""
    d = decide(category="dispute", urgency_score=HIGH_URGENCY_THRESHOLD - 0.01, confidence=0.9)
    assert d.specialist_flagged is False


def test_non_dispute_category_at_high_urgency_does_not_flag():
    """Only `dispute` is in SPECIALIST_CATEGORIES — a high-urgency
    payment_failure ticket should NOT trigger the specialist-category rule."""
    d = decide(category="payment_failure", urgency_score=0.95, confidence=0.9)
    assert d.specialist_flagged is False


def test_standard_case_is_reviewable_but_not_flagged():
    d = decide(category="general_query", urgency_score=0.3, confidence=0.9)
    assert d.needs_review is True
    assert d.specialist_flagged is False
    assert d.reason == "Standard review — draft ready for agent approval."


def test_low_confidence_rule_wins_over_dispute_rule_when_both_apply():
    """A low-confidence, high-urgency dispute ticket should report the
    low-confidence reason, since that check runs first in decide()."""
    d = decide(category="dispute", urgency_score=0.99, confidence=0.1)
    assert d.specialist_flagged is True
    assert "Low draft confidence" in d.reason
    assert "specialist attention" not in d.reason


def test_every_outcome_always_needs_review():
    """No path through decide() should ever set needs_review=False — the
    project's core rule is nothing auto-sends, ever."""
    cases = [
        ("general_query", 0.1, 0.1),
        ("dispute", 0.9, 0.9),
        ("payment_failure", 0.99, 0.99),
    ]
    for category, urgency, confidence in cases:
        assert decide(category, urgency, confidence).needs_review is True
