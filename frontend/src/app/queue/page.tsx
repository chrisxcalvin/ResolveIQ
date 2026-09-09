"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ApiError, getAccessToken, listTickets, type TicketListItem } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

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

const RISK_BADGE_CLASS: Record<RiskBucket, string> = {
  high: "border-transparent bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
  medium: "border-transparent bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
  low: "border-transparent bg-muted text-muted-foreground",
};

function formatAge(createdAt: string): string {
  const minutes = Math.max(0, Math.floor((Date.now() - new Date(createdAt).getTime()) / 60000));
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}m ago`;
}

export default function QueuePage() {
  const router = useRouter();
  const [tickets, setTickets] = useState<TicketListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [urgencyFilter, setUrgencyFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");

  useEffect(() => {
    if (!getAccessToken()) {
      router.push("/login");
      return;
    }

    let cancelled = false;
    const load = () =>
      listTickets()
        .then((rows) => {
          if (!cancelled) setTickets(rows);
        })
        .catch((err) => {
          if (!cancelled) {
            setError(err instanceof ApiError ? err.message : "Failed to load tickets");
          }
        });

    load();

    // Tickets are processed asynchronously by the worker, so a freshly
    // submitted one arrives here as `new` and becomes `drafted` seconds
    // later. Poll so that transition shows up without a manual refresh.
    const handle = setInterval(load, QUEUE_POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(handle);
    };
  }, [router]);

  const categories = useMemo(
    () => Array.from(new Set((tickets ?? []).map((t) => t.category).filter((c): c is string => !!c))),
    [tickets]
  );

  const filtered = useMemo(() => {
    return (tickets ?? []).filter(
      (t) =>
        (categoryFilter === "all" || t.category === categoryFilter) &&
        (urgencyFilter === "all" || urgencyBucket(t.urgency_score) === urgencyFilter) &&
        (statusFilter === "all" || t.status === statusFilter)
    );
  }, [tickets, categoryFilter, urgencyFilter, statusFilter]);

  const health = useMemo(() => {
    const byUrgency = { high: 0, medium: 0, low: 0 };
    for (const t of tickets ?? []) byUrgency[urgencyBucket(t.urgency_score)]++;
    return byUrgency;
  }, [tickets]);

  return (
    <main className="mx-auto flex max-w-5xl flex-1 flex-col gap-6 px-4 py-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Ticket queue</h1>
          <p className="text-sm text-muted-foreground">
            Sorted by breach-risk score, falling back to urgency for tickets not yet scored.
          </p>
        </div>
        <Link href="/tickets/new" className={buttonVariants({ size: "sm" })}>
          Submit a ticket
        </Link>
      </div>

      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}

      {tickets === null && !error ? (
        <div className="flex flex-col gap-3">
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-9 w-full max-w-md" />
          <Skeleton className="h-64 w-full" />
        </div>
      ) : (
        <>
          <Card>
            <CardContent className="flex flex-wrap items-center gap-3 text-sm">
              <span className="font-medium text-muted-foreground">Urgency:</span>
              <Badge className={RISK_BADGE_CLASS.high}>{health.high} high</Badge>
              <Badge className={RISK_BADGE_CLASS.medium}>{health.medium} medium</Badge>
              <Badge className={RISK_BADGE_CLASS.low}>{health.low} low</Badge>
            </CardContent>
          </Card>

          <div className="flex flex-wrap gap-3">
            <Select value={categoryFilter} onValueChange={(v) => v && setCategoryFilter(v)}>
              <SelectTrigger>
                <SelectValue placeholder="All categories" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All categories</SelectItem>
                {categories.map((c) => (
                  <SelectItem key={c} value={c}>
                    {c}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={urgencyFilter} onValueChange={(v) => v && setUrgencyFilter(v)}>
              <SelectTrigger>
                <SelectValue placeholder="All urgency" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All urgency</SelectItem>
                <SelectItem value="high">High</SelectItem>
                <SelectItem value="medium">Medium</SelectItem>
                <SelectItem value="low">Low</SelectItem>
              </SelectContent>
            </Select>

            <Select value={statusFilter} onValueChange={(v) => v && setStatusFilter(v)}>
              <SelectTrigger>
                <SelectValue placeholder="All statuses" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All statuses</SelectItem>
                <SelectItem value="new">New</SelectItem>
                <SelectItem value="classified">Classified</SelectItem>
                <SelectItem value="drafted">Drafted</SelectItem>
                <SelectItem value="resolved">Resolved</SelectItem>
                <SelectItem value="escalated">Escalated</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {filtered.length === 0 ? (
            <Card>
              <CardHeader>
                <CardTitle>All caught up</CardTitle>
                <CardDescription>No tickets match the current filters.</CardDescription>
              </CardHeader>
            </Card>
          ) : (
            <Card>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Ticket</TableHead>
                    <TableHead>Customer</TableHead>
                    <TableHead>Category</TableHead>
                    <TableHead>Urgency</TableHead>
                    <TableHead>Breach risk</TableHead>
                    <TableHead>Age</TableHead>
                    <TableHead>Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filtered.map((t) => {
                    const breachRisk = breachRiskBucket(t.breach_risk_score);
                    return (
                      <TableRow key={t.id}>
                        <TableCell className="font-mono text-xs">
                          <Link href={`/tickets/${t.id}`} className="text-primary underline-offset-2 hover:underline">
                            {t.id.slice(0, 8)}
                          </Link>
                        </TableCell>
                        <TableCell className="font-mono text-xs text-muted-foreground">
                          {t.customer_masked_identifier}
                        </TableCell>
                        <TableCell>{t.category ?? "—"}</TableCell>
                        <TableCell>
                          <Badge className={RISK_BADGE_CLASS[urgencyBucket(t.urgency_score)]}>
                            {t.urgency_score === null ? "unscored" : urgencyBucket(t.urgency_score)}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          {breachRisk === null ? (
                            <span className="text-xs text-muted-foreground">—</span>
                          ) : (
                            <Badge className={RISK_BADGE_CLASS[breachRisk]}>{breachRisk}</Badge>
                          )}
                        </TableCell>
                        <TableCell className="text-muted-foreground">{formatAge(t.created_at)}</TableCell>
                        <TableCell className="capitalize">{t.status}</TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </Card>
          )}
        </>
      )}
    </main>
  );
}
