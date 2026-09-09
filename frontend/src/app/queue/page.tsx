"use client";

import { useMemo, useState } from "react";

type Urgency = "high" | "medium" | "low";
type BreachRisk = "high" | "medium" | "low";
type Status = "new" | "classified" | "drafted" | "resolved" | "escalated";

type MockTicket = {
  id: string;
  maskedCustomerId: string;
  category: string;
  urgency: Urgency;
  breachRisk: BreachRisk;
  ageMinutes: number;
  status: Status;
};

// Static placeholder rows for the Day 1 scaffold — this page isn't wired to
// GET /tickets yet (that happens once the classification/breach-risk
// pipeline exists in later days).
const MOCK_TICKETS: MockTicket[] = [
  { id: "TCK-1042", maskedCustomerId: "cust_***881", category: "dispute", urgency: "high", breachRisk: "high", ageMinutes: 54, status: "drafted" },
  { id: "TCK-1041", maskedCustomerId: "cust_***224", category: "account_lock", urgency: "high", breachRisk: "medium", ageMinutes: 12, status: "new" },
  { id: "TCK-1039", maskedCustomerId: "cust_***510", category: "payment_failure", urgency: "medium", breachRisk: "high", ageMinutes: 130, status: "classified" },
  { id: "TCK-1035", maskedCustomerId: "cust_***097", category: "refund_delay", urgency: "medium", breachRisk: "medium", ageMinutes: 40, status: "drafted" },
  { id: "TCK-1030", maskedCustomerId: "cust_***662", category: "general_query", urgency: "low", breachRisk: "low", ageMinutes: 8, status: "new" },
  { id: "TCK-1024", maskedCustomerId: "cust_***331", category: "refund_delay", urgency: "low", breachRisk: "medium", ageMinutes: 200, status: "escalated" },
];

const URGENCY_STYLES: Record<Urgency, string> = {
  high: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
  medium: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
  low: "bg-neutral-100 text-neutral-600 dark:bg-neutral-800 dark:text-neutral-400",
};

const BREACH_RISK_STYLES: Record<BreachRisk, string> = {
  high: "border-red-500 text-red-700 dark:text-red-300",
  medium: "border-amber-500 text-amber-700 dark:text-amber-300",
  low: "border-neutral-400 text-neutral-500",
};

const BREACH_RISK_ORDER: Record<BreachRisk, number> = { high: 0, medium: 1, low: 2 };

function formatAge(minutes: number): string {
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}m ago`;
}

export default function QueuePage() {
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [urgencyFilter, setUrgencyFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");

  const categories = useMemo(
    () => Array.from(new Set(MOCK_TICKETS.map((t) => t.category))),
    []
  );

  const tickets = useMemo(() => {
    return MOCK_TICKETS.filter(
      (t) =>
        (categoryFilter === "all" || t.category === categoryFilter) &&
        (urgencyFilter === "all" || t.urgency === urgencyFilter) &&
        (statusFilter === "all" || t.status === statusFilter)
    ).sort((a, b) => BREACH_RISK_ORDER[a.breachRisk] - BREACH_RISK_ORDER[b.breachRisk]);
  }, [categoryFilter, urgencyFilter, statusFilter]);

  const health = useMemo(() => {
    const byUrgency = { high: 0, medium: 0, low: 0 };
    const byBreachRisk = { high: 0, medium: 0, low: 0 };
    for (const t of MOCK_TICKETS) {
      byUrgency[t.urgency]++;
      byBreachRisk[t.breachRisk]++;
    }
    return { byUrgency, byBreachRisk };
  }, []);

  return (
    <main className="mx-auto flex max-w-5xl flex-1 flex-col gap-6 px-4 py-8">
      <div>
        <h1 className="text-xl font-semibold">Ticket queue</h1>
        <p className="text-sm text-neutral-500">
          Sorted by breach-risk score, not raw urgency alone.
        </p>
      </div>

      {/* Queue health strip */}
      <div className="flex flex-wrap gap-3 rounded-lg border border-neutral-200 p-3 text-sm dark:border-neutral-800">
        <span className="font-medium text-neutral-500">Urgency:</span>
        <span className="text-red-600 dark:text-red-400">{health.byUrgency.high} high</span>
        <span className="text-amber-600 dark:text-amber-400">{health.byUrgency.medium} medium</span>
        <span className="text-neutral-500">{health.byUrgency.low} low</span>
        <span className="mx-2 text-neutral-300 dark:text-neutral-700">|</span>
        <span className="font-medium text-neutral-500">Breach risk:</span>
        <span className="text-red-600 dark:text-red-400">{health.byBreachRisk.high} high</span>
        <span className="text-amber-600 dark:text-amber-400">{health.byBreachRisk.medium} medium</span>
        <span className="text-neutral-500">{health.byBreachRisk.low} low</span>
      </div>

      {/* Filter bar */}
      <div className="flex flex-wrap gap-3">
        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="rounded-md border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-transparent"
        >
          <option value="all">All categories</option>
          {categories.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>

        <select
          value={urgencyFilter}
          onChange={(e) => setUrgencyFilter(e.target.value)}
          className="rounded-md border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-transparent"
        >
          <option value="all">All urgency</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-md border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-transparent"
        >
          <option value="all">All statuses</option>
          <option value="new">New</option>
          <option value="classified">Classified</option>
          <option value="drafted">Drafted</option>
          <option value="resolved">Resolved</option>
          <option value="escalated">Escalated</option>
        </select>
      </div>

      {/* Ticket list */}
      {tickets.length === 0 ? (
        <p className="py-12 text-center text-sm text-neutral-500">All caught up.</p>
      ) : (
        <div className="overflow-hidden rounded-lg border border-neutral-200 dark:border-neutral-800">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-neutral-200 bg-neutral-50 text-xs uppercase text-neutral-500 dark:border-neutral-800 dark:bg-neutral-900">
              <tr>
                <th className="px-4 py-2">Ticket</th>
                <th className="px-4 py-2">Customer</th>
                <th className="px-4 py-2">Category</th>
                <th className="px-4 py-2">Urgency</th>
                <th className="px-4 py-2">Breach risk</th>
                <th className="px-4 py-2">Age</th>
                <th className="px-4 py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {tickets.map((t) => (
                <tr
                  key={t.id}
                  className="border-b border-neutral-100 last:border-0 dark:border-neutral-800"
                >
                  <td className="px-4 py-2 font-mono text-xs">{t.id}</td>
                  <td className="px-4 py-2 font-mono text-xs text-neutral-500">
                    {t.maskedCustomerId}
                  </td>
                  <td className="px-4 py-2">{t.category}</td>
                  <td className="px-4 py-2">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${URGENCY_STYLES[t.urgency]}`}
                    >
                      {t.urgency}
                    </span>
                  </td>
                  <td className="px-4 py-2">
                    <span
                      className={`rounded-md border px-2 py-0.5 text-xs font-medium ${BREACH_RISK_STYLES[t.breachRisk]}`}
                    >
                      {t.breachRisk}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-neutral-500">{formatAge(t.ageMinutes)}</td>
                  <td className="px-4 py-2 capitalize">{t.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
