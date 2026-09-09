"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ApiError, getAccessToken, getCoaching, type CoachingRow } from "@/lib/api";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

function formatPercent(ratio: number): string {
  return `${Math.round(ratio * 100)}%`;
}

function formatMinutes(minutes: number | null): string {
  if (minutes === null) return "—";
  if (minutes < 60) return `${Math.round(minutes)}m`;
  return `${(minutes / 60).toFixed(1)}h`;
}

export default function CoachingPage() {
  const router = useRouter();
  const [rows, setRows] = useState<CoachingRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!getAccessToken()) {
      router.push("/login");
      return;
    }
    getCoaching()
      .then(setRows)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Failed to load coaching data")
      );
  }, [router]);

  return (
    <main className="mx-auto flex max-w-4xl flex-1 flex-col gap-6 px-4 py-8">
      <div>
        <Link href="/queue" className="text-sm text-muted-foreground underline-offset-2 hover:underline">
          ← Back to queue
        </Link>
        <h1 className="mt-2 text-xl font-semibold">Agent coaching insights</h1>
        <p className="text-sm text-muted-foreground">
          Aggregated from resolution data already captured — edit distance, resolution time, and
          escalation rate per agent.
        </p>
      </div>

      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}

      {rows === null && !error ? (
        <Skeleton className="h-64 w-full" />
      ) : rows && rows.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>No resolutions recorded yet</CardTitle>
            <CardDescription>Coaching data will appear once agents start resolving tickets.</CardDescription>
          </CardHeader>
        </Card>
      ) : (
        rows && (
          <Card>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Agent</TableHead>
                  <TableHead>Resolutions</TableHead>
                  <TableHead>Avg edit distance</TableHead>
                  <TableHead>Avg resolution time</TableHead>
                  <TableHead>Escalation rate</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((r) => (
                  <TableRow key={r.agent_id}>
                    <TableCell>{r.agent_email}</TableCell>
                    <TableCell>{r.total_resolutions}</TableCell>
                    <TableCell>
                      {r.avg_edit_distance === null ? "—" : formatPercent(r.avg_edit_distance)}
                    </TableCell>
                    <TableCell>{formatMinutes(r.avg_resolution_minutes)}</TableCell>
                    <TableCell>{formatPercent(r.escalation_rate)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        )
      )}
    </main>
  );
}
