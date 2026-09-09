"""LangGraph pipeline: redact -> classify -> breach_risk -> retrieve ->
customer_context -> draft -> decide.

Linear, not branching — the decision node's output is state attached to the
ticket, not a different graph path (see the Day 3 plan notes for why).
Built fresh per ticket since it closes over that ticket's DB session rather
than threading it through LangGraph's config mechanism.
"""

import uuid
from datetime import datetime, timezone
from typing import TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tracing import observe
from app.decision.decide import Decision, decide
from app.drafting.customer_context import build_customer_history_summary
from app.drafting.draft import DraftResult, draft
from app.ml.breach_risk import get_queue_depth, score_breach_risk
from app.ml.classifier import classify
from app.redaction.pii import redact
from app.retrieval.retrieve import RetrievedChunk, retrieve


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
        result = decide(
            state["category"], state["urgency_score"], state["draft_result"].confidence
        )
        return {"decision": result}

    graph = StateGraph(PipelineState)
    graph.add_node("redact", redact_node)
    graph.add_node("classify", classify_node)
    graph.add_node("breach_risk", breach_risk_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("customer_context", customer_context_node)
    graph.add_node("draft", draft_node)
    graph.add_node("decide", decide_node)

    graph.set_entry_point("redact")
    graph.add_edge("redact", "classify")
    graph.add_edge("classify", "breach_risk")
    graph.add_edge("breach_risk", "retrieve")
    graph.add_edge("retrieve", "customer_context")
    graph.add_edge("customer_context", "draft")
    graph.add_edge("draft", "decide")
    graph.add_edge("decide", END)

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
