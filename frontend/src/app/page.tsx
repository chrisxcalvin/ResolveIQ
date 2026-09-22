"use client";

import Image from "next/image";
import Link from "next/link";
import { motion } from "framer-motion";
import { buttonVariants } from "@/components/ui/button";
import { PipelineHeroCanvas } from "@/components/marketing/pipeline-hero-canvas";
import { cn } from "@/lib/utils";

const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0 },
};

function Reveal({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <motion.div
      initial="hidden"
      whileInView="show"
      viewport={{ once: true, margin: "-80px" }}
      variants={fadeUp}
      transition={{ duration: 0.6, ease: "easeOut" }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

const PIPELINE_STAGES: [string, string][] = [
  ["Redacted", "PII masked before any model call"],
  ["Classified", "Category + urgency, both scored"],
  ["Retrieved", "Real KB chunks, cited by title"],
  ["Drafted", "Confidence, not a guess"],
];

const TECH_STACK = ["FastAPI", "LangGraph", "Celery", "Next.js", "PostgreSQL + pgvector", "Groq"];

export default function LandingPage() {
  return (
    <div
      className="relative flex flex-1 flex-col"
      style={{
        backgroundImage: "radial-gradient(circle, #232a32 1px, transparent 1px)",
        backgroundSize: "32px 32px",
      }}
    >
      {/* Nav */}
      <header className="border-b border-border">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-5 sm:h-20 sm:px-8">
          <div className="flex items-center gap-2 text-base font-semibold tracking-tight sm:gap-2.5 sm:text-lg">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-primary text-xs font-bold text-primary-foreground sm:h-8 sm:w-8 sm:text-sm">
              R
            </span>
            ResolveIQ
          </div>
          <div className="flex items-center gap-3 sm:gap-5">
            <Link
              href="/portal"
              className="hidden text-base text-muted-foreground hover:text-foreground sm:inline"
            >
              Try the demo
            </Link>
            <Link href="/login" className={buttonVariants({ variant: "outline", size: "sm" })}>
              Agent sign in
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden border-b border-border">
        <div
          aria-hidden
          className="pointer-events-none absolute -top-40 left-1/2 h-[560px] w-[900px] -translate-x-1/2 rounded-full bg-primary/10 blur-[120px]"
        />
        <div className="relative mx-auto flex max-w-7xl flex-col gap-14 px-8 py-28 lg:py-36">
          <motion.div
            initial="hidden"
            animate="show"
            variants={fadeUp}
            transition={{ duration: 0.7, ease: "easeOut" }}
            className="flex max-w-4xl flex-col gap-8"
          >
            <h1 className="text-5xl font-semibold leading-[1.05] tracking-tight sm:text-6xl lg:text-7xl">
              AI reasoning your support team can actually inspect.
            </h1>
            <p className="max-w-2xl text-xl leading-relaxed text-muted-foreground sm:text-2xl">
              ResolveIQ drafts support replies with a real, visible pipeline — cited sources,
              computed confidence, breach-risk scoring — instead of a black-box chat bubble. A
              human still approves every message that goes out.
            </p>
            <div className="flex flex-wrap gap-4">
              <Link href="/portal" className={cn(buttonVariants({ size: "lg" }), "h-12 px-7 text-base")}>
                Try the live demo
              </Link>
              <Link
                href="/login"
                className={cn(buttonVariants({ variant: "outline", size: "lg" }), "h-12 px-7 text-base")}
              >
                Agent sign in
              </Link>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.2, ease: "easeOut" }}
            className="h-56 w-full border border-border bg-card sm:h-64 lg:h-72"
          >
            <PipelineHeroCanvas />
          </motion.div>
        </div>
      </section>

      {/* Feature 1: single pane */}
      <section className="relative overflow-hidden border-b border-border">
        <div
          aria-hidden
          className="pointer-events-none absolute top-1/2 right-0 h-[420px] w-[420px] -translate-y-1/2 translate-x-1/3 rounded-full bg-primary/6 blur-[100px]"
        />
        <div className="relative mx-auto grid max-w-7xl gap-16 px-8 py-28 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)] lg:items-center lg:py-32">
          <Reveal className="flex flex-col gap-5">
            <h2 className="text-4xl font-semibold tracking-tight sm:text-5xl">
              One panel, not four tabs.
            </h2>
            <p className="text-lg leading-relaxed text-muted-foreground">
              The queue, the ticket, and its full context — cited knowledge-base sources,
              confidence breakdown, customer history — sit in one console. An agent reviewing a
              draft never has to go dig for the information that draft depended on.
            </p>
          </Reveal>
          <Reveal>
            <div className="overflow-hidden border border-border bg-card shadow-2xl shadow-primary/5">
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
        <div className="mx-auto flex max-w-7xl flex-col gap-10 px-8 py-28 lg:py-32">
          <Reveal className="max-w-3xl">
            <h2 className="text-4xl font-semibold tracking-tight sm:text-5xl">
              Every draft shows its work.
            </h2>
            <p className="mt-5 text-lg leading-relaxed text-muted-foreground">
              Confidence isn’t one opaque number — it’s broken into its real components:
              retrieval similarity against the knowledge base, and classifier confidence, shown
              separately. The six-stage pipeline trace (redacted → classified → scored →
              retrieved → drafted → routed) is visible on every ticket, not hidden behind a
              status badge.
            </p>
          </Reveal>
          <Reveal className="grid grid-cols-2 gap-px overflow-hidden border border-border bg-border sm:grid-cols-4">
            {PIPELINE_STAGES.map(([label, detail]) => (
              <div key={label} className="bg-background px-6 py-6">
                <div className="text-base font-semibold">{label}</div>
                <div className="mt-1.5 text-sm text-muted-foreground">{detail}</div>
              </div>
            ))}
          </Reveal>
        </div>
      </section>

      {/* Feature 3: fast-path speed */}
      <section className="relative overflow-hidden border-b border-border">
        <div
          aria-hidden
          className="pointer-events-none absolute top-1/2 left-0 h-[420px] w-[420px] -translate-x-1/3 -translate-y-1/2 rounded-full bg-primary/6 blur-[100px]"
        />
        <div className="relative mx-auto grid max-w-7xl gap-16 px-8 py-28 lg:grid-cols-2 lg:items-center lg:py-32">
          <Reveal className="order-2 lg:order-1">
            <div className="border border-border bg-card p-8">
              <div className="mb-2.5 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                Standard ticket
              </div>
              <div className="text-lg leading-relaxed">
                Open ticket → read message → search knowledge base → write reply → send.
              </div>
              <div className="my-6 h-px bg-border" />
              <div className="mb-2.5 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                High-confidence FAQ match
              </div>
              <div className="text-lg leading-relaxed">
                Draft is already flagged for one-click approval. Agent reads it, hits{" "}
                <span className="font-data text-primary">Approve draft</span>.
              </div>
            </div>
          </Reveal>
          <Reveal className="order-1 flex flex-col gap-5 lg:order-2">
            <h2 className="text-4xl font-semibold tracking-tight sm:text-5xl">
              Fast-tracked, never auto-sent.
            </h2>
            <p className="text-lg leading-relaxed text-muted-foreground">
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
        <div className="mx-auto grid max-w-7xl gap-16 px-8 py-28 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)] lg:items-center lg:py-32">
          <Reveal className="flex flex-col gap-5">
            <h2 className="text-4xl font-semibold tracking-tight sm:text-5xl">
              See the whole loop, not half of it.
            </h2>
            <p className="text-lg leading-relaxed text-muted-foreground">
              A customer submits a real question through the public portal, watches it move
              through the same pipeline live, and gets back exactly what an agent approved — no
              internal confidence scores or routing details, just the reply.
            </p>
            <Link
              href="/portal"
              className={cn(buttonVariants({ variant: "outline", size: "lg" }), "mt-2 h-12 self-start px-7 text-base")}
            >
              Try it as a customer
            </Link>
          </Reveal>
          <Reveal>
            <div className="overflow-hidden border border-border bg-card shadow-2xl shadow-primary/5">
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
        <div className="mx-auto max-w-7xl px-8 py-20">
          <Reveal className="flex flex-col gap-5">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
              Built with
            </h2>
            <div className="flex flex-wrap gap-x-10 gap-y-3 font-data text-base text-muted-foreground">
              {TECH_STACK.map((tech) => (
                <span key={tech}>{tech}</span>
              ))}
            </div>
          </Reveal>
        </div>
      </section>

      {/* Footer CTA */}
      <section className="relative overflow-hidden">
        <div
          aria-hidden
          className="pointer-events-none absolute -bottom-40 left-1/2 h-[480px] w-[800px] -translate-x-1/2 rounded-full bg-primary/8 blur-[120px]"
        />
        <div className="relative mx-auto flex max-w-7xl flex-col items-start gap-5 px-8 py-32">
          <h2 className="text-4xl font-semibold tracking-tight sm:text-5xl">Try it yourself.</h2>
          <p className="max-w-xl text-lg text-muted-foreground">
            No signup — pick a demo customer, submit a real question, and watch it move through
            the pipeline.
          </p>
          <div className="mt-2 flex gap-4">
            <Link href="/portal" className={cn(buttonVariants({ size: "lg" }), "h-12 px-7 text-base")}>
              Try the live demo
            </Link>
            <Link
              href="/login"
              className={cn(buttonVariants({ variant: "outline", size: "lg" }), "h-12 px-7 text-base")}
            >
              Agent sign in
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
