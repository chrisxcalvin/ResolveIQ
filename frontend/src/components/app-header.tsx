"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { clearTokens } from "@/lib/api";

const NAV_LINKS = [
  { href: "/queue", label: "Queue" },
  { href: "/admin/coaching", label: "Coaching" },
  { href: "/admin/audit-log", label: "Audit log" },
];

export function AppHeader() {
  const pathname = usePathname();
  const router = useRouter();

  // "/" (the marketing landing page) and /portal (the public customer
  // surface, Phase 7) each have their own header, kept fully separate from
  // this agent-only one rather than branching one component three ways.
  if (pathname === "/login" || pathname === "/" || pathname.startsWith("/portal")) return null;

  return (
    <header className="sticky top-0 z-10 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
      <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-4">
        <div className="flex items-center gap-6">
          <Link href="/queue" className="flex items-center gap-2 font-semibold tracking-tight">
            <span className="flex h-6 w-6 items-center justify-center rounded-md bg-primary text-xs font-bold text-primary-foreground">
              R
            </span>
            ResolveIQ
          </Link>
          <nav className="flex items-center gap-1">
            {NAV_LINKS.map((link) => {
              const active = pathname === link.href;
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                    active
                      ? "bg-accent text-accent-foreground"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground"
                  }`}
                >
                  {link.label}
                </Link>
              );
            })}
          </nav>
        </div>

        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            clearTokens();
            router.push("/login");
          }}
        >
          <LogOut className="size-3.5" />
          Sign out
        </Button>
      </div>
    </header>
  );
}
