import { useSyncExternalStore } from "react";
import { ApiError } from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// No bearer token, no refresh loop, no redirect-on-401 — there's no agent
// session here to expire or bounce to /login. Mirrors how lib/api.ts's own
// login() already talks to the backend before any token exists.
async function portalFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...init.headers,
    },
  });

  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // response wasn't JSON, keep the generic message
    }
    throw new ApiError(detail);
  }

  return res;
}

export type PortalCustomer = {
  id: string;
  display_name: string;
  account_reference: string | null;
};

export type PortalTicketCreated = {
  id: string;
  status: string;
  created_at: string;
};

export type PortalTicketStatus = {
  id: string;
  status: string;
  category: string | null;
  created_at: string;
  final_reply: string | null;
};

export type PortalTicketListItem = {
  id: string;
  status: string;
  category: string | null;
  created_at: string;
};

const PORTAL_CUSTOMER_KEY = "resolveiq_portal_customer_id";

// Deliberately separate localStorage key from the agent token keys in
// lib/api.ts — a portal "session" and an agent session must never collide
// or be confused for one another.
export function getPortalCustomerId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(PORTAL_CUSTOMER_KEY);
}

export function setPortalCustomerId(id: string) {
  localStorage.setItem(PORTAL_CUSTOMER_KEY, id);
}

export function clearPortalCustomerId() {
  localStorage.removeItem(PORTAL_CUSTOMER_KEY);
}

const noSubscription = () => () => {};

// localStorage is a browser-only API, so its value can't be read during
// render (SSR has no window) or synced via a plain useState+useEffect
// without either a hydration mismatch or a setState-in-effect warning —
// useSyncExternalStore is React's own answer to exactly this case: a
// server snapshot of `null`, then the real client value as soon as it's
// safe to read.
export function usePortalCustomerId(): string | null {
  return useSyncExternalStore(noSubscription, getPortalCustomerId, () => null);
}

export async function listDemoCustomers(): Promise<PortalCustomer[]> {
  const res = await portalFetch("/portal/customers");
  return res.json();
}

export async function submitPortalTicket(input: {
  customerId: string;
  subject: string;
  description: string;
}): Promise<PortalTicketCreated> {
  const res = await portalFetch("/portal/tickets", {
    method: "POST",
    body: JSON.stringify({
      customer_id: input.customerId,
      subject: input.subject,
      description: input.description,
    }),
  });
  return res.json();
}

export async function getPortalTicket(id: string): Promise<PortalTicketStatus> {
  const res = await portalFetch(`/portal/tickets/${id}`);
  return res.json();
}

export async function listPortalCustomerTickets(customerId: string): Promise<PortalTicketListItem[]> {
  const res = await portalFetch(`/portal/customers/${customerId}/tickets`);
  return res.json();
}
