"use client";

import Image from "next/image";
import Link from "next/link";
import { motion } from "framer-motion";
import { buttonVariants } from "@/components/ui/button";
import { PipelineHeroCanvas } from "@/components/marketing/pipeline-hero-canvas";
import { cn } from "@/lib/utils";

const fadeUp = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0 },
};

function Reveal({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <motion.div
      initial="hidden"
      whileInView="show"
      viewport={{ once: true, margin: "-80px" }}
      variants={fadeUp}
      transition={{ duration: 0.5, ease: "easeOut" }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

export default function LandingPage() {
  return (
    <div className="flex flex-1 flex-col">
      {/* Nav */}
      <header className="border-b border-border">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
          <div className="flex items-center gap-2 font-semibold tracking-tight">
            <span className="flex h-6 w-6 items-center justify-center rounded-md bg-primary text-xs font-bold text-primary-foreground">
              R
            </span>
            ResolveIQ
          </div>
          <div className="flex items-center gap-3">
            <Link href="/portal" className="text-sm text-muted-foreground hover:text-foreground">
              Try the demo
            </Link>
            <Link href="/login" className={buttonVariants({ variant: "outline", size: "sm" })}>
              Agent sign in
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="border-b border-border">
        <div className="mx-auto flex max-w-6xl flex-col gap-10 px-6 py-20">
          <motion.div
            initial="hidden"
            animate="show"
            variants={fadeUp}
            transition={{ duration: 0.6, ease: "easeOut" }}
            className="flex max-w-2xl flex-col gap-6"
          >
            <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">
              AI reasoning your support team can actually inspect.
            </h1>
            <p className="text-lg text-muted-foreground">
              ResolveIQ drafts support replies with a real, visible pipeline — cited sources,
              computed confidence, breach-risk scoring — instead of a black-box chat bubble.
              A human still approves every message that goes out.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link href="/portal" className={buttonVariants({ size: "lg" })}>
                Try the live demo
              </Link>
              <Link href="/login" className={buttonVariants({ variant: "outline", size: "lg" })}>
                Agent sign in
              </Link>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.15, ease: "easeOut" }}
            className="h-40 w-full border border-border bg-card sm:h-48"
          >
            <PipelineHeroCanvas />
          </motion.div>
        </div>
      </section>

      {/* Feature 1: single pane */}
      <section className="border-b border-border">
        <div className="mx-auto grid max-w-6xl gap-10 px-6 py-20 md:grid-cols-2 md:items-center">
          <Reveal className="flex flex-col gap-4">
            <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">
              One panel, not four tabs.
            </h2>
            <p className="text-base leading-relaxed text-muted-foreground">
              The queue, the ticket, and its full context — cited knowledge-base sources,
              confidence breakdown, customer history — sit in one console. An agent reviewing a
              draft never has to go dig for the information that draft depended on.
            </p>
          </Reveal>
          <Reveal>
            <div className="overflow-hidden border border-border bg-card">
              <Image
                src="/marketing/console-ticket-detail.png"
                alt="ResolveIQ agent console showing the ticket queue, pipeline trace, and confidence breakdown in one view"
                width={1600}
                height={1000}
                className="h-auto w-full"
              />
            </div>
          </Reveal>
        </div>
      </section>

      {/* Feature 2: inspectable, not a black box */}
      <section className="border-b border-border">
        <div className="mx-auto flex max-w-6xl flex-col gap-6 px-6 py-20">
          <Reveal className="max-w-2xl">
            <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">
              Every draft shows its work.
            </h2>
            <p className="mt-4 text-base leading-relaxed text-muted-foreground">
              Confidence isn’t one opaque number — it’s broken into its real components:
              retrieval similarity against the knowledge base, and classifier confidence, shown
              separately. The six-stage pipeline trace (redacted → classified → scored →
              retrieved → drafted → routed) is visible on every ticket, not hidden behind a
              status badge.
            </p>
          </Reveal>
          <Reveal className="grid grid-cols-2 gap-px border border-border bg-border sm:grid-cols-4">
            {[
              ["Redacted", "PII masked before any model call"],
              ["Classified", "Category + urgency, both scored"],
              ["Retrieved", "Real KB chunks, cited by title"],
              ["Drafted", "Confidence, not a guess"],
            ].map(([label, detail]) => (
              <div key={label} className="bg-background px-4 py-4">
                <div className="text-sm font-semibold">{label}</div>
                <div className="mt-1 text-xs text-muted-foreground">{detail}</div>
              </div>
            ))}
          </Reveal>
        </div>
      </section>

      {/* Feature 3: fast-path speed */}
      <section className="border-b border-border">
        <div className="mx-auto grid max-w-6xl gap-10 px-6 py-20 md:grid-cols-2 md:items-center">
          <Reveal className="order-2 flex flex-col gap-4 md:order-1">
            <div className="border border-border bg-card p-6">
              <div className="mb-2 text-sm font-semibold">Standard ticket</div>
              <div className="text-sm text-muted-foreground">
                Open ticket → read message → search knowledge base → write reply → send.
              </div>
              <div className="my-4 h-px bg-border" />
              <div className="mb-2 text-sm font-semibold">High-confidence FAQ match</div>
              <div className="text-sm text-muted-foreground">
                Draft is already flagged for one-click approval. Agent reads it, hits{" "}
                <span className="font-data text-primary">Approve draft</span>.
              </div>
            </div>
          </Reveal>
          <Reveal className="order-1 flex flex-col gap-4 md:order-2">
            <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">
              Fast-tracked, never auto-sent.
            </h2>
            <p className="text-base leading-relaxed text-muted-foreground">
              When a draft is high-confidence, low-urgency, and tightly matched to the knowledge
              base — the kind of question that’s really a policy lookup, not an account-specific
              case — it’s flagged for one-click approval. A human still approves every message.
              Nothing skips review by default.
            </p>
          </Reveal>
        </div>
      </section>

      {/* Feature 4: the full loop, portal */}
      <section className="border-b border-border">
        <div className="mx-auto grid max-w-6xl gap-10 px-6 py-20 md:grid-cols-2 md:items-center">
          <Reveal className="flex flex-col gap-4">
            <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">
              See the whole loop, not half of it.
            </h2>
            <p className="text-base leading-relaxed text-muted-foreground">
              A customer submits a real question through the public portal, watches it move
              through the same pipeline live, and gets back exactly what an agent approved —
              no internal confidence scores or routing details, just the reply.
            </p>
            <Link href="/portal" className={cn(buttonVariants({ variant: "outline" }), "self-start")}>
              Try it as a customer
            </Link>
          </Reveal>
          <Reveal>
            <div className="overflow-hidden border border-border bg-card">
              <Image
                src="/marketing/portal-resolved.png"
                alt="Customer portal showing a resolved support request with the reply, and no internal AI details"
                width={1400}
                height={900}
                className="h-auto w-full"
              />
            </div>
          </Reveal>
        </div>
      </section>

      {/* Built with */}
      <section className="border-b border-border">
        <div className="mx-auto max-w-6xl px-6 py-16">
          <Reveal className="flex flex-col gap-4">
            <h2 className="text-sm font-semibold text-muted-foreground">Built with</h2>
            <div className="flex flex-wrap gap-x-6 gap-y-2 font-data text-sm text-muted-foreground">
              {["FastAPI", "LangGraph", "Celery", "Next.js", "PostgreSQL + pgvector", "Groq"].map(
                (tech) => (
                  <span key={tech}>{tech}</span>
                )
              )}
            </div>
          </Reveal>
        </div>
      </section>

      {/* Footer CTA */}
      <section>
        <div className="mx-auto flex max-w-6xl flex-col items-start gap-4 px-6 py-20">
          <h2 className="text-2xl font-semibold tracking-tight">Try it yourself.</h2>
          <p className="max-w-xl text-base text-muted-foreground">
            No signup — pick a demo customer, submit a real question, and watch it move through
            the pipeline.
          </p>
          <div className="flex gap-3">
            <Link href="/portal" className={buttonVariants({ size: "lg" })}>
              Try the live demo
            </Link>
            <Link href="/login" className={buttonVariants({ variant: "outline", size: "lg" })}>
              Agent sign in
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
