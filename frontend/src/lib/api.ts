const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type TokenPair = {
  access_token: string;
  refresh_token: string;
  token_type: string;
};

export class ApiError extends Error {}

export async function login(email: string, password: string): Promise<TokenPair> {
  const res = await fetch(`${API_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  if (!res.ok) {
    throw new ApiError(
      res.status === 401 ? "Invalid email or password" : "Login failed, please try again"
    );
  }

  return res.json();
}

const ACCESS_TOKEN_KEY = "resolveiq_access_token";
const REFRESH_TOKEN_KEY = "resolveiq_refresh_token";

// Storing tokens in localStorage is a Day 1 scaffolding shortcut, not the
// final auth posture — revisit (httpOnly cookies) once the queue view
// depends on real authenticated requests.
export function storeTokens(tokens: TokenPair) {
  localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
  localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
}

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

// Access tokens live 15 minutes (backend ACCESS_TOKEN_EXPIRE_MINUTES). A
// ticket submission + review pass routinely runs longer than that, and the
// queue view polls every few seconds in the background — without a refresh
// path every request past the 15-minute mark 401s and the UI just goes
// silently stale. Concurrent 401s (e.g. a poll firing mid-refresh) share one
// in-flight refresh call rather than each racing their own.
let refreshInFlight: Promise<boolean> | null = null;

async function refreshTokens(): Promise<boolean> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;

  const res = await fetch(`${API_URL}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!res.ok) return false;

  const tokens: TokenPair = await res.json();
  storeTokens(tokens);
  return true;
}

function redirectToLogin() {
  clearTokens();
  if (typeof window !== "undefined") window.location.href = "/login";
}

async function rawFetch(path: string, init: RequestInit, token: string | null): Promise<Response> {
  return fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });
}

async function authedFetch(path: string, init: RequestInit = {}): Promise<Response> {
  let res = await rawFetch(path, init, getAccessToken());

  if (res.status === 401) {
    refreshInFlight ??= refreshTokens().finally(() => {
      refreshInFlight = null;
    });
    const refreshed = await refreshInFlight;

    if (!refreshed) {
      redirectToLogin();
      throw new ApiError("Session expired, please sign in again");
    }

    res = await rawFetch(path, init, getAccessToken());
  }

  if (!res.ok) {
    if (res.status === 401) redirectToLogin();
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

export type TicketListItem = {
  id: string;
  customer_masked_identifier: string;
  channel: string;
  category: string | null;
  urgency_score: number | null;
  breach_risk_score: number | null;
  status: string;
  created_at: string;
};

export type SourceOut = {
  chunk_id: string;
  document_title: string;
  content: string;
};

export type DraftOut = {
  id: string;
  draft_text: string;
  confidence: number | null;
  sources: SourceOut[];
};

export type CustomerHistoryItem = {
  id: string;
  category: string | null;
  status: string;
  created_at: string;
};

export type TicketDetail = {
  id: string;
  customer_id: string;
  customer_masked_identifier: string;
  channel: string;
  raw_text: string;
  redacted_text: string | null;
  category: string | null;
  urgency_score: number | null;
  breach_risk_score: number | null;
  status: string;
  created_at: string;
  draft: DraftOut | null;
  customer_history: CustomerHistoryItem[];
  specialist_flagged: boolean;
  decision_reason: string | null;
  category_confidence: number | null;
  avg_retrieval_similarity: number | null;
};

export type ResolveAction = "approve" | "edit" | "escalate";

export type ResolveResponse = {
  id: string;
  status: string;
  action: ResolveAction;
};

export type TicketCreated = {
  id: string;
  customer_id: string;
  channel: string;
  status: string;
  created_at: string;
};

export async function createTicket(input: {
  customerMaskedIdentifier: string;
  channel: string;
  rawText: string;
}): Promise<TicketCreated> {
  const res = await authedFetch("/tickets", {
    method: "POST",
    body: JSON.stringify({
      customer_masked_identifier: input.customerMaskedIdentifier,
      channel: input.channel,
      raw_text: input.rawText,
    }),
  });
  return res.json();
}

export async function listTickets(): Promise<TicketListItem[]> {
  const res = await authedFetch("/tickets");
  return res.json();
}

export async function getTicket(id: string): Promise<TicketDetail> {
  const res = await authedFetch(`/tickets/${id}`);
  return res.json();
}

export async function resolveTicket(
  id: string,
  action: ResolveAction,
  options: { finalText?: string; escalationNote?: string } = {}
): Promise<ResolveResponse> {
  const res = await authedFetch(`/tickets/${id}/resolve`, {
    method: "POST",
    body: JSON.stringify({
      action,
      final_text: options.finalText ?? null,
      escalation_note: options.escalationNote ?? null,
    }),
  });
  return res.json();
}

export type CoachingRow = {
  agent_id: string;
  agent_email: string;
  total_resolutions: number;
  avg_edit_distance: number | null;
  avg_resolution_minutes: number | null;
  escalation_rate: number;
};

export type AuditLogEntry = {
  id: string;
  ticket_id: string;
  event_type: string;
  detail: Record<string, unknown>;
  actor: string;
  created_at: string;
};

export async function getCoaching(): Promise<CoachingRow[]> {
  const res = await authedFetch("/admin/coaching");
  return res.json();
}

export async function getAuditLog(): Promise<AuditLogEntry[]> {
  const res = await authedFetch("/admin/audit-log");
  return res.json();
}
