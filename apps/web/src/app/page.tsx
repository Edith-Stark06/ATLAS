import type { Metadata } from "next";
import Link from "next/link";
import {
  ArrowRight,
  FlaskConical,
  Github,
  Scale,
  ScrollText,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";

import { AtlasMark } from "@/components/layout/atlas-mark";
import { PipelineDiagram } from "@/components/marketing/pipeline-diagram";

export const metadata: Metadata = {
  title: "ATLAS — Governance Control Plane",
  description:
    "ATLAS decides whether an autonomous agent can be trusted to act — before it acts. Continuous trust scoring, policy as data, pre-execution simulation, and a verifiable governance ledger.",
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
    proof: "Learned scoring beats hand-set weights on held-out data",
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

function Eyebrow({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-md border border-outline-variant px-2.5 py-1 text-status-label uppercase text-on-surface-variant">
      <span className="size-1.5 rounded-full bg-primary" aria-hidden />
      {children}
    </span>
  );
}

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-surface-base">
      <header className="sticky top-0 z-50 border-b border-outline-variant bg-surface-base/90 backdrop-blur-sm">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-6">
          <Link href="/" className="flex items-center gap-2.5">
            <span className="flex size-7 items-center justify-center rounded-md border border-primary/25 bg-primary/[0.08] p-1 text-primary">
              <AtlasMark />
            </span>
            <span className="text-[15px] font-semibold tracking-[0.14em] text-on-surface">
              ATLAS
            </span>
          </Link>

          <nav className="hidden items-center gap-7 md:flex">
            {NAV_LINKS.map((link) => (
              <a
                key={link.href}
                href={link.href}
                className="text-body-sm text-on-surface-variant transition-colors hover:text-on-surface"
              >
                {link.label}
              </a>
            ))}
          </nav>

          <Link
            href="/console"
            className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-body-sm font-medium text-on-primary transition-colors hover:bg-primary-bright"
          >
            Open console
            <ArrowRight className="size-3.5" />
          </Link>
        </div>
      </header>

      {/* --- Hero --- */}
      <section className="border-b border-outline-variant px-6 py-24 md:py-28">
        <div className="mx-auto max-w-4xl text-center">
          <div className="animate-fade-in-up">
            <Eyebrow>Governance Control Plane</Eyebrow>
          </div>

          <h1 className="mx-auto mt-7 max-w-3xl animate-fade-in-up text-[40px] font-semibold leading-[1.08] tracking-[-0.03em] text-on-surface [animation-delay:60ms] md:text-[56px]">
            Autonomous agents are acting.
            <br />
            <span className="text-on-surface-variant">Something has to govern them.</span>
          </h1>

          <p className="mx-auto mt-7 max-w-2xl animate-fade-in-up text-body-lg leading-relaxed text-on-surface-variant [animation-delay:120ms]">
            ATLAS decides whether an agent can be trusted to take a consequential action —
            scoring its behaviour, enforcing your policies, and simulating the outcome{" "}
            <span className="text-on-surface">before the action executes</span>, never after.
            Every verdict is recorded where it can be verified.
          </p>

          <div className="mt-9 flex animate-fade-in-up flex-col items-center justify-center gap-2.5 [animation-delay:180ms] sm:flex-row">
            <Link
              href="/console"
              className="group inline-flex w-full items-center justify-center gap-2 rounded-md bg-primary px-5 py-2.5 text-body-md font-medium text-on-primary transition-colors hover:bg-primary-bright sm:w-auto"
            >
              Open the console
              <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
            </Link>
            <a
              href="https://github.com/Edith-Stark06/ATLAS"
              target="_blank"
              rel="noreferrer"
              className="inline-flex w-full items-center justify-center gap-2 rounded-md border border-outline-strong px-5 py-2.5 text-body-md text-on-surface-variant transition-colors hover:border-outline hover:text-on-surface sm:w-auto"
            >
              <Github className="size-4" />
              View the source
            </a>
          </div>

          <p className="mt-6 animate-fade-in-up text-body-sm text-outline [animation-delay:240ms]">
            Live demo runs on seeded data · No sign-up
          </p>
        </div>
      </section>

      {/* --- Pipeline --- */}
      <section id="pipeline" className="scroll-mt-16 border-b border-outline-variant px-6 py-20">
        <div className="mx-auto max-w-6xl">
          <div className="mb-14 text-center">
            <Eyebrow>The governance pipeline</Eyebrow>
            <h2 className="mx-auto mt-5 max-w-2xl text-[30px] font-semibold tracking-[-0.025em] text-on-surface">
              Eight checks, every one of them before execution
            </h2>
            <p className="mx-auto mt-3 max-w-2xl text-body-md text-on-surface-variant">
              Conventional governance audits what already happened. ATLAS sits in front of the
              action, so a decision that should not have been made simply is not made.
            </p>
          </div>

          <PipelineDiagram />
        </div>
      </section>

      {/* --- Capabilities --- */}
      <section id="capabilities" className="scroll-mt-16 border-b border-outline-variant px-6 py-20">
        <div className="mx-auto max-w-6xl">
          <div className="mb-10 max-w-2xl">
            <Eyebrow>Core capabilities</Eyebrow>
            <h2 className="mt-5 text-[30px] font-semibold tracking-[-0.025em] text-on-surface">
              Built to be inspected, not just trusted
            </h2>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            {CAPABILITIES.map((capability) => (
              <article
                key={capability.title}
                className="surface-card glass-panel-hover flex flex-col p-6"
              >
                <span className="mb-4 flex size-9 items-center justify-center rounded-md border border-outline-variant bg-surface-container-high text-on-surface-variant">
                  <capability.icon className="size-4" strokeWidth={1.75} />
                </span>
                <h3 className="mb-2 text-headline-md text-on-surface">{capability.title}</h3>
                <p className="text-body-md leading-relaxed text-on-surface-variant">
                  {capability.body}
                </p>
                <p className="mt-5 border-t border-outline-variant pt-3.5 text-body-sm text-outline">
                  {capability.proof}
                </p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* --- How it works --- */}
      <section id="how" className="scroll-mt-16 border-b border-outline-variant px-6 py-20">
        <div className="mx-auto max-w-5xl">
          <div className="mb-10 text-center">
            <Eyebrow>How it works</Eyebrow>
            <h2 className="mt-5 text-[30px] font-semibold tracking-[-0.025em] text-on-surface">
              Three steps to governed autonomy
            </h2>
          </div>

          <ol className="grid gap-8 md:grid-cols-3">
            {STEPS.map((item) => (
              <li key={item.step}>
                <span className="font-mono text-label-mono text-primary">{item.step}</span>
                <h3 className="mb-2 mt-3 text-headline-md text-on-surface">{item.title}</h3>
                <p className="text-body-md leading-relaxed text-on-surface-variant">
                  {item.body}
                </p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* --- Closing --- */}
      <section className="px-6 py-24">
        <div className="mx-auto max-w-3xl text-center">
          <h2 className="text-[32px] font-semibold leading-tight tracking-[-0.025em] text-on-surface">
            The question is not whether your agents are capable.
            <br />
            <span className="text-on-surface-variant">
              It is whether you can prove they were safe.
            </span>
          </h2>
          <p className="mx-auto mt-5 max-w-xl text-body-lg text-on-surface-variant">
            Open the console and watch a real governance pipeline evaluate live agents,
            policies, and decisions.
          </p>
          <Link
            href="/console"
            className="group mt-8 inline-flex items-center gap-2 rounded-md bg-primary px-5 py-2.5 text-body-md font-medium text-on-primary transition-colors hover:bg-primary-bright"
          >
            Open the console
            <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
          </Link>
        </div>
      </section>

      <footer className="border-t border-outline-variant px-6 py-8">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 text-center sm:flex-row sm:text-left">
          <div className="flex items-center gap-2.5">
            <span className="flex size-5 items-center justify-center text-outline">
              <AtlasMark />
            </span>
            <span className="text-body-sm text-outline">
              ATLAS — Adaptive Trust &amp; Lifecycle Assurance System
            </span>
          </div>
          <div className="flex items-center gap-6">
            <Link
              href="/console/status"
              className="text-body-sm text-on-surface-variant transition-colors hover:text-on-surface"
            >
              System status
            </Link>
            <a
              href="https://github.com/Edith-Stark06/ATLAS"
              target="_blank"
              rel="noreferrer"
              className="text-body-sm text-on-surface-variant transition-colors hover:text-on-surface"
            >
              GitHub
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
