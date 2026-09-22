"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError } from "@/lib/api";
import { listDemoCustomers, setPortalCustomerId, type PortalCustomer } from "@/lib/portal-api";

export default function PortalPickerPage() {
  const router = useRouter();
  const [customers, setCustomers] = useState<PortalCustomer[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listDemoCustomers()
      .then(setCustomers)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load demo customers"));
  }, []);

  function pick(customer: PortalCustomer) {
    setPortalCustomerId(customer.id);
    router.push("/portal/new");
  }

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-4 py-10">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Get help</h1>
        <p className="mt-1 text-base text-muted-foreground">
          This is a demo — pick one of the sample customers below to see how a real support
          request moves through the system, from submission to a reviewed reply.
        </p>
      </div>

      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}

      {customers === null && !error ? (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-16 animate-pulse bg-muted" />
          ))}
        </div>
      ) : (
        <div className="border border-border bg-card">
          {customers?.map((customer) => (
            <button
              key={customer.id}
              type="button"
              onClick={() => pick(customer)}
              className="flex w-full items-center justify-between border-b border-border px-5 py-4 text-left last:border-b-0 hover:bg-accent"
            >
              <span className="text-base font-medium">{customer.display_name}</span>
              {customer.account_reference && (
                <span className="font-data text-sm text-muted-foreground">
                  {customer.account_reference}
                </span>
              )}
            </button>
          ))}
        </div>
      )}
    </main>
  );
}
