"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BrainCircuit } from "lucide-react";

import { NAV_ITEMS, SETTINGS_ITEM, type NavItem } from "@/lib/nav";
import { cn } from "@/lib/utils";

function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

function NavLink({ item, active }: { item: NavItem; active: boolean }) {
  const Icon = item.icon;

  return (
    <Link
      href={item.href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex items-center gap-3 rounded-lg px-3 py-2 transition-all duration-200",
        active
          ? "border-r-2 border-primary bg-primary-container/20 text-primary shadow-[0_0_12px_-2px_rgba(173,198,255,0.4)]"
          : "text-on-surface-variant hover:bg-surface-variant/40 hover:text-on-surface",
      )}
    >
      <Icon className="size-5 shrink-0" strokeWidth={active ? 2.25 : 1.75} />
      <span className="font-mono text-label-mono tracking-wide">{item.label}</span>
      {!item.built && (
        <span className="ml-auto text-status-label uppercase text-outline/70">soon</span>
      )}
    </Link>
  );
}

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 z-50 flex h-full w-64 flex-col border-r border-white/10 bg-surface-container/80 shadow-2xl backdrop-blur-xl">
      <div className="flex items-center gap-3 border-b border-white/10 p-gutter">
        <div className="flex size-8 shrink-0 items-center justify-center rounded border border-primary/30 bg-primary/20">
          <BrainCircuit className="size-5 text-primary" />
        </div>
        <div className="min-w-0">
          <p className="text-headline-lg font-bold tracking-tighter text-primary drop-shadow-[0_0_8px_rgba(173,198,255,0.3)]">
            ATLAS
          </p>
          <p className="font-mono text-status-label text-on-surface-variant">
            AI Trust Operating System
          </p>
        </div>
      </div>

      <nav className="flex flex-1 flex-col gap-1 overflow-y-auto px-3 py-stack-md">
        {NAV_ITEMS.map((item) => (
          <NavLink key={item.href} item={item} active={isActive(pathname, item.href)} />
        ))}
      </nav>

      <div className="mt-auto flex flex-col gap-2 border-t border-white/10 p-4">
        <NavLink item={SETTINGS_ITEM} active={isActive(pathname, SETTINGS_ITEM.href)} />
        <div className="mt-2 flex items-center justify-between px-3">
          <span className="flex items-center gap-2">
            <span className="size-2 animate-pulse rounded-full bg-tertiary shadow-[0_0_8px_0_var(--color-tertiary)]" />
            <span className="font-mono text-label-mono text-tertiary">Online</span>
          </span>
          <span className="text-right text-status-label text-on-surface-variant/60">
            v1.0 · Enterprise
          </span>
        </div>
      </div>
    </aside>
  );
}
