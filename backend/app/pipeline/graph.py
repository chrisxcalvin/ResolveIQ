"""LangGraph pipeline: redact -> classify -> breach_risk -> retrieve ->
customer_context -> draft -> decide -> [specialist_review] -> END.

Mostly linear, with one real conditional branch (Phase 9): a ticket the
decision step flags for specialist attention (low confidence, or a
high-urgency dispute) doesn't just carry that flag into the queue — it
gets a genuinely distinct second pass first, widening retrieval context
and forcing the strong-tier model regardless of urgency, before an agent
ever sees it. A routine ticket skips straight to END. See
docs/checkpoints/phase-9.md for why this lives in the graph itself rather
than as a queue-side "needs extra review" filter.

Built fresh per ticket since it closes over that ticket's DB session rather
than threading it through LangGraph's config mechanism.
"""

import uuid
from datetime import datetime, timezone
from typing import TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.tracing import observe
from app.decision.decide import Decision, decide
from app.drafting.customer_context import build_customer_history_summary
from app.drafting.draft import DraftResult, draft
from app.ml.breach_risk import get_queue_depth, score_breach_risk
from app.ml.classifier import classify
from app.redaction.pii import redact
from app.retrieval.retrieve import RetrievedChunk, retrieve

# Wider than the standard top_k=5 — the specialist pass is deliberately more
# expensive, trading latency/cost for a better-grounded second attempt on
# the tickets most likely to need it.
SPECIALIST_REVIEW_TOP_K = 8


def route_after_decide(state: "PipelineState") -> str:
    """The graph's one real conditional branch point. A module-level function
    (not a closure inside build_graph) so it's unit-testable on a bare state
    dict without a DB session or a compiled graph — see test_graph_routing.py.
    """
    return "specialist_review" if state["decision"].specialist_flagged else "end"


class PipelineState(TypedDict, total=False):
    raw_text: str
    ticket_id: uuid.UUID
    customer_id: uuid.UUID
    created_at: datetime
    redacted_text: str
    category: str
    category_confidence: float
    urgency_score: float
    urgency_confidence: float
    breach_risk_score: float
    chunks: list[RetrievedChunk]
    customer_history: str
    draft_result: DraftResult
    decision: Decision
    specialist_reviewed: bool


def build_graph(db: AsyncSession):
    @observe(name="redact")
    async def redact_node(state: PipelineState) -> dict:
        return {"redacted_text": redact(state["raw_text"])}

    @observe(name="classify")
    async def classify_node(state: PipelineState) -> dict:
        result = classify(state["redacted_text"])
        return {
            "category": result.category,
            "category_confidence": result.category_confidence,
            "urgency_score": result.urgency_score,
            "urgency_confidence": result.urgency_confidence,
        }

    @observe(name="breach_risk")
    async def breach_risk_node(state: PipelineState) -> dict:
        age_minutes = (
            datetime.now(timezone.utc) - state["created_at"].replace(tzinfo=timezone.utc)
        ).total_seconds() / 60
        queue_depth = await get_queue_depth(db, state["category"])
        score = score_breach_risk(age_minutes, state["category"], state["urgency_score"], queue_depth)
        return {"breach_risk_score": score}

    @observe(name="retrieve", as_type="retriever")
    async def retrieve_node(state: PipelineState) -> dict:
        chunks = await retrieve(db, state["redacted_text"], category=state["category"], top_k=5)
        return {"chunks": chunks}

    @observe(name="customer_context")
    async def customer_context_node(state: PipelineState) -> dict:
        summary = await build_customer_history_summary(
            db, state["customer_id"], state["ticket_id"]
        )
        return {"customer_history": summary}

    @observe(name="draft")
    async def draft_node(state: PipelineState) -> dict:
        result = draft(
            state["redacted_text"],
            state["chunks"],
            state["urgency_score"],
            state["category_confidence"],
            state["customer_history"],
        )
        return {"draft_result": result}

    @observe(name="decide")
    async def decide_node(state: PipelineState) -> dict:
        chunks = state.get("chunks") or []
        avg_retrieval_similarity = (
            sum(c.similarity for c in chunks) / len(chunks) if chunks else None
        )
        result = decide(
            state["category"],
            state["urgency_score"],
            state["draft_result"].confidence,
            avg_retrieval_similarity=avg_retrieval_similarity,
            auto_resolve_threshold=settings.auto_resolve_threshold,
        )
        return {"decision": result}

    @observe(name="specialist_review")
    async def specialist_review_node(state: PipelineState) -> dict:
        wider_chunks = await retrieve(
            db, state["redacted_text"], category=state["category"], top_k=SPECIALIST_REVIEW_TOP_K
        )
        result = draft(
            state["redacted_text"],
            wider_chunks,
            state["urgency_score"],
            state["category_confidence"],
            state["customer_history"],
            force_strong_tier=True,
        )
        return {"chunks": wider_chunks, "draft_result": result, "specialist_reviewed": True}

    graph = StateGraph(PipelineState)
    graph.add_node("redact", redact_node)
    graph.add_node("classify", classify_node)
    graph.add_node("breach_risk", breach_risk_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("customer_context", customer_context_node)
    graph.add_node("draft", draft_node)
    graph.add_node("decide", decide_node)
    graph.add_node("specialist_review", specialist_review_node)

    graph.set_entry_point("redact")
    graph.add_edge("redact", "classify")
    graph.add_edge("classify", "breach_risk")
    graph.add_edge("breach_risk", "retrieve")
    graph.add_edge("retrieve", "customer_context")
    graph.add_edge("customer_context", "draft")
    graph.add_edge("draft", "decide")
    graph.add_conditional_edges(
        "decide", route_after_decide, {"specialist_review": "specialist_review", "end": END}
    )
    graph.add_edge("specialist_review", END)

    return graph.compile()


@observe(name="ticket_pipeline")
async def run_pipeline(
    db: AsyncSession,
    raw_text: str,
    ticket_id: uuid.UUID,
    customer_id: uuid.UUID,
    created_at: datetime,
) -> PipelineState:
    graph = build_graph(db)
    return await graph.ainvoke(
        {
            "raw_text": raw_text,
            "ticket_id": ticket_id,
            "customer_id": customer_id,
            "created_at": created_at,
        }
    )
