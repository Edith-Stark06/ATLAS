"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { LogIn, TriangleAlert } from "lucide-react";

import { Panel } from "@/components/ui/panel";

const FIELD_CLASS =
  "w-full rounded border border-white/10 bg-surface-container-high px-3 py-2 font-mono text-body-sm text-on-surface focus:border-secondary focus:outline-none";

/**
 * Only same-origin paths are followed after login. Without this check, a link
 * like `/login?next=https://evil.example` would turn the sign-in page into an
 * open redirect that looks like it came from ATLAS.
 */
function safeRedirect(next: string | undefined): string {
  if (!next || !next.startsWith("/") || next.startsWith("//")) return "/console";
  return next;
}

export function LoginForm({ next, expired }: { next?: string; expired?: boolean }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  function submit(event: React.FormEvent) {
    event.preventDefault();
    startTransition(async () => {
      setError(null);
      try {
        const response = await fetch("/api/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password }),
        });

        if (!response.ok) {
          const body = await response.json().catch(() => ({}));
          setError(body.error ?? "Sign in failed");
          return;
        }

        router.replace(safeRedirect(next));
        // The console is server-rendered; without this it would re-use the
        // tree fetched while signed out.
        router.refresh();
      } catch {
        setError("Could not reach the sign-in service");
      }
    });
  }

  return (
    <Panel interactive={false}>
      <form onSubmit={submit} className="flex flex-col gap-4 p-6">
        {expired && (
          <p className="rounded border-l-2 border-brand-amber bg-brand-amber/5 px-3 py-2 text-body-sm text-brand-amber">
            Your session expired. Sign in again to continue.
          </p>
        )}

        <label className="flex flex-col gap-1.5">
          <span className="font-mono text-status-label uppercase text-on-surface-variant">
            Email
          </span>
          <input
            className={FIELD_CLASS}
            type="email"
            name="email"
            autoComplete="username"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>

        <label className="flex flex-col gap-1.5">
          <span className="font-mono text-status-label uppercase text-on-surface-variant">
            Password
          </span>
          <input
            className={FIELD_CLASS}
            type="password"
            name="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>

        {error && (
          <p
            role="alert"
            className="flex items-start gap-2 rounded border-l-2 border-error bg-error/5 px-3 py-2 text-body-sm text-error"
          >
            <TriangleAlert className="mt-0.5 size-4 shrink-0" />
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={pending}
          className="mt-1 flex items-center justify-center gap-2 rounded border border-primary/30 bg-primary/10 px-4 py-2 font-mono text-label-mono uppercase text-primary transition-colors hover:bg-primary/20 disabled:opacity-60"
        >
          <LogIn className="size-3.5" />
          {pending ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </Panel>
  );
}
