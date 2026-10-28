"""Exercises the REAL compiled LangGraph (app/pipeline/graph.py's
build_graph + run_pipeline), not just route_after_decide in isolation —
proves add_conditional_edges is wired correctly and a specialist-flagged
ticket's state actually passes through specialist_review_node, while a
routine ticket skips it. Every model/retrieval call is stubbed (no Groq/HF/
network calls, no KB data needed) so only the graph's own control flow is
under test; db_session is still a real test-DB session since several nodes
take it as a positional arg.
"""

import uuid
from datetime import datetime, timezone

import pytest

import app.pipeline.graph as graph_module
from app.decision.decide import Decision
from app.drafting.draft import DraftResult
from app.ml.classifier import ClassificationResult
from app.pipeline.graph import run_pipeline
from app.retrieval.retrieve import RetrievedChunk


def _chunks(n: int) -> list[RetrievedChunk]:
    return [
        RetrievedChunk(chunk_id=f"c{i}", document_title="doc", content="x", similarity=0.5)
        for i in range(n)
    ]


@pytest.fixture
def stub_pipeline_steps(monkeypatch):
    """Stubs every node's underlying call so run_pipeline needs no network,
    no model weights, and no seeded KB data — only decide() runs for real,
    since that's the function whose output drives the branch under test.
    """
    monkeypatch.setattr(graph_module, "redact", lambda text: text)
    monkeypatch.setattr(
        graph_module,
        "classify",
        lambda text: ClassificationResult(
            category="dispute",
            category_confidence=0.9,
            urgency_score=0.9,
            urgency_confidence=0.9,
        ),
    )
    monkeypatch.setattr(graph_module, "score_breach_risk", lambda *a, **k: 0.5)

    async def _fake_queue_depth(db, category):
        return 1

    monkeypatch.setattr(graph_module, "get_queue_depth", _fake_queue_depth)

    async def _fake_customer_history(db, customer_id, ticket_id):
        return ""

    monkeypatch.setattr(graph_module, "build_customer_history_summary", _fake_customer_history)

    retrieve_calls: list[int] = []

    async def _fake_retrieve(db, query, category=None, top_k=5):
        retrieve_calls.append(top_k)
        return _chunks(min(top_k, 5))

    monkeypatch.setattr(graph_module, "retrieve", _fake_retrieve)

    draft_calls: list[dict] = []

    def _fake_draft(text, chunks, urgency_score, category_confidence, customer_history, force_strong_tier=False):
        draft_calls.append({"force_strong_tier": force_strong_tier, "n_chunks": len(chunks)})
        # First call (normal pass): deliberately low confidence so decide()
        # flags it for specialist review. Second call (the specialist pass,
        # force_strong_tier=True): a believable higher confidence, as a real
        # wider-context, stronger-model re-draft plausibly would produce.
        confidence = 0.9 if force_strong_tier else 0.1
        return DraftResult(
            draft_text="stub reply", source_chunk_ids=[c.chunk_id for c in chunks],
            confidence=confidence, tier="strong" if force_strong_tier else "cheap",
        )

    monkeypatch.setattr(graph_module, "draft", _fake_draft)

    return {"retrieve_calls": retrieve_calls, "draft_calls": draft_calls}


@pytest.mark.asyncio
async def test_low_confidence_draft_actually_traverses_specialist_review_node(
    db_session, stub_pipeline_steps
):
    state = await run_pipeline(
        db_session,
        raw_text="some ticket text",
        ticket_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        created_at=datetime.now(timezone.utc),
    )

    assert state["decision"].specialist_flagged is True
    assert state.get("specialist_reviewed") is True
    # draft() called twice: the normal pass, then the specialist pass forced
    # to the strong tier.
    assert len(stub_pipeline_steps["draft_calls"]) == 2
    assert stub_pipeline_steps["draft_calls"][0]["force_strong_tier"] is False
    assert stub_pipeline_steps["draft_calls"][1]["force_strong_tier"] is True
    # retrieve() called twice: the normal top_k=5 pass, then the wider
    # specialist-review pass.
    assert stub_pipeline_steps["retrieve_calls"] == [5, graph_module.SPECIALIST_REVIEW_TOP_K]
    # The final draft_result in state is the specialist (second) one, not
    # the original low-confidence one.
    assert state["draft_result"].confidence == 0.9
    assert state["draft_result"].tier == "strong"


@pytest.mark.asyncio
async def test_high_confidence_draft_skips_specialist_review_node(
    db_session, stub_pipeline_steps, monkeypatch
):
    # Force a high-confidence draft on the first (and only expected) call.
    def _fake_draft_high_conf(text, chunks, urgency_score, category_confidence, customer_history, force_strong_tier=False):
        stub_pipeline_steps["draft_calls"].append({"force_strong_tier": force_strong_tier})
        return DraftResult(
            draft_text="stub reply", source_chunk_ids=[c.chunk_id for c in chunks],
            confidence=0.9, tier="strong",
        )

    monkeypatch.setattr(graph_module, "draft", _fake_draft_high_conf)
    # dispute + high urgency would otherwise specialist-flag regardless of
    # confidence — force a non-specialist category so only the confidence
    # path is under test here.
    monkeypatch.setattr(
        graph_module,
        "classify",
        lambda text: ClassificationResult(
            category="general_query", category_confidence=0.9, urgency_score=0.1, urgency_confidence=0.9,
        ),
    )

    state = await run_pipeline(
        db_session,
        raw_text="some ticket text",
        ticket_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        created_at=datetime.now(timezone.utc),
    )

    assert state["decision"].specialist_flagged is False
    assert state.get("specialist_reviewed") is None
    assert len(stub_pipeline_steps["draft_calls"]) == 1
    assert stub_pipeline_steps["retrieve_calls"] == [5]


@pytest.mark.asyncio
async def test_low_similarity_retrieval_skips_customer_context_draft_and_specialist_review(
    db_session, stub_pipeline_steps, monkeypatch
):
    """The out-of-domain guardrail (added after a live off-topic ticket --
    'Give me code for travelling salesman problem' -- burned a real LLM
    call and landed on an unexplained 'AI draft unavailable'). Low
    retrieval similarity must skip customer_context, draft, AND
    specialist_review entirely -- not just avoid the normal draft call
    and then immediately re-trigger an equally pointless specialist pass.
    """
    customer_context_calls: list[bool] = []

    async def _fake_customer_history(db, customer_id, ticket_id):
        customer_context_calls.append(True)
        return ""

    monkeypatch.setattr(graph_module, "build_customer_history_summary", _fake_customer_history)

    async def _fake_low_similarity_retrieve(db, query, category=None, top_k=5):
        stub_pipeline_steps["retrieve_calls"].append(top_k)
        return [RetrievedChunk(chunk_id="c0", document_title="doc", content="x", similarity=0.06)]

    monkeypatch.setattr(graph_module, "retrieve", _fake_low_similarity_retrieve)

    state = await run_pipeline(
        db_session,
        raw_text="Give me code for travelling salesman problem",
        ticket_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        created_at=datetime.now(timezone.utc),
    )

    assert state["out_of_domain"] is True
    assert state["draft_result"].tier == "out_of_domain"
    assert state["draft_result"].confidence == 0.0
    assert state["draft_result"].source_chunk_ids == []
    assert customer_context_calls == []
    assert stub_pipeline_steps["draft_calls"] == []
    assert state.get("specialist_reviewed") is None
    # retrieve() called exactly once — never a second, equally-doomed
    # specialist-review retrieval on top of the already-low-similarity one.
    assert stub_pipeline_steps["retrieve_calls"] == [5]
    # decide() still runs off the synthetic draft_result (confidence=0.0
    # naturally flags it for human review — that's correct, it's the
    # SECOND redraft attempt that's wasted, not human visibility).
    assert state["decision"].needs_review is True
