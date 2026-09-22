"use client";

import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ApiError } from "@/lib/api";
import {
  getPortalTicket,
  submitPortalTicket,
  usePortalCustomerId,
  type PortalTicketStatus,
} from "@/lib/portal-api";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { PipelineTrace, type TraceStage } from "@/components/pipeline-trace";
import { cn } from "@/lib/utils";

const POLL_INTERVAL_MS = 1500;
const POLL_TIMEOUT_MS = 90_000;
const TERMINAL_STATUSES = ["resolved", "escalated"];

// Deliberately coarser than the agent-facing trace — no confidence
// percentages, no specialist-routing detail, nothing internal. A customer
// only needs to know their request arrived, is being worked, and when a
// real answer is ready.
type StageDef = { key: string; label: string; done: (t: PortalTicketStatus) => boolean };

const STAGE_DEFS: StageDef[] = [
  { key: "received", label: "Received", done: () => true },
  { key: "reviewing", label: "Under review", done: (t) => t.status !== "new" },
  { key: "ready", label: "Response ready", done: (t) => t.status === "resolved" },
];

export default function PortalNewTicketPage() {
  const router = useRouter();
  const customerId = usePortalCustomerId();

  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [ticket, setTicket] = useState<PortalTicketStatus | null>(null);
  const [watching, setWatching] = useState(false);
  const [timedOut, setTimedOut] = useState(false);

  const timers = useRef<ReturnType<typeof setInterval>[]>([]);

  useEffect(() => {
    if (customerId === null) {
      router.push("/portal");
    }
  }, [customerId, router]);

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
    if (!customerId) return;
    setError(null);
    setTimedOut(false);
    setTicket(null);
    setSubmitting(true);

    try {
      const created = await submitPortalTicket({
        customerId,
        subject: subject.trim(),
        description: description.trim(),
      });

      setWatching(true);
      const startedAt = Date.now();

      const poll = setInterval(async () => {
        try {
          const latest = await getPortalTicket(created.id);
          setTicket(latest);
          if (TERMINAL_STATUSES.includes(latest.status)) {
            stopPolling();
          } else if (Date.now() - startedAt > POLL_TIMEOUT_MS) {
            setTimedOut(true);
            stopPolling();
          }
        } catch {
          // transient read failure — the timeout above is the real backstop
        }
      }, POLL_INTERVAL_MS);

      timers.current = [poll];
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not submit your request");
    } finally {
      setSubmitting(false);
    }
  }

  const done = ticket !== null && TERMINAL_STATUSES.includes(ticket.status);

  const stages: TraceStage[] = useMemo(() => {
    const activeIndex = watching
      ? STAGE_DEFS.findIndex((def) => !(ticket ? def.done(ticket) : false))
      : -1;
    return STAGE_DEFS.map((def, i) => ({
      key: def.key,
      label: def.label,
      done: ticket ? def.done(ticket) : false,
      active: i === activeIndex,
    }));
  }, [ticket, watching]);

  if (!customerId) return null;

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-4 py-10">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Submit a request</h1>
        <p className="mt-1 text-base text-muted-foreground">
          Tell us what’s going on — a support agent reviews every response before it’s sent to
          you.
        </p>
      </div>

      <div className="border border-border bg-card">
        <div className="px-6 py-5">
          <form onSubmit={handleSubmit} className="flex flex-col gap-5">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="subject" className="text-sm">Subject</Label>
              <Input
                id="subject"
                required
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                placeholder="Payment issue, account access, refund status..."
                className="rounded-sm bg-background text-base"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="description" className="text-sm">What’s happening?</Label>
              <Textarea
                id="description"
                required
                rows={6}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe the issue in your own words..."
                className="rounded-sm bg-background text-base"
              />
            </div>

            {error && (
              <p role="alert" className="text-sm text-destructive">
                {error}
              </p>
            )}

            <Button type="submit" disabled={submitting || watching} className="self-start">
              {submitting ? "Submitting..." : watching ? "Processing..." : "Submit request"}
            </Button>
          </form>
        </div>
      </div>

      {(watching || ticket) && (
        <div className="border border-border bg-card">
          <div className="border-b border-border px-6 py-4">
            <h2 className="text-base font-semibold">Status</h2>
            <p className="mt-0.5 text-sm text-muted-foreground">
              {done
                ? ticket?.status === "resolved"
                  ? "A reply is ready below."
                  : "This request needed a specialist and is being handled directly."
                : timedOut
                  ? "Still working on it — check back shortly."
                  : "We're reviewing your request..."}
            </p>
          </div>
          <div className="flex flex-col gap-5 px-6 py-5">
            <PipelineTrace stages={stages} />

            {ticket?.final_reply && (
              <div className="border-l-4 border-l-signal-low bg-background p-4">
                <div className="mb-1.5 text-sm font-semibold">Reply</div>
                <p className="text-base leading-relaxed">{ticket.final_reply}</p>
              </div>
            )}

            {ticket && (
              <div className="flex flex-wrap gap-2 pt-1">
                <Link
                  href={`/portal/tickets/${ticket.id}`}
                  className={cn(buttonVariants({ variant: "outline" }))}
                >
                  View this request later
                </Link>
              </div>
            )}
          </div>
        </div>
      )}
    </main>
  );
}
