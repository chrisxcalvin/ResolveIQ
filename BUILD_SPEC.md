# ResolveIQ — Build Spec for Claude Code

**Purpose of this document:** hand this to Claude Code as the working brief for finishing ResolveIQ. It covers bug fixes, testing, real data, database migration, deployment, a UI overhaul, a customer-facing portal, and honest benchmarking. Work through it in the phase order given — later phases assume earlier ones are done. Ask for clarification only where explicitly marked; otherwise use the specified defaults.

**Context Claude Code needs first:** read the existing codebase structure before making changes. The current stack is FastAPI (async) + LangGraph + Celery/Redis + PostgreSQL 16 with pgvector + Next.js (App Router) + Tailwind. Classification is TF-IDF + Logistic Regression (scikit-learn). Drafting uses a locally fine-tuned Qwen2.5-0.5B (LoRA/Unsloth) for routine tickets and Llama 3.3 70B via Groq for urgent ones. Embeddings are all-MiniLM-L6-v2. Everything currently runs natively via WSL2 Ubuntu (not Docker) — Postgres, Redis, API, worker, and frontend all run as local processes.

**Standing requirement — a checkpoint after every phase:** once a phase's work is verifiably done (tests passing, the change actually running), stop and write a short explanation of it addressed to the person building this — Chris — in the voice of a blunt, technical engineering manager grilling a candidate in an interview. Do not write it as a changelog or a summary of diffs. For each meaningful thing built in that phase, answer, in plain spoken language:

* What did you actually build, in one or two sentences a non-implementer could follow?
* Why this approach, and what else did you consider or rule out?
* What's the failure mode if this were wrong or missing — what breaks, and how would you notice?
* What's the one follow-up question a sharp interviewer would ask next, and what's the honest answer?
If a phase touches more than one distinct piece of work (e.g. two bugs, or data + retraining), give each its own short Q\&A rather than one blended paragraph. Keep the tone direct and unpolished — this is a rehearsal artifact for Chris to actually study and be able to answer cold in an interview, not documentation for a README. Save each phase's checkpoint as its own file, e.g. `docs/checkpoints/phase-1.md`, `docs/checkpoints/phase-2.md`, etc., so they accumulate into an interview-prep set by the end.

\---

## Phase 1 — Fix known bugs (do this first, before anything else)

1. **Phone-number redaction gap.** The PII redaction regex requires a full 3-3-4 digit grouping and misses 7-digit local-format numbers (e.g. `555-0142`). Locate the phone regex in the redaction module and broaden it to catch local-format numbers, while confirming it still doesn't false-positive on things like ticket IDs, dollar amounts, or dates. Add explicit test cases for both the original bug and the fix (feeds into Phase 2).
2. **Double-resolve race condition.** `resolve\_ticket` currently checks that a draft exists but never checks the ticket's current status, so two agents acting on the same ticket concurrently can both succeed, producing contradictory resolution records. Add a status check (and ideally a `SELECT ... FOR UPDATE` or an optimistic-concurrency version column) so a second resolve attempt on an already-resolved ticket fails cleanly with a clear error, not a silent overwrite.

Do not touch anything else in this phase — keep it scoped to these two fixes so they're easy to verify independently.

**Checkpoint:** write `docs/checkpoints/phase-1.md` per the standing requirement above, covering the redaction fix and the race-condition fix as two separate Q\&As.

\---

## Phase 2 — Testing

No automated tests exist yet; every bug found so far was caught by manual live testing. Add a `pytest` suite covering, at minimum:

* **Redaction patterns**: email, card number, name (spaCy NER), and the phone-number cases from Phase 1 (both the bug case and the fix).
* **Decision/routing thresholds**: confidence formula (`0.6 × retrieval similarity + 0.4 × classifier confidence`), the specialist-review trigger (confidence < 0.35, or category = dispute with urgency ≥ 0.75), and the zero-chunks-returned refusal path.
* **Retrieval-boost math**: approval multiplies boost by 1.05, edit multiplies by 0.85, both clamped to \[0.1, 3.0] — test the clamp boundaries specifically, not just the happy path.
* **Double-resolve guard** from Phase 1.

Then run a **basic concurrency test**: fire N simultaneous ticket submissions (start with N=10) at the running API and confirm the pipeline holds up — no dropped tickets, no corrupted state, Celery worker doesn't deadlock. This directly answers the "what happens under load" question the project has never been tested against.

**Checkpoint:** write `docs/checkpoints/phase-2.md`. Cover the testing strategy as a whole (what's tested and, honestly, what still isn't) plus the concurrency test result specifically — including what N=10 does and doesn't prove, since a sharp interviewer will ask about scale beyond that.

\---

## Phase 3 — Real data

**Problem:** every dataset currently in use is synthetic or hand-authored (template-generated classifier data with train/test leakage producing a fake 1.000 accuracy; hand-written KB articles; hand-written fine-tuning triples). There is no evidence any trained component works on anything resembling real text.

**Fix: use the CFPB Consumer Complaint Database.** This is a real, public, free, continuously-updated U.S. government dataset of 2M+ real consumer complaint narratives against banks, credit card issuers, lenders, and fintechs — a very close real-world analog to fintech support tickets. It's available as a bulk CSV/JSON download and via API, with fields including `Product`, `Sub-product`, `Issue`, `Sub-issue`, `Consumer complaint narrative`, `Company`, `State`, `Submitted via`, and `Company response`.

Do this:

1. Pull the CFPB dataset (filter to rows where `Consumer complaint narrative` is non-empty — only a subset of complaints have the free-text narrative field populated).
2. Map CFPB `Product`/`Issue` categories to ResolveIQ's existing 5 ticket categories as closely as possible (e.g. `Credit card`, `Checking or savings account`, `Money transfer, virtual currency, or money service`, `Debt collection`, `Credit reporting` → map onto whatever the current 5-class taxonomy is; adjust the taxonomy slightly if a cleaner mapping emerges, but keep it to 5 classes so the rest of the pipeline doesn't need rework).
3. Re-train the category classifier on this real data with a **proper train/test split** — split by complaint, and check there's no near-duplicate leakage across the split (unlike the template-generated data, this is real independent text, so leakage risk is much lower, but verify with a duplicate/near-duplicate check before trusting the split).
4. Report the new held-out accuracy honestly, whatever it is (expect something meaningfully below 1.000 — that's the point, and it's a stronger number to defend in an interview).
5. Leave the **SLA breach-risk classifier** as synthetic/rule-based — there's no public ground truth for breach risk, so this one is legitimately synthetic by necessity. Note this distinction clearly in code comments/docs so it isn't confused with the category classifier's data source.
6. Optionally: use a sample of real CFPB narratives (rather than hand-written tickets) as the input side of the fine-tuning triples for the cheap-tier drafting model, keeping the grounded-reply side authored/reviewed by you, so the model at least learns from realistic input phrasing.
7. Leave the knowledge-base articles as authored content (this is legitimate — a real company would author its own KB), but consider expanding past 20 articles if time allows, since 60 chunks is thin for a retrieval eval.

Document (in a `DATA.md` or similar) exactly which parts are real (classifier training/eval data) versus synthetic-by-necessity (SLA risk, KB articles) versus authored (fine-tuning replies). This honesty is itself a positive interview signal — don't obscure it.

**Checkpoint:** write `docs/checkpoints/phase-3.md`. Be explicit about the real-vs-synthetic-vs-authored breakdown and the honest new accuracy number — this is the checkpoint most likely to get pressure-tested in an interview ("how do you know your data is representative"), so the failure-mode and follow-up-question answers matter most here.

\---

## Phase 4 — Database migration (move off native WSL2 to a real external database)

**Current state:** Postgres 16 + pgvector and Redis both run as native installs inside a WSL2 Ubuntu distro, alongside the API/worker/frontend running directly on Windows. Nothing is externally reachable, and the setup isn't reproducible from a clean machine.

**Target:** a managed, externally-hosted database, reachable from anywhere, with zero manual OS-level setup required to reproduce.

Recommended:

|Component|Recommendation|Why|
|-|-|-|
|Postgres + pgvector|**Neon** (neon.tech)|Serverless Postgres with native pgvector support, generous free tier, instant provisioning, and branching (spin up an isolated DB branch for testing migrations — a good thing to mention in an interview). Supabase is a solid alternative if you want built-in auth/storage bundled in, but Neon is the more direct, lower-friction swap for a plain Postgres+pgvector setup.|
|Redis (Celery broker)|**Upstash**|Serverless Redis with a free tier, works over REST/TCP from anywhere, no server to manage — pairs naturally with a serverless Postgres choice.|

Migration steps:

1. Provision a Neon project and database; enable the `pgvector` extension (`CREATE EXTENSION IF NOT EXISTS vector;`).
2. Point Alembic at the Neon connection string; run the existing 2 migrations against it fresh — this also validates the migrations are actually reproducible from empty, which they've never been tested to be.
3. Migrate/re-seed data: since most current data is about to be replaced with real CFPB-derived data (Phase 3) anyway, do this **after** Phase 3, seeding Neon directly with the new, real dataset rather than migrating the old synthetic rows.
4. Provision Upstash Redis; update the Celery broker/backend URLs.
5. Update environment variables/config (`DATABASE\_URL`, `REDIS\_URL`) to point at the hosted services; remove the WSL2-specific setup instructions from any README once this is confirmed working.
6. Verify pgvector index performance on Neon at the current KB size (60 chunks — trivial, but confirm the `HNSW` or `IVFFlat` index type in use is actually created on the hosted instance, not just assumed).

This gives a concrete, correct answer to "which database do you use and why" in an interview: Postgres+pgvector, chosen because it keeps relational and vector data in one engine, hosted on Neon for reproducibility and serverless scaling, with the actual schema (`users`, `customers`, `tickets`, `ticket\_drafts`, `ticket\_resolutions`, `kb\_documents`/`kb\_chunks`, `correction\_signals`, `audit\_log`) to walk through if asked.

**Checkpoint:** write `docs/checkpoints/phase-4.md`. Include the schema walkthrough and a direct answer to "why Postgres+pgvector instead of a separate vector DB like Pinecone or Weaviate" — that's the standard follow-up question for this exact architecture choice.

\---

## Phase 5 — Deployment

Docker Desktop was unstable on the dev machine, which is why services moved to native WSL2. Deployment does **not** require Docker Desktop or resolving that instability — most of these platforms build directly from source.

1. **API + Celery worker**: deploy to **Railway** or **Render**. Both build directly from a `Dockerfile` or buildpack without needing Docker Desktop locally — the build happens on their infrastructure, not the dev machine. Set `DATABASE\_URL` (Neon) and `REDIS\_URL` (Upstash) as environment variables there.
2. **Frontend**: deploy the Next.js app to **Vercel** — this is close to a one-command deploy from the existing repo.
3. Confirm the local-GPU-dependent piece (the LoRA-fine-tuned Qwen2.5-0.5B for cheap-tier drafting) has a deployment story: either (a) host it on a small GPU instance (e.g. a Modal or Replicate endpoint) and call it over HTTP from the deployed API, or (b) for the deployed/demo version only, route all tickets through the Groq-hosted Llama 3.3 70B and keep the local fine-tuned model as a documented "this is how cost-based routing would work with a self-hosted cheap tier" component that you can explain and show code for, without it needing to run in the live deployment. Pick whichever is less effort — option (b) is fine for a portfolio deployment as long as it's described honestly in the README, not implied to be running.
4. Once deployed, do a fresh end-to-end run against the live URL (same style as the existing verified run) and record the result for the README/portfolio writeup.
5. CI/CD (GitHub Actions running the Phase 2 pytest suite on push) is a good next step once the above is stable, but not a blocker for having a live, linkable deployment.

**Checkpoint:** write `docs/checkpoints/phase-5.md`. Cover the deployment topology (what runs where, and why split across Railway/Render/Vercel/Neon/Upstash rather than one host) and be direct about the GPU/local-model tradeoff decision made in step 3 — that's a deliberate scope cut, not an oversight, and should be explainable as one.

\---

## Phase 6 — UI overhaul (replace the generic default look)

**Problem to fix:** current UI reads as an unstyled/default scaffold — generic system font, no considered layout, nothing that signals this is an operational tool built with intent.

**Design direction — do not default to a generic SaaS-card look, a dark-mode-with-neon-accent look, or a warm-cream-with-serif look. Build this instead:**

**Concept:** ResolveIQ is an operations console for support agents working under time pressure, not a marketing site. The product's actual differentiator is that AI reasoning is inspectable — every draft shows its cited sources, computed confidence, and pipeline stage rather than hiding behind a black-box chat bubble. The UI should make that inspectability the visual point: dense, functional, legible at speed — closer to a trading terminal or an ops dashboard than a landing page.

**Typography:**

* UI text / labels / body: **Archivo** (a grotesk sans with real character, not the default system-ui/Inter look).
* Data, IDs, timestamps, confidence scores, ticket IDs: **IBM Plex Mono** — using a monospace face specifically for *data* values (not decoration) makes numbers scannable and signals "this is real operational data," which is an intentional, content-driven choice, not a generic monospace-for-labels tic.
* Two-family type system only. No serif anywhere — this isn't an editorial/marketing product.

**Color (base palette, 6 named values):**

* Background: `#101418` (near-black slate — deliberately not pure `#000`/`#0B0B0B`)
* Surface (panels, rows): `#171C22`
* Border/hairline: `#2A313A`
* Text primary: `#E8ECEF`
* Text secondary: `#8B96A3`
* Accent (primary actions only — buttons, active states, links): `#4C8BF5`

Status/signal colors are used **functionally only** (urgency, confidence, breach-risk badges) — never decoratively elsewhere:

* High urgency / low confidence: `#E5484D`
* Medium: `#E5A82E`
* Low urgency / resolved / healthy: `#3FB27F`

**Layout:**

* Three-panel console layout, not a card grid: left = ticket queue (compact table rows sorted by breach-risk score, not cards — density matters more than whitespace here), center = ticket detail with the LangGraph pipeline stages shown as a visible horizontal trace (redacted → classified → scored → retrieved → drafted → routed), right = context panel showing cited KB chunks, the confidence formula breakdown (retrieval similarity component + classifier confidence component, not just a single number), and customer history.
* Hairline dividers between rows/panels, not drop shadows or rounded card borders. Zero or minimal border-radius — this is a console, not a marketing page.
* No animated card hover effects, no gradient washes, no all-caps tracked-out eyebrow labels above sections, no middle-dot-joined meta strings, no arrow (→) appended to buttons/links — these are the generic AI-generated-UI tells and none of them serve this product.
* One deliberate motion moment only, if any: the pipeline-stage trace animating left-to-right as a ticket is processed (this directly visualizes the real pipeline execution — motion tied to actual state change, not decorative).

**Voice/copy:** plain, operational language from the agent's point of view — "Escalate," "Approve draft," "Needs specialist review," not marketing language. Errors state what happened and what to do, they don't apologize.

Apply this to: the agent queue view, the ticket detail view, the admin audit log view, and the live ticket-submission page. Keep it consistent across all four rather than styling any one page in isolation.

**Checkpoint:** write `docs/checkpoints/phase-6.md`. This one should defend the design *decisions*, not describe the visuals — why a three-panel console over a chat UI, why the pipeline trace is shown rather than hidden, why monospace is used only for data. A technical interviewer asking about the UI is usually really asking whether you can justify a product decision, not whether it looks nice.

\---

## Phase 7 — Customer-facing portal

**Problem:** the project currently only has a support-agent side. There's no way to demo the full loop — a customer submitting a real query and getting a real answer back — which means in an interview you're describing half the system instead of showing it.

**Scope — keep this tightly bounded, it's a demo surface, not a second product:**

1. **Dummy customer profiles.** Seed 8–10 synthetic customers with a name, an account reference, and 2–3 past resolved tickets each (reuse CFPB-derived tickets from Phase 3 where sensible). This is what you "log in as" during a demo.
2. **Customer auth — deliberately minimal.** No real signup/password/email-verification flow. A simple "select a demo customer" session picker is fine, and is honest to describe as intentionally simplified for demo purposes — don't spend real effort here, it teaches nothing new and isn't what anyone will ask about.
3. **Ticket submission form.** Public-facing page: subject, description, account reference (pre-filled from the selected demo customer). Submits into the exact same pipeline the agent side already uses — no separate code path.
4. **Live status view — use polling, not WebSockets.** A "my ticket" page that polls every few seconds and shows the ticket moving through the same pipeline stages the agent/admin UI already visualizes (redacted → classified → scored → retrieved → drafted → routed → resolved), mirrored in a customer-appropriate, non-internal way (don't expose internal confidence scores or agent notes to the customer view — only status and, once resolved, the final reply). Polling over WebSockets is a deliberate, defensible tradeoff here (resolution isn't sub-second, so persistent-connection overhead isn't worth it) — note this reasoning in the Phase 7 checkpoint.
5. **Fast-path approval, not full auto-send, for high-confidence FAQ tickets.** When a ticket is classified high-confidence with an exact KB match (no account-specific lookup required — e.g. limits, policy, timelines, not "my specific transaction"), the draft is generated and queued for the agent as **flagged for one-click approval**, so it clears the queue in seconds rather than sitting in the normal wait, but a human still approves every outbound message — no ticket bypasses human review by default. State this design choice explicitly in code comments: it's a compliance and trust decision, not a technical limitation.
6. **Optional, off-by-default true auto-resolve.** Add a config flag, e.g. `AUTO\_RESOLVE\_THRESHOLD`, gated to a narrow slice of genuinely static, non-account-specific FAQs where confidence and KB match are both very high. When enabled, those tickets can resolve with no human touch — but mark them distinctly in the audit log (`resolved\_by: ai\_auto` vs `resolved\_by: agent`) so the audit trail always shows whether a human was involved. Keep this flag **off** for the default/demo state; it exists to show you thought about the tradeoff, not to be the demo default.
7. Reuse the Phase 6 design system (typography, color tokens, panel style) for the customer views — a simplified, less dense version of the same console aesthetic, not a different visual language. The customer-facing pages should feel like the same product, not a bolted-on marketing site.

**Checkpoint:** write `docs/checkpoints/phase-7.md`. Directly address: why polling over WebSockets, why fast-path-approval instead of full auto-send as the default, and what the `AUTO\_RESOLVE\_THRESHOLD` flag is for and why it's off by default. This phase is the one most likely to get the "couldn't a chatbot just answer everything" pushback — the checkpoint should include a ready answer to that, framed around what needs human judgment/action vs. what's a pure lookup.

\---

## Phase 8 — Benchmarking (measure real, honest numbers — don't estimate them)

**Problem:** there are currently no time-savings or efficiency numbers for this project, and inventing plausible-sounding ones (e.g. "reduces resolution time by 40%") is a serious interview risk — a single follow-up question about methodology will expose a fabricated number, which is far worse than having no number at all. Everything in this phase must be something you actually ran and can describe exactly how you ran it.

Do this, using the real CFPB-derived ticket data from Phase 3:

1. **Time-to-draft, measured directly from logs.** Instrument the pipeline to timestamp ticket-submitted and draft-ready, and report the real distribution (median, p95) across a batch run, not a single cherry-picked example.
2. **A small controlled manual-vs-assisted comparison, done by you.** Take 20–30 tickets from the real dataset. Time yourself two ways: (a) answering manually — searching the KB yourself and writing a reply from scratch, (b) using the system's draft and reviewing/editing it before sending. Log per-ticket time both ways. Report the result honestly, including the sample size, so it's presented as a small controlled test, not a production statistic.
3. **Draft quality via approval-rate, not a made-up satisfaction score.** Across the same test batch, report what fraction of drafts were approved as-is, lightly edited, or rejected outright. This is a real, defensible proxy for draft usefulness.
4. Write these results into a short `BENCHMARKS.md`, stating plainly: what was measured, exact methodology, sample size, and — critically — what this does *not* prove (e.g. "this is a controlled single-person test on historical data, not a production measurement across a real support team").

**Checkpoint:** write `docs/checkpoints/phase-8.md`. This is the phase where "what's your evidence" gets asked hardest — the checkpoint should model the honest version of that answer directly: what you measured, what you didn't, and why you didn't just state an estimated percentage instead.

\---

## Phase 9 — Stretch / future work (only after Phases 1–8 are solid)

* No ticket ownership/locking: `assigned\_agent\_id` exists in the schema but is never set. Add explicit claim/assignment so two agents don't work the same ticket blind.
* LangGraph pipeline is currently linear — specialist-flagged tickets aren't routed differently within the graph itself, only flagged as state. Add an actual branch so flagged tickets take a distinct path (e.g. mandatory secondary review step) rather than just carrying a flag.
* Expand the knowledge base past 20 articles once real complaint data (Phase 3) surfaces which issue categories are underrepresented.
* CI/CD via GitHub Actions (build + run Phase 2 test suite on every push).

\---

## Suggested order of operations for Claude Code

Work strictly in this order: **Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6 → Phase 7 → Phase 8 → Phase 9.** Each phase should end in a working, verifiable state (tests passing, a fresh end-to-end run succeeding) before moving to the next — don't let bug fixes, data changes, UI work, and the customer portal interleave, since that makes it hard to isolate what broke if something does. Phase 8 (benchmarking) is placed after the customer portal deliberately — it needs the full loop working to produce a meaningful manual-vs-assisted comparison.





update the original readme file as required

