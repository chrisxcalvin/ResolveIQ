"""Phase 2: decision-agent thresholds (app/decision/decide.py).

Pure function, no DB needed. Covers both threshold boundaries exactly
(< vs >=) and confirms which rule wins when more than one could apply.
"""

from app.decision.decide import (
    FAST_PATH_MAX_URGENCY,
    FAST_PATH_MIN_CONFIDENCE,
    FAST_PATH_MIN_RETRIEVAL_SIMILARITY,
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
    """No path through decide() should ever set needs_review=False when
    auto_resolve_threshold is left at its default (None) — the project's
    core rule is nothing auto-sends, ever, unless that flag is explicitly
    opted into (see the auto-resolve tests below for the one exception)."""
    cases = [
        ("general_query", 0.1, 0.1),
        ("dispute", 0.9, 0.9),
        ("payment_failure", 0.99, 0.99),
    ]
    for category, urgency, confidence in cases:
        assert decide(category, urgency, confidence).needs_review is True


# --- Phase 7: fast-path eligibility -----------------------------------

def test_fast_path_eligible_when_low_urgency_high_confidence_tight_match():
    d = decide(
        category="general_query",
        urgency_score=FAST_PATH_MAX_URGENCY - 0.01,
        confidence=FAST_PATH_MIN_CONFIDENCE,
        avg_retrieval_similarity=FAST_PATH_MIN_RETRIEVAL_SIMILARITY,
    )
    assert d.fast_path_eligible is True
    assert d.needs_review is True  # still reviewable, just fast-tracked
    assert "one-click approval" in d.reason


def test_fast_path_not_eligible_when_urgency_too_high():
    d = decide(
        category="general_query",
        urgency_score=FAST_PATH_MAX_URGENCY,
        confidence=0.95,
        avg_retrieval_similarity=0.95,
    )
    assert d.fast_path_eligible is False


def test_fast_path_not_eligible_when_confidence_too_low():
    d = decide(
        category="general_query",
        urgency_score=0.1,
        confidence=FAST_PATH_MIN_CONFIDENCE - 0.01,
        avg_retrieval_similarity=0.95,
    )
    assert d.fast_path_eligible is False


def test_fast_path_not_eligible_when_retrieval_similarity_missing():
    """No retrieved chunks at all (None) can't be a tight KB match."""
    d = decide(
        category="general_query", urgency_score=0.1, confidence=0.95, avg_retrieval_similarity=None
    )
    assert d.fast_path_eligible is False


def test_fast_path_not_eligible_when_retrieval_similarity_too_low():
    d = decide(
        category="general_query",
        urgency_score=0.1,
        confidence=0.95,
        avg_retrieval_similarity=FAST_PATH_MIN_RETRIEVAL_SIMILARITY - 0.01,
    )
    assert d.fast_path_eligible is False


def test_fast_path_excludes_dispute_even_if_otherwise_eligible():
    """dispute is fraud-adjacent (SPECIALIST_CATEGORIES) — excluded from
    fast-path on principle, not just because of the confidence/urgency
    numbers."""
    d = decide(
        category="dispute", urgency_score=0.1, confidence=0.99, avg_retrieval_similarity=0.99
    )
    assert d.fast_path_eligible is False


# --- Phase 7: auto-resolve (off by default) -----------------------------

def test_auto_resolve_threshold_none_never_auto_resolves_even_if_fast_path_eligible():
    d = decide(
        category="general_query",
        urgency_score=0.1,
        confidence=0.99,
        avg_retrieval_similarity=0.99,
        auto_resolve_threshold=None,
    )
    assert d.fast_path_eligible is True
    assert d.auto_resolved is False
    assert d.needs_review is True


def test_auto_resolve_fires_when_threshold_set_and_fast_path_eligible_and_confidence_clears_it():
    d = decide(
        category="general_query",
        urgency_score=0.1,
        confidence=0.95,
        avg_retrieval_similarity=0.9,
        auto_resolve_threshold=0.9,
    )
    assert d.auto_resolved is True
    assert d.needs_review is False
    assert "Auto-resolved" in d.reason


def test_auto_resolve_does_not_fire_when_confidence_below_threshold():
    d = decide(
        category="general_query",
        urgency_score=0.1,
        confidence=0.85,
        avg_retrieval_similarity=0.9,
        auto_resolve_threshold=0.9,
    )
    assert d.auto_resolved is False
    assert d.needs_review is True


def test_auto_resolve_does_not_fire_when_not_fast_path_eligible_even_above_threshold():
    """High confidence alone isn't enough — must also be fast-path eligible
    (low urgency, tight retrieval match, non-specialist category)."""
    d = decide(
        category="general_query",
        urgency_score=0.9,  # too urgent to be fast-path eligible
        confidence=0.95,
        avg_retrieval_similarity=0.9,
        auto_resolve_threshold=0.9,
    )
    assert d.fast_path_eligible is False
    assert d.auto_resolved is False
    assert d.needs_review is True
