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

export function clearTokens() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}
