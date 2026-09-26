"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ApiError } from "@/lib/api";
import { getPortalTicket, type PortalTicketStatus } from "@/lib/portal-api";
import { PipelineTrace, type TraceStage } from "@/components/pipeline-trace";

const POLL_INTERVAL_MS = 3000;
// Past this with the ticket still untouched, say why instead of leaving a
// silent spinner that looks like nothing is happening.
const SLOW_START_MS = 15_000;
const TERMINAL_STATUSES = ["resolved", "escalated"];

type StageDef = { key: string; label: string; done: (t: PortalTicketStatus) => boolean };

const STAGE_DEFS: StageDef[] = [
  { key: "received", label: "Received", done: () => true },
  { key: "reviewing", label: "Under review", done: (t) => t.status !== "new" },
  { key: "ready", label: "Response ready", done: (t) => t.status === "resolved" },
];

export default function PortalTicketStatusPage() {
  const { id } = useParams<{ id: string }>();
  const [ticket, setTicket] = useState<PortalTicketStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [slowStart, setSlowStart] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let handle: ReturnType<typeof setInterval> | null = null;
    const watchingSince = Date.now();

    const load = () =>
      getPortalTicket(id)
        .then((t) => {
          if (cancelled) return;
          setTicket(t);
          setSlowStart(t.status === "new" && Date.now() - watchingSince > SLOW_START_MS);
          if (TERMINAL_STATUSES.includes(t.status) && handle) {
            clearInterval(handle);
          }
        })
        .catch((err) => !cancelled && setError(err instanceof ApiError ? err.message : "Ticket not found"));

    load();
    handle = setInterval(load, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      if (handle) clearInterval(handle);
    };
  }, [id]);

  const done = ticket !== null && TERMINAL_STATUSES.includes(ticket.status);

  const stages: TraceStage[] = useMemo(() => {
    if (!ticket) return [];
    const activeIndex = done ? -1 : STAGE_DEFS.findIndex((def) => !def.done(ticket));
    return STAGE_DEFS.map((def, i) => ({
      key: def.key,
      label: def.label,
      done: def.done(ticket),
      active: i === activeIndex,
    }));
  }, [ticket, done]);

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-4 py-10">
      <div>
        <Link href="/portal/new" className="text-sm text-muted-foreground underline-offset-2 hover:underline">
          ← Submit another request
        </Link>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">Your request</h1>
        <p className="mt-1 font-data text-sm text-muted-foreground">{id.slice(0, 8)}</p>
      </div>

      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}

      {!ticket && !error && <div className="h-32 w-full animate-pulse bg-muted" />}

      {ticket && (
        <div className="border border-border bg-card">
          <div className="border-b border-border px-6 py-4">
            <p className="text-sm text-muted-foreground">
              {done
                ? ticket.status === "resolved"
                  ? "A reply is ready below."
                  : "This request needed a specialist and is being handled directly."
                : slowStart
                  ? "Still starting up — the first request after a quiet period can take up to a minute or two while our servers wake up. Your request is safely received."
                  : "We're reviewing your request..."}
            </p>
          </div>
          <div className="flex flex-col gap-5 px-6 py-5">
            <PipelineTrace stages={stages} />

            {ticket.final_reply && (
              <div className="border-l-4 border-l-signal-low bg-background p-4">
                <div className="mb-1.5 text-sm font-semibold">Reply</div>
                <p className="text-base leading-relaxed">{ticket.final_reply}</p>
              </div>
            )}
          </div>
        </div>
      )}
    </main>
  );
}
