"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { ApiError, login, storeTokens } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

// Free-tier Render API can be asleep (15min idle) and take 30-60s+ to
// wake on the first request — with no indicator here, that just looks
// like a hung "Signing in..." button, easy to mistake for broken and
// navigate away from (which cancels the in-flight request for real).
const SLOW_SUBMIT_MS = 8_000;

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [slowSubmit, setSlowSubmit] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    setSlowSubmit(false);
    const slowTimer = setTimeout(() => setSlowSubmit(true), SLOW_SUBMIT_MS);
    try {
      const tokens = await login(email, password);
      storeTokens(tokens);
      router.push("/queue");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      clearTimeout(slowTimer);
      setSubmitting(false);
      setSlowSubmit(false);
    }
  }

  return (
    <main className="flex flex-1 items-center justify-center px-4">
      <div className="w-full max-w-sm border border-border bg-card">
        <div className="border-b border-border px-6 py-5">
          <h1 className="text-xl font-semibold tracking-tight">ResolveIQ</h1>
          <p className="mt-1 text-sm text-muted-foreground">Sign in to your agent account</p>
        </div>
        <div className="px-6 py-5">
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="email" className="text-sm">Email</Label>
              <Input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="rounded-sm bg-background text-base"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="password" className="text-sm">Password</Label>
              <Input
                id="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="rounded-sm bg-background text-base"
              />
            </div>

            {submitting && slowSubmit && (
              <p className="text-sm text-muted-foreground">
                Still working — our server may be waking up after sitting idle, this can take up
                to a minute. No need to retry.
              </p>
            )}

            {error && (
              <p role="alert" className="text-sm text-destructive">
                {error}
              </p>
            )}

            <Button type="submit" disabled={submitting} className="mt-2">
              {submitting ? "Signing in..." : "Sign in"}
            </Button>
          </form>

          <p className="mt-6 text-sm text-muted-foreground">
            No public sign-up — accounts are admin-provisioned.
          </p>
        </div>
      </div>
    </main>
  );
}
