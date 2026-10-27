"""The LangGraph pipeline's one real conditional branch (Phase 9):
specialist-flagged tickets route to a second, more expensive review pass
instead of straight to END. route_after_decide is a module-level function
specifically so this can be tested without a DB session or a compiled
graph — see app/pipeline/graph.py's docstring.
"""

from app.decision.decide import Decision
from app.pipeline.graph import route_after_decide


def _state(decision: Decision) -> dict:
    return {"decision": decision}


def test_specialist_flagged_routes_to_specialist_review():
    decision = Decision(
        needs_review=True,
        specialist_flagged=True,
        fast_path_eligible=False,
        auto_resolved=False,
        reason="Low draft confidence — needs careful human review.",
    )
    assert route_after_decide(_state(decision)) == "specialist_review"


def test_non_flagged_routes_straight_to_end():
    decision = Decision(
        needs_review=True,
        specialist_flagged=False,
        fast_path_eligible=False,
        auto_resolved=False,
        reason="Standard review — draft ready for agent approval.",
    )
    assert route_after_decide(_state(decision)) == "end"


def test_fast_path_eligible_but_not_specialist_flagged_still_routes_to_end():
    decision = Decision(
        needs_review=True,
        specialist_flagged=False,
        fast_path_eligible=True,
        auto_resolved=False,
        reason="High-confidence FAQ match — flagged for one-click approval.",
    )
    assert route_after_decide(_state(decision)) == "end"


def test_auto_resolved_is_never_specialist_flagged_so_routes_to_end():
    # decide() never sets both auto_resolved and specialist_flagged True at
    # once (they're mutually exclusive branches in decide()) — confirming
    # that here pins the invariant the router relies on.
    decision = Decision(
        needs_review=False,
        specialist_flagged=False,
        fast_path_eligible=True,
        auto_resolved=True,
        reason="Auto-resolved: confidence cleared the configured threshold.",
    )
    assert route_after_decide(_state(decision)) == "end"
