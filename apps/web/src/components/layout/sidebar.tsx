"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Menu, X } from "lucide-react";

import { AtlasMark } from "@/components/layout/atlas-mark";
import {
  NAV_SECTIONS,
  SETTINGS_ITEM,
  isNavItemActive,
  type NavItem,
} from "@/lib/nav";
import { cn } from "@/lib/utils";

function NavLink({
  item,
  active,
  onNavigate,
}: {
  item: NavItem;
  active: boolean;
  onNavigate?: () => void;
}) {
  const Icon = item.icon;

  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={cn(
        "group relative flex items-center gap-2.5 rounded-md px-2.5 py-[7px] text-body-sm transition-colors",
        active
          ? "bg-primary/[0.10] font-medium text-on-surface"
          : "text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface",
      )}
    >
      {/* The active marker is a 2px violet rule, not a filled pill — the
          accent stays a brand cue rather than becoming the background. */}
      <span
        aria-hidden
        className={cn(
          "absolute left-0 top-1/2 h-4 w-[2px] -translate-y-1/2 rounded-r-full bg-primary transition-opacity",
          active ? "opacity-100" : "opacity-0",
        )}
      />
      <Icon
        className={cn(
          "size-[15px] shrink-0 transition-colors",
          active ? "text-primary" : "text-outline group-hover:text-on-surface-variant",
        )}
        strokeWidth={1.75}
      />
      <span className="truncate">{item.label}</span>
      {!item.built && (
        <span className="ml-auto rounded-sm bg-surface-container-highest px-1.5 py-0.5 text-status-label uppercase text-outline">
          soon
        </span>
      )}
    </Link>
  );
}

function NavTree({ pathname, onNavigate }: { pathname: string; onNavigate?: () => void }) {
  return (
    <>
      <nav className="custom-scrollbar flex flex-1 flex-col gap-5 overflow-y-auto px-3 py-4">
        {NAV_SECTIONS.map((section) => (
          <div key={section.label} className="flex flex-col gap-0.5">
            <p className="eyebrow px-2.5 pb-1.5">{section.label}</p>
            {section.items.map((item) => (
              <NavLink
                key={item.href}
                item={item}
                active={isNavItemActive(pathname, item.href)}
                onNavigate={onNavigate}
              />
            ))}
          </div>
        ))}
      </nav>

      <div className="mt-auto border-t border-outline-variant p-3">
        <NavLink
          item={SETTINGS_ITEM}
          active={isNavItemActive(pathname, SETTINGS_ITEM.href)}
          onNavigate={onNavigate}
        />
        <p className="px-2.5 pt-3 font-mono text-label-mono-xs uppercase text-outline">
          v1.0 · Enterprise
        </p>
      </div>
    </>
  );
}

function Brand({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <Link
      href="/console"
      onClick={onNavigate}
      className="flex h-14 shrink-0 items-center gap-2.5 border-b border-outline-variant px-4"
    >
      <span className="flex size-7 shrink-0 items-center justify-center rounded-md border border-primary/25 bg-primary/[0.08] p-1 text-primary">
        <AtlasMark />
      </span>
      <span className="min-w-0">
        <span className="block text-[15px] font-semibold leading-none tracking-[0.14em] text-on-surface">
          ATLAS
        </span>
        <span className="mt-1 block truncate text-[9px] font-semibold uppercase leading-none tracking-[0.055em] text-outline">
          Governance Control Plane
        </span>
      </span>
    </Link>
  );
}

/**
 * Fixed rail on desktop; a slide-over sheet below `lg`, where a permanent
 * 15rem column would eat most of the viewport.
 */
export function Sidebar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [lastPath, setLastPath] = useState(pathname);

  // A sheet left open over the newly-navigated page is the classic mobile-nav
  // bug. Adjusted during render rather than in an effect: this is derived
  // state, and an effect would paint the stale open sheet for a frame first.
  if (lastPath !== pathname) {
    setLastPath(pathname);
    setOpen(false);
  }

  // Escape closes it. This one *is* an effect — it subscribes to the document.
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <>
      {/* Mobile trigger — sits in the top bar's left slot. */}
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Open navigation"
        aria-expanded={open}
        className="fixed left-3 top-3 z-50 rounded-md border border-outline-variant bg-surface-container-low p-2 text-on-surface-variant transition-colors hover:text-on-surface lg:hidden"
      >
        <Menu className="size-4" />
      </button>

      {open && (
        <div
          className="fixed inset-0 z-50 animate-fade-in bg-black/60 lg:hidden"
          onClick={() => setOpen(false)}
          aria-hidden
        />
      )}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-60 flex-col border-r border-outline-variant bg-surface-container-lowest transition-transform duration-200 ease-out lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
        aria-label="Console navigation"
      >
        <div className="flex items-center">
          <div className="min-w-0 flex-1">
            <Brand onNavigate={() => setOpen(false)} />
          </div>
          <button
            type="button"
            onClick={() => setOpen(false)}
            aria-label="Close navigation"
            className="mr-2 rounded-md p-2 text-on-surface-variant hover:text-on-surface lg:hidden"
          >
            <X className="size-4" />
          </button>
        </div>

        <NavTree pathname={pathname} onNavigate={() => setOpen(false)} />
      </aside>
    </>
  );
}
