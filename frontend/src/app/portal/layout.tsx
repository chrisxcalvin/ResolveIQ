"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { usePortalCustomerId, clearPortalCustomerId } from "@/lib/portal-api";

export default function PortalLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const customerId = usePortalCustomerId();
  const signedIn = pathname !== "/portal" && customerId !== null;

  return (
    <div className="flex min-h-full flex-1 flex-col">
      <header className="border-b border-border">
        <div className="mx-auto flex h-14 max-w-3xl items-center justify-between px-4">
          <Link href="/portal" className="flex items-center gap-2 font-semibold tracking-tight">
            <span className="flex h-6 w-6 items-center justify-center rounded-md bg-primary text-xs font-bold text-primary-foreground">
              R
            </span>
            ResolveIQ Support
          </Link>
          {signedIn && (
            <button
              type="button"
              onClick={() => {
                clearPortalCustomerId();
                router.push("/portal");
              }}
              className="text-sm text-muted-foreground underline-offset-2 hover:underline"
            >
              Switch customer
            </button>
          )}
        </div>
      </header>
      {children}
    </div>
  );
}
