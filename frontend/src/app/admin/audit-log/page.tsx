"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ChevronDownIcon } from "lucide-react";
import { ApiError, getAccessToken, getAuditLog, type AuditLogEntry } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Skeleton } from "@/components/ui/skeleton";

function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleString();
}

export default function AuditLogPage() {
  const router = useRouter();
  const [entries, setEntries] = useState<AuditLogEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!getAccessToken()) {
      router.push("/login");
      return;
    }
    getAuditLog()
      .then(setEntries)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Failed to load audit log")
      );
  }, [router]);

  return (
    <main className="mx-auto flex max-w-4xl flex-1 flex-col gap-6 px-4 py-8">
      <div>
        <Link href="/queue" className="text-sm text-muted-foreground underline-offset-2 hover:underline">
          ← Back to queue
        </Link>
        <h1 className="mt-2 text-xl font-semibold">Audit log</h1>
        <p className="text-sm text-muted-foreground">
          Every state transition — submission, drafting, and human resolution — with its
          reasoning data. Most recent 100 events.
        </p>
      </div>

      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}

      {entries === null && !error ? (
        <div className="flex flex-col gap-2">
          <Skeleton className="h-10 w-full rounded-sm" />
          <Skeleton className="h-10 w-full rounded-sm" />
          <Skeleton className="h-10 w-full rounded-sm" />
        </div>
      ) : entries && entries.length === 0 ? (
        <div className="border border-dashed border-border px-5 py-6">
          <p className="text-sm font-medium">No events recorded yet</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Ticket state transitions will show up here as they happen.
          </p>
        </div>
      ) : (
        entries && (
          <div className="border border-border">
            {entries.map((e) => (
              <Collapsible key={e.id} className="border-b border-border last:border-b-0">
                <CollapsibleTrigger className="group/trigger flex w-full cursor-pointer items-center justify-between gap-3 px-4 py-2.5 text-sm hover:bg-accent">
                  <span className="flex items-center gap-3">
                    <Badge variant="outline" className="rounded-sm capitalize">
                      {e.event_type}
                    </Badge>
                    <Link
                      href={`/tickets/${e.ticket_id}`}
                      onClick={(ev) => ev.stopPropagation()}
                      className="font-data text-xs text-muted-foreground underline-offset-2 hover:underline"
                    >
                      {e.ticket_id.slice(0, 8)}
                    </Link>
                  </span>
                  <span className="flex items-center gap-2 font-data text-xs text-muted-foreground">
                    {formatTimestamp(e.created_at)}
                    <ChevronDownIcon className="size-3.5 transition-transform group-data-[panel-open]/trigger:rotate-180" />
                  </span>
                </CollapsibleTrigger>
                <CollapsibleContent>
                  <div className="px-4 pb-3">
                    <pre className="overflow-x-auto border border-border bg-muted/40 p-2.5 font-data text-xs text-muted-foreground">
                      {JSON.stringify(e.detail, null, 2)}
                    </pre>
                  </div>
                </CollapsibleContent>
              </Collapsible>
            ))}
          </div>
        )
      )}
    </main>
  );
}
