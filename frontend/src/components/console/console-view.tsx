"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Inbox } from "lucide-react";
import {
  ApiError,
  getAccessToken,
  getTicket,
  listTickets,
  resolveTicket,
  type ResolveAction,
  type TicketDetail,
  type TicketListItem,
} from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { PipelineTrace, type TraceStage } from "@/components/pipeline-trace";
import { cn } from "@/lib/utils";

type RiskBucket = "high" | "medium" | "low";
const QUEUE_POLL_INTERVAL_MS = 4000;

function urgencyBucket(score: number | null): RiskBucket {
  if (score === null) return "low";
  if (score >= 0.75) return "high";
  if (score >= 0.4) return "medium";
  return "low";
}

function breachRiskBucket(score: number | null): RiskBucket | null {
  if (score === null) return null;
  if (score >= 0.6) return "high";
  if (score >= 0.3) return "medium";
  return "low";
}

// Confidence is the inverse of risk: a HIGH number is the healthy outcome,
// so it gets the "low/resolved/healthy" green, not the "high" red — same
// three functional colors as risk, opposite direction, per the design
// spec's own pairing (High/low-confidence -> red, Low/healthy -> green).
function confidenceBucket(score: number | null): RiskBucket {
  if (score === null) return "medium";
  if (score >= 0.7) return "low";
  if (score >= 0.4) return "medium";
  return "high";
}

const SIGNAL_DOT: Record<RiskBucket, string> = {
  high: "bg-signal-high",
  medium: "bg-signal-medium",
  low: "bg-signal-low",
};

const SIGNAL_TEXT: Record<RiskBucket, string> = {
  high: "text-signal-high",
  medium: "text-signal-medium",
  low: "text-signal-low",
};

const SIGNAL_BORDER: Record<RiskBucket, string> = {
  high: "border-l-signal-high",
  medium: "border-l-signal-medium",
  low: "border-l-signal-low",
};

function formatAge(createdAt: string): string {
  const minutes = Math.max(0, Math.floor((Date.now() - new Date(createdAt).getTime()) / 60000));
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}m`;
}

function formatPct(value: number | null): string {
  return value === null ? "—" : `${Math.round(value * 100)}%`;
}

/**
 * The three-panel console: queue (left) | ticket + pipeline trace (center)
 * | inspectable context — sources, confidence breakdown, history (right).
 * Not a card grid: this product's differentiator is that AI reasoning is
 * inspectable, so the layout puts retrieval sources and the confidence
 * formula's own components in permanent view next to the draft, not behind
 * a click. See docs/checkpoints/phase-6.md for why this over a chat UI.
 */
export function ConsoleView({ selectedTicketId }: { selectedTicketId?: string }) {
  const router = useRouter();
  const [tickets, setTickets] = useState<TicketListItem[] | null>(null);
  const [listError, setListError] = useState<string | null>(null);

  useEffect(() => {
    if (!getAccessToken()) {
      router.push("/login");
      return;
    }
    let cancelled = false;
    const load = () =>
      listTickets()
        .then((rows) => !cancelled && setTickets(rows))
        .catch((err) => !cancelled && setListError(err instanceof ApiError ? err.message : "Failed to load tickets"));
    load();
    const handle = setInterval(load, QUEUE_POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(handle);
    };
  }, [router]);

  return (
    <main className="mx-auto flex w-full max-w-[1700px] flex-1 flex-col md:flex-row">
      <QueuePanel tickets={tickets} error={listError} selectedId={selectedTicketId} />
      <TicketAndContext key={selectedTicketId ?? "none"} ticketId={selectedTicketId} tickets={tickets} />
    </main>
  );
}

// ---------------------------------------------------------------- left ---

function QueuePanel({
  tickets,
  error,
  selectedId,
}: {
  tickets: TicketListItem[] | null;
  error: string | null;
  selectedId?: string;
}) {
  const [statusFilter, setStatusFilter] = useState("all");

  const filtered = useMemo(() => {
    return (tickets ?? []).filter((t) => statusFilter === "all" || t.status === statusFilter);
  }, [tickets, statusFilter]);

  const health = useMemo(() => {
    const byUrgency = { high: 0, medium: 0, low: 0 };
    for (const t of tickets ?? []) byUrgency[urgencyBucket(t.urgency_score)]++;
    return byUrgency;
  }, [tickets]);

  return (
    <div className="flex w-full shrink-0 flex-col border-b border-border bg-card md:w-96 md:border-b-0 md:border-r">
      <div className="flex items-center justify-between gap-2 border-b border-border px-5 py-4">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Queue</h1>
          <p className="text-sm text-muted-foreground">
            <span className="font-data">{(tickets ?? []).length}</span> tickets, sorted by breach risk
          </p>
        </div>
        <Link href="/tickets/new" className={buttonVariants({ size: "sm" })}>
          New ticket
        </Link>
      </div>

      <div className="grid grid-cols-3 gap-px border-b border-border bg-border">
        {(["high", "medium", "low"] as const).map((bucket) => (
          <div key={bucket} className="bg-card px-3 py-2.5">
            <div className={cn("font-data text-xl font-semibold", SIGNAL_TEXT[bucket])}>
              {health[bucket]}
            </div>
            <div className="text-xs text-muted-foreground capitalize">{bucket} urgency</div>
          </div>
        ))}
      </div>

      <div className="border-b border-border px-5 py-2.5">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="w-full rounded-sm border border-border bg-transparent px-2 py-1.5 text-sm text-foreground"
        >
          <option value="all">All statuses</option>
          <option value="new">New</option>
          <option value="classified">Classified</option>
          <option value="drafted">Drafted</option>
          <option value="resolved">Resolved</option>
          <option value="escalated">Escalated</option>
        </select>
      </div>

      {error && (
        <p role="alert" className="px-5 py-3 text-sm text-destructive">
          {error}
        </p>
      )}

      {tickets === null && !error ? (
        <div className="flex flex-col gap-px p-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-12 animate-pulse bg-muted" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <p className="px-5 py-6 text-sm text-muted-foreground">No tickets match this filter.</p>
      ) : (
        <ul className="max-h-[70vh] overflow-y-auto md:max-h-[calc(100vh-11.5rem)]">
          {filtered.map((t) => {
            const breachRisk = breachRiskBucket(t.breach_risk_score);
            const active = t.id === selectedId;
            return (
              <li key={t.id} className="border-b border-border">
                <Link
                  href={`/tickets/${t.id}`}
                  className={cn(
                    "flex flex-col gap-1 border-l-4 px-4 py-3 text-sm hover:bg-accent",
                    breachRisk ? SIGNAL_BORDER[breachRisk] : "border-l-transparent",
                    active && "bg-accent"
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium capitalize">{t.category ?? "uncategorized"}</span>
                    <span className="font-data text-xs text-muted-foreground">{formatAge(t.created_at)} ago</span>
                  </div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-data text-xs text-muted-foreground">{t.id.slice(0, 8)}</span>
                    <span className="text-xs text-muted-foreground capitalize">{t.status}</span>
                  </div>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

// ------------------------------------------------ center + right shell ---

type Mode = "view" | "editing" | "escalating";

function TicketAndContext({ ticketId, tickets }: { ticketId?: string; tickets: TicketListItem[] | null }) {
  const [ticket, setTicket] = useState<TicketDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<Mode>("view");
  const [editedText, setEditedText] = useState("");
  const [escalationNote, setEscalationNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<ResolveAction | null>(null);

  function load(id: string) {
    getTicket(id)
      .then((t) => {
        setTicket(t);
        setEditedText(t.draft?.draft_text ?? "");
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load ticket"));
  }

  // The parent keys this component by ticketId (`key={selectedTicketId}`),
  // so a ticket switch remounts it and every useState above already starts
  // fresh — this effect only has to kick off the initial load.
  useEffect(() => {
    if (ticketId) load(ticketId);
  }, [ticketId]);

  if (!ticketId) {
    return <QueueOverview tickets={tickets} />;
  }

  if (error) {
    return (
      <div className="flex-1 px-6 py-8">
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      </div>
    );
  }

  if (!ticket) {
    return (
      <div className="flex flex-1 flex-col gap-3 px-6 py-8">
        <div className="h-6 w-40 animate-pulse bg-muted" />
        <div className="h-24 w-full animate-pulse bg-muted" />
        <div className="h-32 w-full animate-pulse bg-muted" />
      </div>
    );
  }

  const resolvable = ticket.status !== "resolved" && ticket.status !== "escalated";
  const traced = ticket.status !== "new";
  const stages: TraceStage[] = [
    { key: "redact", label: "Redacted", done: traced },
    { key: "classify", label: "Classified", done: traced, detail: ticket.category ?? undefined },
    { key: "score", label: "Scored", done: traced, detail: ticket.breach_risk_score !== null ? `risk ${ticket.breach_risk_score.toFixed(2)}` : undefined },
    { key: "retrieve", label: "Retrieved", done: traced, detail: ticket.draft ? `${ticket.draft.sources.length} source(s)` : undefined },
    { key: "draft", label: "Drafted", done: traced, detail: ticket.draft ? formatPct(ticket.draft.confidence) + " conf." : undefined },
    { key: "route", label: "Routed", done: traced, detail: ticket.specialist_flagged ? "specialist" : traced ? "standard" : undefined },
  ];

  async function submit(action: ResolveAction) {
    setActionError(null);
    setSubmitting(true);
    try {
      await resolveTicket(ticketId!, action, {
        finalText: action === "edit" ? editedText : undefined,
        escalationNote: action === "escalate" ? escalationNote : undefined,
      });
      setMode("view");
      setOutcome(action);
      load(ticketId!);
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Action failed, please try again");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <div className="flex min-w-0 flex-1 flex-col border-b border-border md:border-b-0 md:border-r">
        {/* Header */}
        <div className="flex items-center justify-between gap-3 border-b border-border px-6 py-4">
          <div className="flex items-center gap-3">
            <div>
              <h2 className="font-data text-xl font-semibold">{ticket.id.slice(0, 8)}</h2>
              <p className="text-sm text-muted-foreground">{ticket.customer_masked_identifier}</p>
            </div>
            <Badge variant="outline" className="rounded-sm capitalize">
              {ticket.channel}
            </Badge>
          </div>
          <Badge variant="outline" className="rounded-sm capitalize">
            {ticket.status}
          </Badge>
        </div>

        {/* Pipeline trace */}
        <div className="border-b border-border px-6 py-5">
          <PipelineTrace stages={stages} />
        </div>

        {ticket.specialist_flagged && (
          <div role="alert" className="flex items-start gap-3 border-b border-l-4 border-border border-l-signal-high bg-signal-high/10 px-6 py-3 text-sm">
            <Badge className="shrink-0 rounded-sm border-transparent bg-signal-high/20 text-signal-high">
              Needs specialist review
            </Badge>
            <span className="text-muted-foreground">
              {ticket.decision_reason ?? "The system flagged this draft as needing careful review."}
            </span>
          </div>
        )}

        {/* Customer message */}
        <div className="border-b border-border px-6 py-5">
          <div className="mb-2 text-sm font-semibold">Customer message</div>
          <p className="text-base leading-relaxed">{ticket.raw_text}</p>
        </div>

        {/* Draft */}
        <div className="flex-1 px-6 py-5">
          {ticket.draft ? (
            <>
              <div className="mb-2 flex items-center justify-between">
                <span className="text-sm font-semibold">AI draft reply</span>
                <span className="font-data text-xs text-muted-foreground">
                  confidence {formatPct(ticket.draft.confidence)}
                </span>
              </div>
              {mode === "editing" ? (
                <Textarea
                  value={editedText}
                  onChange={(e) => setEditedText(e.target.value)}
                  rows={7}
                  className="rounded-sm text-base"
                />
              ) : (
                <p className="border-l-4 border-l-primary bg-card p-4 text-base leading-relaxed">
                  {ticket.draft.draft_text}
                </p>
              )}
            </>
          ) : (
            <p className="border border-dashed border-border p-4 text-base text-muted-foreground">
              No AI draft yet — still processing, or retrieval found nothing relevant to ground a reply on.
            </p>
          )}

          {mode === "escalating" && (
            <div className="mt-3">
              <label className="mb-1 block text-sm text-muted-foreground">
                Escalation note
              </label>
              <Textarea
                value={escalationNote}
                onChange={(e) => setEscalationNote(e.target.value)}
                rows={3}
                placeholder="Why is this being escalated?"
                className="rounded-sm text-base"
              />
            </div>
          )}

          {actionError && (
            <p role="alert" className="mt-2 text-sm text-destructive">
              {actionError}
            </p>
          )}

          {outcome && (
            <div role="status" className="mt-4 border-l-4 border-l-signal-low bg-card p-4 text-sm">
              <p className="font-medium">
                {outcome === "approve" && "Reply approved and sent."}
                {outcome === "edit" && "Edited reply sent."}
                {outcome === "escalate" && "Ticket escalated."}
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                {outcome === "approve" && "The cited sources were promoted — they'll rank higher for similar tickets."}
                {outcome === "edit" && "A correction signal was recorded and the cited sources were demoted."}
                {outcome === "escalate" && "Routed for specialist attention. Retrieval ranking was left unchanged."}
              </p>
              <Link href="/admin/audit-log" className="mt-2 inline-block text-sm text-primary underline-offset-2 hover:underline">
                View in audit log
              </Link>
            </div>
          )}

          {resolvable && ticket.draft && (
            <div className="mt-5 flex flex-wrap gap-2">
              {mode === "view" && (
                <>
                  <Button onClick={() => submit("approve")} disabled={submitting}>
                    Approve draft
                  </Button>
                  <Button variant="outline" onClick={() => setMode("editing")} disabled={submitting}>
                    Edit then send
                  </Button>
                  <Button variant="destructive" onClick={() => setMode("escalating")} disabled={submitting}>
                    Escalate
                  </Button>
                </>
              )}
              {mode === "editing" && (
                <>
                  <Button onClick={() => submit("edit")} disabled={submitting || !editedText.trim()}>
                    {submitting ? "Sending…" : "Send edited reply"}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => {
                      setMode("view");
                      setEditedText(ticket.draft?.draft_text ?? "");
                    }}
                    disabled={submitting}
                  >
                    Cancel
                  </Button>
                </>
              )}
              {mode === "escalating" && (
                <>
                  <Button variant="destructive" onClick={() => submit("escalate")} disabled={submitting}>
                    {submitting ? "Escalating…" : "Confirm escalation"}
                  </Button>
                  <Button variant="outline" onClick={() => setMode("view")} disabled={submitting}>
                    Cancel
                  </Button>
                </>
              )}
            </div>
          )}
        </div>
      </div>

      <ContextPanel ticket={ticket} />
    </>
  );
}

// ---------------------------------------------------- center, no selection ---

function QueueOverview({ tickets }: { tickets: TicketListItem[] | null }) {
  const stats = useMemo(() => {
    const rows = tickets ?? [];
    return {
      total: rows.length,
      highRisk: rows.filter((t) => breachRiskBucket(t.breach_risk_score) === "high").length,
      awaitingReview: rows.filter((t) => t.status === "drafted").length,
      resolved: rows.filter((t) => t.status === "resolved").length,
    };
  }, [tickets]);

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-8 px-6 py-16">
      <div className="flex flex-col items-center gap-3 text-center">
        <Inbox className="size-8 text-muted-foreground" strokeWidth={1.5} />
        <div>
          <h2 className="text-lg font-semibold">Select a ticket to begin</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Pick one from the queue to inspect its pipeline trace, cited sources, and draft.
          </p>
        </div>
      </div>

      {tickets && tickets.length > 0 && (
        <div className="grid w-full max-w-xl grid-cols-2 gap-px border border-border bg-border sm:grid-cols-4">
          <div className="bg-background px-4 py-4 text-center">
            <div className="font-data text-2xl font-semibold">{stats.total}</div>
            <div className="text-xs text-muted-foreground">Total tickets</div>
          </div>
          <div className="bg-background px-4 py-4 text-center">
            <div className={cn("font-data text-2xl font-semibold", SIGNAL_TEXT.high)}>{stats.highRisk}</div>
            <div className="text-xs text-muted-foreground">High breach risk</div>
          </div>
          <div className="bg-background px-4 py-4 text-center">
            <div className={cn("font-data text-2xl font-semibold", SIGNAL_TEXT.medium)}>{stats.awaitingReview}</div>
            <div className="text-xs text-muted-foreground">Awaiting review</div>
          </div>
          <div className="bg-background px-4 py-4 text-center">
            <div className={cn("font-data text-2xl font-semibold", SIGNAL_TEXT.low)}>{stats.resolved}</div>
            <div className="text-xs text-muted-foreground">Resolved</div>
          </div>
        </div>
      )}
    </div>
  );
}

// --------------------------------------------------------------- right ---

function ContextPanel({ ticket }: { ticket: TicketDetail }) {
  const retrievalTerm = ticket.avg_retrieval_similarity !== null ? 0.6 * ticket.avg_retrieval_similarity : null;
  const categoryTerm = ticket.category_confidence !== null ? 0.4 * ticket.category_confidence : null;
  const confBucket = confidenceBucket(ticket.draft?.confidence ?? null);

  return (
    <div className="w-full shrink-0 bg-card md:w-[360px]">
      {/* Confidence breakdown */}
      {ticket.draft && (
        <div className="border-b border-border px-5 py-5">
          <div className="mb-3 text-sm font-semibold">Confidence breakdown</div>

          <div className={cn("font-data text-3xl font-bold", SIGNAL_TEXT[confBucket])}>
            {formatPct(ticket.draft.confidence)}
          </div>
          <div className="mt-2 h-1.5 w-full bg-border">
            <div
              className={cn("h-full", SIGNAL_DOT[confBucket])}
              style={{ width: `${Math.round((ticket.draft.confidence ?? 0) * 100)}%` }}
            />
          </div>

          <div className="mt-4 flex flex-col gap-2 font-data text-xs">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Retrieval similarity × 0.6</span>
              <span>{retrievalTerm !== null ? retrievalTerm.toFixed(2) : "—"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Category confidence × 0.4</span>
              <span>{categoryTerm !== null ? categoryTerm.toFixed(2) : "—"}</span>
            </div>
          </div>
        </div>
      )}

      {/* Sources */}
      {ticket.draft && ticket.draft.sources.length > 0 && (
        <div className="border-b border-border px-5 py-5">
          <div className="mb-3 text-sm font-semibold">Cited sources ({ticket.draft.sources.length})</div>
          <div className="flex flex-col gap-2">
            {ticket.draft.sources.map((s) => (
              <details key={s.chunk_id} className="border border-border bg-background p-2.5 text-sm">
                <summary className="cursor-pointer font-medium">{s.document_title}</summary>
                <p className="mt-1.5 text-sm text-muted-foreground">{s.content}</p>
              </details>
            ))}
          </div>
        </div>
      )}

      {/* Customer history */}
      <div className="px-5 py-5">
        <div className="mb-3 text-sm font-semibold">Customer history ({ticket.customer_history.length})</div>
        {ticket.customer_history.length === 0 ? (
          <p className="text-sm text-muted-foreground">First-time customer — no prior tickets.</p>
        ) : (
          <ul className="flex flex-col gap-2 text-sm">
            {ticket.customer_history.map((h) => (
              <li key={h.id} className="flex justify-between">
                <span className="capitalize">{h.category ?? "uncategorized"}</span>
                <span className="capitalize text-muted-foreground">{h.status}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
