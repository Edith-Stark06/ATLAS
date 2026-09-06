"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { CornerDownLeft, Search } from "lucide-react";

import { NAV_ITEMS, NAV_SECTIONS, SETTINGS_ITEM } from "@/lib/nav";
import { cn } from "@/lib/utils";

interface Target {
  label: string;
  href: string;
  group: string;
  icon: (typeof NAV_ITEMS)[number]["icon"];
}

const TARGETS: Target[] = [
  ...NAV_SECTIONS.flatMap((section) =>
    section.items.map((item) => ({
      label: item.breadcrumb ?? item.label,
      href: item.href,
      group: section.label,
      icon: item.icon,
    })),
  ),
  { label: "Settings", href: SETTINGS_ITEM.href, group: "System", icon: SETTINGS_ITEM.icon },
];

/** Decision ids look like DEC-10482 / TRX-1 — anything with a dash and digits. */
const DECISION_ID = /^[a-z]{2,6}-[a-z0-9-]+$/i;

/**
 * Jump-to navigation. Deliberately scoped to what the app can actually answer
 * without a search endpoint: every console destination, plus a direct jump to
 * a decision when the query is shaped like a decision id.
 */
export function CommandSearch() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [cursor, setCursor] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const results = useMemo(() => {
    const trimmed = query.trim();
    const matches = trimmed
      ? TARGETS.filter((target) =>
          `${target.group} ${target.label}`.toLowerCase().includes(trimmed.toLowerCase()),
        )
      : TARGETS.slice(0, 6);

    if (trimmed && DECISION_ID.test(trimmed)) {
      return [
        {
          label: `Open decision ${trimmed.toUpperCase()}`,
          href: `/console/decisions/${encodeURIComponent(trimmed.toUpperCase())}`,
          group: "Decision",
          icon: Search,
        },
        ...matches,
      ];
    }
    return matches;
  }, [query]);

  // Derived, not an effect: a new query invalidates the old highlight, and
  // an effect would render one frame with a cursor past the end of the list.
  const [lastQuery, setLastQuery] = useState(query);
  if (lastQuery !== query) {
    setLastQuery(query);
    setCursor(0);
  }

  // Cmd/Ctrl-K focuses it; a click outside or Escape closes it.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        inputRef.current?.focus();
        setOpen(true);
      }
      if (event.key === "Escape") setOpen(false);
    };
    const onClick = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("mousedown", onClick);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("mousedown", onClick);
    };
  }, []);

  function onInputKey(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setCursor((c) => Math.min(c + 1, results.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setCursor((c) => Math.max(c - 1, 0));
    } else if (event.key === "Enter" && results[cursor]) {
      event.preventDefault();
      router.push(results[cursor].href);
      setOpen(false);
      setQuery("");
      inputRef.current?.blur();
    }
  }

  return (
    <div ref={containerRef} className="relative w-full max-w-xs">
      <label className="sr-only" htmlFor="atlas-search">
        Search the console
      </label>
      <Search
        className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-outline"
        aria-hidden
      />
      <input
        id="atlas-search"
        ref={inputRef}
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        onFocus={() => setOpen(true)}
        onKeyDown={onInputKey}
        placeholder="Search"
        autoComplete="off"
        role="combobox"
        aria-expanded={open}
        aria-controls="atlas-search-results"
        className="w-full rounded-md border border-outline-variant bg-surface-container-low py-1.5 pl-8 pr-10 text-body-sm text-on-surface placeholder:text-outline focus:border-primary/50 focus:outline-none"
      />
      <kbd className="pointer-events-none absolute right-2 top-1/2 hidden -translate-y-1/2 rounded border border-outline-variant px-1 py-0.5 font-mono text-label-mono-xs text-outline sm:block">
        ⌘K
      </kbd>

      {open && results.length > 0 && (
        <div
          id="atlas-search-results"
          role="listbox"
          className="glass-overlay absolute left-0 right-0 top-[calc(100%+6px)] z-50 max-h-80 overflow-y-auto p-1"
        >
          {results.map((result, index) => (
            <Link
              key={result.href}
              href={result.href}
              role="option"
              aria-selected={index === cursor}
              onMouseEnter={() => setCursor(index)}
              onClick={() => {
                setOpen(false);
                setQuery("");
              }}
              className={cn(
                "flex items-center gap-2.5 rounded px-2.5 py-2 text-body-sm transition-colors",
                index === cursor
                  ? "bg-primary/[0.10] text-on-surface"
                  : "text-on-surface-variant",
              )}
            >
              <result.icon className="size-3.5 shrink-0 text-outline" strokeWidth={1.75} />
              <span className="truncate">{result.label}</span>
              <span className="ml-auto shrink-0 text-label-mono-xs uppercase text-outline">
                {result.group}
              </span>
              {index === cursor && (
                <CornerDownLeft className="size-3 shrink-0 text-outline" aria-hidden />
              )}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
