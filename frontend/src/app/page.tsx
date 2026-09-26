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

const STANDARD_STEPS = ["Open ticket", "Read message", "Search knowledge base", "Write reply", "Send"];
const STEP_DELAY = 0.32;

// The pacing here is the actual point, not just decoration: standard-path
// steps reveal one at a time, slowly, because that's really five separate
// actions — then the fast-path result appears in one quick beat right
// after, dramatizing the speed difference the copy next to this describes
// instead of just stating it in words.
function FastPathComparison() {
  const faqDelay = STANDARD_STEPS.length * STEP_DELAY + 0.25;

  return (
    <motion.div
      initial="hidden"
      whileInView="show"
      viewport={{ once: true, margin: "-80px" }}
      className="border border-border bg-card p-8"
    >
      <div className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        Standard ticket
      </div>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-lg leading-relaxed">
        {STANDARD_STEPS.map((step, i) => (
          <span key={step} className="flex items-center gap-2">
            {i > 0 && (
              <motion.span
                variants={fadeUp}
                transition={{ duration: 0.3, delay: i * STEP_DELAY - 0.1 }}
                className="text-muted-foreground"
                aria-hidden
              >
                →
              </motion.span>
            )}
            <motion.span variants={fadeUp} transition={{ duration: 0.35, delay: i * STEP_DELAY }}>
              {step}
            </motion.span>
          </span>
        ))}
      </div>

      <div className="my-6 h-px bg-border" />

      <div className="mb-2.5 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        High-confidence FAQ match
      </div>
      <motion.div
        variants={{ hidden: { opacity: 0, scale: 0.97 }, show: { opacity: 1, scale: 1 } }}
        transition={{ duration: 0.2, delay: faqDelay, ease: "easeOut" }}
        className="text-lg leading-relaxed"
      >
        Draft is already flagged for one-click approval. Agent reads it, hits{" "}
        <motion.span
          variants={{ hidden: { opacity: 0 }, show: { opacity: 1 } }}
          transition={{ duration: 0.3, delay: faqDelay + 0.15 }}
          className="inline-block rounded-sm bg-primary/15 px-2 py-0.5 font-data text-primary"
        >
          Approve draft
        </motion.span>
      </motion.div>
    </motion.div>
  );
}

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

      {/* Hero — flows into Feature 1 with no hard border; the dot-grid
          background is continuous underneath both, and a hard line right
          after the canvas made that gap read as a dead stop rather than a
          transition. */}
      <section className="relative overflow-hidden">
        <div
          aria-hidden
          className="pointer-events-none absolute -top-40 left-1/2 h-[560px] w-[900px] -translate-x-1/2 rounded-full bg-primary/10 blur-[120px]"
        />
        <div className="relative mx-auto flex max-w-7xl flex-col gap-14 px-8 pt-28 pb-16 lg:pt-36 lg:pb-20">

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

          <motion.div
            aria-hidden
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.6, delay: 0.8 }}
            className="flex justify-center"
          >
            <motion.div
              animate={{ y: [0, 6, 0] }}
              transition={{ duration: 1.8, repeat: Infinity, ease: "easeInOut" }}
              className="text-muted-foreground"
            >
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <path d="M4 7l6 6 6-6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </motion.div>
          </motion.div>
        </div>
      </section>

      {/* Feature 1: single pane */}
      <section className="relative overflow-hidden border-b border-border">
        <div
          aria-hidden
          className="pointer-events-none absolute top-1/2 right-0 h-[420px] w-[420px] -translate-y-1/2 translate-x-1/3 rounded-full bg-primary/6 blur-[100px]"
        />
        <div className="relative mx-auto grid max-w-7xl gap-16 px-8 pt-16 pb-28 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)] lg:items-center lg:pt-20 lg:pb-32">
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
          <motion.div
            initial="hidden"
            whileInView="show"
            viewport={{ once: true, margin: "-80px" }}
            transition={{ staggerChildren: 0.12 }}
            className="grid grid-cols-2 gap-px overflow-hidden border border-border bg-border sm:grid-cols-4"
          >
            {/* Staggered, not a single block fade — these are sequential
                pipeline stages, so the reveal itself mirrors "one thing
                happens, then the next," not just a decorative entrance. */}
            {PIPELINE_STAGES.map(([label, detail]) => (
              <motion.div
                key={label}
                variants={fadeUp}
                transition={{ duration: 0.5, ease: "easeOut" }}
                className="bg-background px-6 py-6"
              >
                <div className="text-base font-semibold">{label}</div>
                <div className="mt-1.5 text-sm text-muted-foreground">{detail}</div>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* Feature 3: fast-path speed */}
      <section className="relative overflow-hidden border-b border-border">
        <div
          aria-hidden
          className="pointer-events-none absolute top-1/2 left-0 h-[420px] w-[420px] -translate-x-1/3 -translate-y-1/2 rounded-full bg-primary/6 blur-[100px]"
        />
        <div className="relative mx-auto grid max-w-7xl gap-16 px-8 py-28 lg:grid-cols-2 lg:items-center lg:py-32">
          <div className="order-2 lg:order-1">
            <FastPathComparison />
          </div>
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
