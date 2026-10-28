"""The LangGraph pipeline's two conditional branch points (Phase 9):
specialist-flagged tickets route to a second, more expensive review pass
instead of straight to END, and off-domain input (confirmed live — see
app/pipeline/graph.py's docstring) short-circuits past drafting entirely.
Both routers are module-level functions specifically so this can be
tested without a DB session or a compiled graph.
"""

from app.decision.decide import Decision
from app.pipeline.graph import (
    OUT_OF_DOMAIN_SIMILARITY_THRESHOLD,
    route_after_decide,
    route_after_retrieve,
)
from app.retrieval.retrieve import RetrievedChunk


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


def test_out_of_domain_flag_always_routes_to_end_even_if_specialist_flagged():
    """The out_of_domain short-circuit's whole point is avoiding a second
    expensive pass on input that was never going to match the KB — a
    confidence-driven specialist_flagged=True (which out_of_domain's
    confidence=0.0 draft always triggers) must not undo that."""
    decision = Decision(
        needs_review=True,
        specialist_flagged=True,
        fast_path_eligible=False,
        auto_resolved=False,
        reason="Low draft confidence — needs careful human review.",
    )
    assert route_after_decide({"decision": decision, "out_of_domain": True}) == "end"


# --- route_after_retrieve (out-of-domain guardrail) -------------------------

def _chunks(*similarities: float) -> list[RetrievedChunk]:
    return [
        RetrievedChunk(chunk_id=f"c{i}", document_title="doc", content="x", similarity=s)
        for i, s in enumerate(similarities)
    ]


def test_low_similarity_routes_to_out_of_domain():
    state = {"chunks": _chunks(0.05, 0.07, 0.06)}
    assert route_after_retrieve(state) == "out_of_domain"


def test_similarity_at_threshold_routes_to_customer_context():
    # Exactly at the threshold is NOT below it — only strictly-below counts.
    state = {"chunks": _chunks(OUT_OF_DOMAIN_SIMILARITY_THRESHOLD)}
    assert route_after_retrieve(state) == "customer_context"


def test_real_ticket_similarity_routes_to_customer_context():
    # The lowest avg_retrieval_similarity actually observed across a
    # 30-ticket real benchmark batch (see docs/checkpoints/phase-9.md) —
    # pins that the threshold doesn't swallow real legitimate tickets.
    state = {"chunks": _chunks(0.223, 0.223, 0.223)}
    assert route_after_retrieve(state) == "customer_context"


def test_empty_chunks_routes_to_out_of_domain():
    assert route_after_retrieve({"chunks": []}) == "out_of_domain"
