"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ApiError,
  getAccessToken,
  getTicket,
  resolveTicket,
  type ResolveAction,
  type TicketDetail,
} from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";

type Mode = "view" | "editing" | "escalating";

function formatConfidence(confidence: number | null): string {
  if (confidence === null) return "n/a";
  return `${Math.round(confidence * 100)}%`;
}

export default function TicketDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const [ticket, setTicket] = useState<TicketDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<Mode>("view");
  const [editedText, setEditedText] = useState("");
  const [escalationNote, setEscalationNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<ResolveAction | null>(null);

  function load() {
    getTicket(id)
      .then((t) => {
        setTicket(t);
        setEditedText(t.draft?.draft_text ?? "");
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load ticket"));
  }

  useEffect(() => {
    if (!getAccessToken()) {
      router.push("/login");
      return;
    }
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, router]);

  async function submit(action: ResolveAction) {
    setActionError(null);
    setSubmitting(true);
    try {
      await resolveTicket(id, action, {
        finalText: action === "edit" ? editedText : undefined,
        escalationNote: action === "escalate" ? escalationNote : undefined,
      });
      setMode("view");
      setOutcome(action);
      load();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Action failed, please try again");
    } finally {
      setSubmitting(false);
    }
  }

  if (error) {
    return (
      <main className="mx-auto flex max-w-3xl flex-1 flex-col gap-4 px-4 py-8">
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
        <Link href="/queue" className="text-sm text-primary underline-offset-2 hover:underline">
          Back to queue
        </Link>
      </main>
    );
  }

  if (!ticket) {
    return (
      <main className="mx-auto flex max-w-3xl flex-1 flex-col gap-6 px-4 py-8">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-32 w-full" />
      </main>
    );
  }

  const resolvable = ticket.status !== "resolved" && ticket.status !== "escalated";

  return (
    <main className="mx-auto flex max-w-3xl flex-1 flex-col gap-6 px-4 py-8">
      <div>
        <Link href="/queue" className="text-sm text-muted-foreground underline-offset-2 hover:underline">
          ← Back to queue
        </Link>
        <div className="mt-2 flex items-baseline justify-between">
          <h1 className="text-xl font-semibold">Ticket {ticket.id.slice(0, 8)}</h1>
          <Badge variant="outline" className="capitalize">
            {ticket.status}
          </Badge>
        </div>
      </div>

      {/* The decide() node's own verdict — previously only visible by
          digging through the admin audit log, even though it's the single
          clearest signal that a draft shouldn't be trusted at face value. */}
      {ticket.specialist_flagged && (
        <Card
          role="alert"
          className="border-amber-300 bg-amber-50 dark:border-amber-900 dark:bg-amber-950/30"
        >
          <CardContent className="flex items-start gap-3 py-4 text-sm">
            <Badge className="border-transparent bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300">
              Flagged for specialist review
            </Badge>
            <span className="text-muted-foreground">
              {ticket.decision_reason ?? "The system flagged this draft as needing careful review."}
            </span>
          </CardContent>
        </Card>
      )}

      {/* Ticket summary */}
      <Card>
        <CardContent className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
          <div>
            <div className="text-xs uppercase text-muted-foreground">Customer</div>
            <div className="font-mono text-xs">{ticket.customer_masked_identifier}</div>
          </div>
          <div>
            <div className="text-xs uppercase text-muted-foreground">Category</div>
            <div>{ticket.category ?? "—"}</div>
          </div>
          <div>
            <div className="text-xs uppercase text-muted-foreground">Urgency</div>
            <div>{ticket.urgency_score === null ? "unscored" : ticket.urgency_score.toFixed(2)}</div>
          </div>
          <div>
            <div className="text-xs uppercase text-muted-foreground">Channel</div>
            <div className="capitalize">{ticket.channel}</div>
          </div>
        </CardContent>
      </Card>

      {/* Customer history (Feature 2) */}
      {ticket.customer_history.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-xs font-medium uppercase text-muted-foreground">
              Customer history ({ticket.customer_history.length} prior ticket
              {ticket.customer_history.length === 1 ? "" : "s"})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="flex flex-col gap-1 text-sm">
              {ticket.customer_history.map((h) => (
                <li key={h.id} className="flex justify-between text-muted-foreground">
                  <span>{h.category ?? "uncategorized"}</span>
                  <span className="capitalize">{h.status}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Original ticket text */}
      <div>
        <div className="mb-1 text-xs font-medium uppercase text-muted-foreground">Customer message</div>
        <Card>
          <CardContent className="text-sm">{ticket.raw_text}</CardContent>
        </Card>
      </div>

      {/* Draft */}
      {ticket.draft ? (
        <div>
          <div className="mb-1 flex items-center justify-between">
            <span className="text-xs font-medium uppercase text-muted-foreground">AI draft reply</span>
            <span className="text-xs text-muted-foreground">
              Confidence: {formatConfidence(ticket.draft.confidence)}
            </span>
          </div>

          {mode === "editing" ? (
            <Textarea
              value={editedText}
              onChange={(e) => setEditedText(e.target.value)}
              rows={6}
              className="text-sm"
            />
          ) : (
            <Card>
              <CardContent className="bg-muted/50 text-sm">{ticket.draft.draft_text}</CardContent>
            </Card>
          )}

          {ticket.draft.sources.length > 0 && (
            <div className="mt-2 flex flex-col gap-2">
              <span className="text-xs font-medium uppercase text-muted-foreground">Sources</span>
              {ticket.draft.sources.map((s) => (
                <details key={s.chunk_id} className="rounded-md border border-border p-2 text-xs">
                  <summary className="cursor-pointer font-medium text-muted-foreground">
                    {s.document_title}
                  </summary>
                  <p className="mt-1 text-muted-foreground">{s.content}</p>
                </details>
              ))}
            </div>
          )}
        </div>
      ) : (
        <Card className="border-dashed">
          <CardContent className="text-sm text-muted-foreground">
            No AI draft yet — the ticket may still be processing, or retrieval found nothing
            relevant to ground a reply on.
          </CardContent>
        </Card>
      )}

      {/* Escalation note input */}
      {mode === "escalating" && (
        <div>
          <Label className="mb-1 text-xs uppercase text-muted-foreground">Escalation note</Label>
          <Textarea
            value={escalationNote}
            onChange={(e) => setEscalationNote(e.target.value)}
            rows={3}
            placeholder="Why is this being escalated?"
          />
        </div>
      )}

      {actionError && (
        <p role="alert" className="text-sm text-destructive">
          {actionError}
        </p>
      )}

      {/* Outcome confirmation — without this the action buttons simply
          disappear once the ticket is no longer resolvable, which reads as
          nothing having happened. */}
      {outcome && (
        <Card
          role="status"
          className={
            outcome === "escalate"
              ? "border-amber-300 bg-amber-50 dark:border-amber-900 dark:bg-amber-950/30"
              : "border-emerald-300 bg-emerald-50 dark:border-emerald-900 dark:bg-emerald-950/30"
          }
        >
          <CardHeader>
            <CardTitle className="text-base">
              {outcome === "approve" && "Reply approved and sent"}
              {outcome === "edit" && "Edited reply sent"}
              {outcome === "escalate" && "Ticket escalated"}
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3 text-sm">
            <p className="text-muted-foreground">
              {outcome === "approve" &&
                "The cited knowledge base sources were promoted, so they rank higher for similar tickets."}
              {outcome === "edit" &&
                "A correction signal was recorded and the cited sources were demoted, so they rank lower for similar tickets."}
              {outcome === "escalate" &&
                "Routed for specialist attention. Retrieval ranking was left unchanged."}
            </p>
            <div className="flex flex-wrap gap-2">
              <Link href="/queue" className={buttonVariants({ size: "sm" })}>
                Back to queue
              </Link>
              <Link
                href="/admin/audit-log"
                className={buttonVariants({ size: "sm", variant: "outline" })}
              >
                View in audit log
              </Link>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Actions */}
      {resolvable && ticket.draft && (
        <div className="flex flex-wrap gap-2">
          {mode === "view" && (
            <>
              <Button onClick={() => submit("approve")} disabled={submitting}>
                Approve &amp; send
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
                {submitting ? "Sending..." : "Send edited reply"}
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
                {submitting ? "Escalating..." : "Confirm escalation"}
              </Button>
              <Button variant="outline" onClick={() => setMode("view")} disabled={submitting}>
                Cancel
              </Button>
            </>
          )}
        </div>
      )}
    </main>
  );
}
