import type { Metadata } from "next";
import Link from "next/link";
import {
  ArrowRight,
  BrainCircuit,
  FlaskConical,
  Github,
  Scale,
  ScrollText,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";

import { PipelineDiagram } from "@/components/marketing/pipeline-diagram";
import { cn } from "@/lib/utils";

export const metadata: Metadata = {
  title: "ATLAS — The Trust Layer for Autonomous AI",
  description:
    "ATLAS decides whether an autonomous financial agent can be trusted to act — before it acts. Continuous trust scoring, policy-as-code, and pre-execution simulation.",
};

const NAV_LINKS = [
  { label: "Pipeline", href: "#pipeline" },
  { label: "Capabilities", href: "#capabilities" },
  { label: "How it works", href: "#how" },
];

interface Capability {
  icon: LucideIcon;
  title: string;
  body: string;
  proof: string;
}

const CAPABILITIES: Capability[] = [
  {
    icon: ShieldCheck,
    title: "Trust that moves",
    body: "Every agent carries a score recomputed from its own behaviour — not a permission granted once at deployment and never revisited. Drift is measured against the agent's own history, so a fleet of dissimilar agents doesn't need one impossible shared threshold.",
    proof: "Learned scoring beats hand-set weights by 6.1% AUC",
  },
  {
    icon: Scale,
    title: "Policy as data",
    body: "Rules are structured records, not code branches — so they can be versioned, diffed, and replayed. Editing a policy appends an immutable version, which means a decision from months ago is still explainable against the exact rule that produced it.",
    proof: "Every rule version kept, never overwritten",
  },
  {
    icon: FlaskConical,
    title: "Simulate before you commit",
    body: "Draft a rule and replay it against decisions already on record to see precisely what it catches — and what it misses — before it governs anything real. No policy reaches production on a guess.",
    proof: "Replay any candidate rule over historical decisions",
  },
  {
    icon: ScrollText,
    title: "An answer for every verdict",
    body: "Each decision returns the arithmetic in plain language: which factors moved the score, which policies fired, and what the model attributed it to. Explanation is an output of the pipeline, not a report generated afterwards.",
    proof: "Per-factor attribution on every scored decision",
  },
];

const STEPS = [
  {
    step: "01",
    title: "Register your agents",
    body: "Each autonomous agent joins with a capability, an owner, and an autonomy tier. ATLAS starts building its behavioural record from the first decision.",
  },
  {
    step: "02",
    title: "Write the rules that matter",
    body: "Compose policies from a fixed vocabulary of signals — trust, risk, amount, lifecycle state, time of day — then simulate them against real history before deploying.",
  },
  {
    step: "03",
    title: "Route every action through the pipeline",
    body: "Agents ask ATLAS before they act. Trust is scored, policies evaluated, outcomes simulated, and the verdict recorded — all before execution.",
  },
];

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-xl border border-cyan-glow/25 bg-cyan-glow/5 px-3 py-1.5 font-mono text-label-mono-xs uppercase tracking-[0.15em] text-cyan-glow">
      {children}
    </span>
  );
}

export default function LandingPage() {
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-50 border-b border-white/5 bg-surface-base/70 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
          <Link href="/" className="flex items-center gap-3">
            <span className="flex size-8 items-center justify-center rounded border border-cyan-glow/30 bg-cyan-glow/10 shadow-[0_0_10px_rgb(6_182_212_/_0.2)]">
              <BrainCircuit className="size-5 text-cyan-glow" />
            </span>
            <span className="text-headline-sm font-bold tracking-tight text-white">ATLAS</span>
          </Link>

          <nav className="hidden items-center gap-8 md:flex">
            {NAV_LINKS.map((link) => (
              <a
                key={link.href}
                href={link.href}
                className="font-mono text-label-mono text-on-surface-variant transition-colors hover:text-white"
              >
                {link.label}
              </a>
            ))}
          </nav>

          <Link
            href="/console"
            className="flex items-center gap-2 rounded border border-cyan-glow/40 bg-cyan-glow/10 px-4 py-2 font-mono text-label-mono uppercase tracking-wider text-cyan-glow transition-all hover:bg-cyan-glow/20 hover:shadow-[0_0_15px_rgb(6_182_212_/_0.25)]"
          >
            Launch Console
            <ArrowRight className="size-3.5" />
          </Link>
        </div>
      </header>

      {/* --- Hero --- */}
      <section className="relative overflow-hidden px-6 pb-28 pt-24 md:pt-32">
        {/* Bloom behind the headline. */}
        <div
          className="pointer-events-none absolute left-1/2 top-0 size-[700px] -translate-x-1/2 -translate-y-1/3 rounded-full bg-cyan-glow/10 blur-[130px]"
          aria-hidden
        />

        <div className="relative mx-auto max-w-4xl text-center">
          <div className="animate-fade-in-up">
            <SectionLabel>Governance Layer for Autonomous Agents</SectionLabel>
          </div>

          <h1 className="mt-8 animate-fade-in-up text-[44px] font-bold leading-[1.1] tracking-tight text-white [animation-delay:100ms] md:text-[64px]">
            The control plane for
            <br />
            <span className="bg-gradient-to-r from-cyan-glow via-primary to-tertiary-green bg-clip-text text-transparent">
              trusted autonomous finance
            </span>
          </h1>

          <p className="mx-auto mt-8 max-w-2xl animate-fade-in-up text-body-lg leading-relaxed text-on-surface-variant [animation-delay:200ms] md:text-[18px]">
            Autonomous agents are moving real money. ATLAS decides whether one can be
            trusted to act — scoring its behaviour, enforcing your policies, and simulating
            the outcome{" "}
            <em className="not-italic text-white">before the action executes</em>, never
            after.
          </p>

          <div className="mt-10 flex animate-fade-in-up flex-col items-center justify-center gap-3 [animation-delay:300ms] sm:flex-row">
            <Link
              href="/console"
              className="group flex w-full items-center justify-center gap-2 rounded border border-cyan-glow/50 bg-cyan-glow/15 px-6 py-3 text-body-md font-semibold text-white transition-all hover:bg-cyan-glow/25 hover:shadow-[0_0_25px_rgb(6_182_212_/_0.3)] sm:w-auto"
            >
              Open the Console
              <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
            </Link>
            <a
              href="https://github.com/Edith-Stark06/ATLAS"
              target="_blank"
              rel="noreferrer"
              className="flex w-full items-center justify-center gap-2 rounded border border-white/10 px-6 py-3 text-body-md text-on-surface-variant transition-colors hover:border-white/20 hover:text-white sm:w-auto"
            >
              <Github className="size-4" />
              View the source
            </a>
          </div>

          <p className="mt-6 animate-fade-in-up font-mono text-label-mono-xs uppercase tracking-[0.12em] text-outline [animation-delay:400ms]">
            Live demo runs on seeded data · No sign-up
          </p>
        </div>
      </section>

      {/* --- Pipeline --- */}
      <section
        id="pipeline"
        className="scroll-mt-20 border-y border-white/5 bg-surface-base/40 px-6 py-24"
      >
        <div className="mx-auto max-w-6xl">
          <div className="mb-16 text-center">
            <SectionLabel>The Governance Pipeline</SectionLabel>
            <h2 className="mx-auto mt-6 max-w-2xl text-headline-lg font-bold tracking-tight text-white md:text-[36px]">
              Eight checks, every one of them before execution
            </h2>
            <p className="mx-auto mt-4 max-w-2xl text-body-md text-on-surface-variant">
              Conventional governance audits what already happened. ATLAS sits in front of
              the action, so a decision that should not have been made simply is not made.
            </p>
          </div>

          <PipelineDiagram />
        </div>
      </section>

      {/* --- Capabilities --- */}
      <section id="capabilities" className="scroll-mt-20 px-6 py-24">
        <div className="mx-auto max-w-6xl">
          <div className="mb-14 max-w-2xl">
            <SectionLabel>Core Capabilities</SectionLabel>
            <h2 className="mt-6 text-headline-lg font-bold tracking-tight text-white md:text-[36px]">
              Built to be inspected, not just trusted
            </h2>
          </div>

          <div className="grid gap-6 md:grid-cols-2">
            {CAPABILITIES.map((capability, i) => (
              <article
                key={capability.title}
                className="glass-panel glass-panel-hover group animate-fade-in-up rounded-xl p-7"
                style={{ animationDelay: `${i * 80}ms` }}
              >
                <span className="mb-5 flex size-11 items-center justify-center rounded-lg border border-cyan-glow/25 bg-cyan-glow/10 text-cyan-glow transition-shadow group-hover:shadow-[0_0_18px_rgb(6_182_212_/_0.25)]">
                  <capability.icon className="size-5" />
                </span>
                <h3 className="mb-3 text-headline-sm font-semibold text-white">
                  {capability.title}
                </h3>
                <p className="text-body-md leading-relaxed text-on-surface-variant">
                  {capability.body}
                </p>
                <p className="mt-5 border-t border-white/5 pt-4 font-mono text-label-mono-xs uppercase tracking-wider text-cyan-glow/80">
                  {capability.proof}
                </p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* --- How it works --- */}
      <section
        id="how"
        className="scroll-mt-20 border-t border-white/5 bg-surface-base/40 px-6 py-24"
      >
        <div className="mx-auto max-w-5xl">
          <div className="mb-14 text-center">
            <SectionLabel>How it works</SectionLabel>
            <h2 className="mt-6 text-headline-lg font-bold tracking-tight text-white md:text-[36px]">
              Three steps to governed autonomy
            </h2>
          </div>

          <ol className="grid gap-8 md:grid-cols-3">
            {STEPS.map((item, i) => (
              <li
                key={item.step}
                className="animate-fade-in-up"
                style={{ animationDelay: `${i * 100}ms` }}
              >
                <span className="font-mono text-hero-num text-transparent [-webkit-text-stroke:1px_rgb(6_182_212_/_0.4)]">
                  {item.step}
                </span>
                <h3 className="mb-3 mt-4 text-headline-sm font-semibold text-white">
                  {item.title}
                </h3>
                <p className="text-body-md leading-relaxed text-on-surface-variant">
                  {item.body}
                </p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* --- Closing CTA --- */}
      <section className="relative overflow-hidden px-6 py-28">
        <div
          className="pointer-events-none absolute left-1/2 top-1/2 size-[600px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-cyan-glow/[0.07] blur-[120px]"
          aria-hidden
        />
        <div className="relative mx-auto max-w-3xl text-center">
          <h2 className="text-headline-lg font-bold tracking-tight text-white md:text-[40px]">
            The question is not whether your AI is capable.
            <br />
            <span className="text-cyan-glow">It is whether you can prove it is safe.</span>
          </h2>
          <p className="mx-auto mt-6 max-w-xl text-body-lg text-on-surface-variant">
            Open the console and watch a real governance pipeline evaluate live agents,
            policies, and decisions.
          </p>
          <Link
            href="/console"
            className="group mt-10 inline-flex items-center gap-2 rounded border border-cyan-glow/50 bg-cyan-glow/15 px-7 py-3.5 text-body-md font-semibold text-white transition-all hover:bg-cyan-glow/25 hover:shadow-[0_0_25px_rgb(6_182_212_/_0.3)]"
          >
            Launch Console
            <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
          </Link>
        </div>
      </section>

      <footer className="border-t border-white/5 px-6 py-10">
        <div
          className={cn(
            "mx-auto flex max-w-6xl flex-col items-center justify-between gap-4",
            "text-center sm:flex-row sm:text-left",
          )}
        >
          <div className="flex items-center gap-3">
            <BrainCircuit className="size-4 text-cyan-glow" />
            <span className="font-mono text-label-mono text-on-surface-variant">
              ATLAS — Adaptive Trust &amp; Lifecycle Assurance System
            </span>
          </div>
          <div className="flex items-center gap-6">
            <Link
              href="/console/status"
              className="font-mono text-label-mono text-on-surface-variant transition-colors hover:text-white"
            >
              System status
            </Link>
            <a
              href="https://github.com/Edith-Stark06/ATLAS"
              target="_blank"
              rel="noreferrer"
              className="font-mono text-label-mono text-on-surface-variant transition-colors hover:text-white"
            >
              GitHub
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
