"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ApiError,
  createTicket,
  getAccessToken,
  getTicket,
  type TicketDetail,
} from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

// The pipeline runs on the Celery worker, so the ticket lands as `new` and
// becomes `drafted` a few seconds later. Poll until it settles so the demo
// can watch the transition happen instead of refreshing by hand.
const POLL_INTERVAL_MS = 1500;
const POLL_TIMEOUT_MS = 90_000;
const TERMINAL_STATUSES = ["drafted", "resolved", "escalated"];

const SAMPLE_TICKET =
  "My payment failed but I can still see the charge pending on my statement, " +
  "was I actually charged?";

type Stage = {
  key: string;
  label: string;
  detail: (t: TicketDetail) => string | null;
};

// Mirrors app/pipeline/graph.py. Each stage reports done once the field it
// writes is present on the ticket.
const STAGES: Stage[] = [
  {
    key: "redact",
    label: "Redact PII",
    detail: (t) => (t.redacted_text ? "PII masked before any model call" : null),
  },
  {
    key: "classify",
    label: "Classify",
    detail: (t) =>
      t.category
        ? `${t.category} · urgency ${t.urgency_score?.toFixed(2) ?? "—"}`
        : null,
  },
  {
    key: "breach_risk",
    label: "Score breach risk",
    detail: (t) =>
      t.breach_risk_score !== null ? `breach risk ${t.breach_risk_score.toFixed(2)}` : null,
  },
  {
    key: "retrieve",
    label: "Retrieve sources",
    detail: (t) =>
      t.draft ? `${t.draft.sources.length} knowledge base chunk(s) cited` : null,
  },
  {
    key: "draft",
    label: "Draft reply",
    detail: (t) =>
      t.draft ? `confidence ${t.draft.confidence?.toFixed(2) ?? "—"}` : null,
  },
];

export default function NewTicketPage() {
  const router = useRouter();

  const [customerId, setCustomerId] = useState("cust_demo_001");
  const [channel, setChannel] = useState("email");
  const [rawText, setRawText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [ticket, setTicket] = useState<TicketDetail | null>(null);
  const [watching, setWatching] = useState(false);
  const [timedOut, setTimedOut] = useState(false);
  const [elapsed, setElapsed] = useState(0);

  const timers = useRef<ReturnType<typeof setInterval>[]>([]);

  useEffect(() => {
    if (!getAccessToken()) router.push("/login");
  }, [router]);

  // Clear any pending timers when the component goes away mid-poll.
  useEffect(() => {
    const handles = timers.current;
    return () => handles.forEach(clearInterval);
  }, []);

  function stopPolling() {
    timers.current.forEach(clearInterval);
    timers.current = [];
    setWatching(false);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setTimedOut(false);
    setTicket(null);
    setElapsed(0);
    setSubmitting(true);

    try {
      const created = await createTicket({
        customerMaskedIdentifier: customerId.trim(),
        channel,
        rawText: rawText.trim(),
      });

      setWatching(true);
      const startedAt = Date.now();

      const tick = setInterval(() => setElapsed(Date.now() - startedAt), 200);
      const poll = setInterval(async () => {
        try {
          const latest = await getTicket(created.id);
          setTicket(latest);
          if (TERMINAL_STATUSES.includes(latest.status)) {
            stopPolling();
          } else if (Date.now() - startedAt > POLL_TIMEOUT_MS) {
            setTimedOut(true);
            stopPolling();
          }
        } catch {
          // A transient read failure shouldn't kill the watch — the next
          // tick retries. The timeout above is the real backstop.
        }
      }, POLL_INTERVAL_MS);

      timers.current = [tick, poll];
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not submit the ticket");
    } finally {
      setSubmitting(false);
    }
  }

  const done = ticket !== null && TERMINAL_STATUSES.includes(ticket.status);
  const seconds = (elapsed / 1000).toFixed(1);

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-4 py-8">
      <div>
        <Link
          href="/queue"
          className="text-sm text-muted-foreground underline-offset-2 hover:underline"
        >
          ← Back to queue
        </Link>
        <h1 className="mt-2 text-xl font-semibold">Submit a ticket</h1>
        <p className="text-sm text-muted-foreground">
          Submits through the same public API a real channel would use. The pipeline runs on
          the worker, so you can watch the ticket move from <code>new</code> to{" "}
          <code>drafted</code> below.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Incoming message</CardTitle>
          <CardDescription>
            Write as the customer would. Include an email or card number to see redaction work.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="customer">Customer identifier</Label>
                <Input
                  id="customer"
                  required
                  value={customerId}
                  onChange={(e) => setCustomerId(e.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                  Reuse an identifier to build history for that customer.
                </p>
              </div>

              <div className="flex flex-col gap-1.5">
                <Label htmlFor="channel">Channel</Label>
                <Select value={channel} onValueChange={(v) => v && setChannel(v)}>
                  <SelectTrigger id="channel">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="email">Email</SelectItem>
                    <SelectItem value="chat">Chat</SelectItem>
                    <SelectItem value="form">Web form</SelectItem>
                    <SelectItem value="social">Social</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              <div className="flex items-center justify-between">
                <Label htmlFor="body">Message</Label>
                <button
                  type="button"
                  onClick={() => setRawText(SAMPLE_TICKET)}
                  className="text-xs text-muted-foreground underline-offset-2 hover:underline"
                >
                  Use sample message
                </button>
              </div>
              <Textarea
                id="body"
                required
                rows={6}
                value={rawText}
                onChange={(e) => setRawText(e.target.value)}
                placeholder="My payment failed but I was still charged..."
              />
            </div>

            {error && (
              <p role="alert" className="text-sm text-destructive">
                {error}
              </p>
            )}

            <Button type="submit" disabled={submitting || watching} className="self-start">
              {submitting ? "Submitting..." : watching ? "Processing..." : "Submit ticket"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {(watching || ticket) && (
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <CardTitle className="text-base">Pipeline</CardTitle>
              <div className="flex items-center gap-2">
                <Badge variant="outline">{ticket?.status ?? "new"}</Badge>
                <span className="text-xs tabular-nums text-muted-foreground">{seconds}s</span>
              </div>
            </div>
            <CardDescription>
              {done
                ? "Pipeline finished — the draft is ready for review."
                : timedOut
                  ? "Still processing after 90s. The worker may be busy or stopped."
                  : "Running on the Celery worker..."}
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <ol className="flex flex-col gap-2">
              {STAGES.map((stage) => {
                const detail = ticket ? stage.detail(ticket) : null;
                const complete = detail !== null;
                return (
                  <li key={stage.key} className="flex items-start gap-3 text-sm">
                    <span
                      aria-hidden
                      className={
                        "mt-1.5 size-2 shrink-0 rounded-full " +
                        (complete ? "bg-emerald-500" : "bg-muted-foreground/30")
                      }
                    />
                    <span className="flex flex-col">
                      <span className={complete ? "font-medium" : "text-muted-foreground"}>
                        {stage.label}
                      </span>
                      {detail && (
                        <span className="text-xs text-muted-foreground">{detail}</span>
                      )}
                    </span>
                  </li>
                );
              })}
            </ol>

            {timedOut && (
              <p role="alert" className="text-sm text-destructive">
                No result yet. Check that the Celery worker is running, then open the ticket
                from the queue.
              </p>
            )}

            {ticket && (
              <div className="flex flex-wrap gap-2 pt-1">
                <Link
                  href={`/tickets/${ticket.id}`}
                  aria-disabled={!done}
                  tabIndex={done ? undefined : -1}
                  className={cn(
                    buttonVariants({ size: "sm" }),
                    !done && "pointer-events-none opacity-50"
                  )}
                >
                  Open ticket
                </Link>
                <Link href="/queue" className={buttonVariants({ size: "sm", variant: "outline" })}>
                  Back to queue
                </Link>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </main>
  );
}
