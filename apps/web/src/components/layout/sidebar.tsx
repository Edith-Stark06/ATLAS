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
          ? "border-l-2 border-cyan-glow bg-cyan-glow/10 font-semibold text-cyan-glow shadow-[inset_20px_0_20px_-20px_rgb(6_182_212_/_0.2)]"
          : "text-on-surface-variant hover:bg-surface-variant/40 hover:text-white",
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
    <aside className="fixed left-0 z-50 flex h-full w-64 flex-col border-r border-white/5 bg-surface-container/60 shadow-2xl backdrop-blur-xl">
      <div className="flex items-center gap-3 border-b border-white/5 p-gutter">
        <div className="flex size-8 shrink-0 items-center justify-center rounded border border-cyan-glow/30 bg-cyan-glow/10 shadow-[0_0_10px_rgb(6_182_212_/_0.2)]">
          <BrainCircuit className="size-5 text-cyan-glow" />
        </div>
        <div className="min-w-0">
          <p className="text-headline-lg font-bold tracking-tighter text-white drop-shadow-[0_0_8px_rgb(6_182_212_/_0.5)]">
            ATLAS
          </p>
          <p className="font-mono text-status-label text-cyan-glow/70">
            AI Trust Operating System
          </p>
        </div>
      </div>

      <nav className="custom-scrollbar flex flex-1 flex-col gap-1 overflow-y-auto px-3 py-stack-md">
        {NAV_ITEMS.map((item) => (
          <NavLink key={item.href} item={item} active={isActive(pathname, item.href)} />
        ))}
      </nav>

      <div className="mt-auto flex flex-col gap-2 border-t border-white/5 p-4">
        <NavLink item={SETTINGS_ITEM} active={isActive(pathname, SETTINGS_ITEM.href)} />
        <div className="mt-2 flex items-center justify-between px-3">
          <span className="flex items-center gap-2">
            <span className="size-2 animate-pulse rounded-full bg-tertiary-green shadow-[0_0_8px_0_var(--color-tertiary-green)]" />
            <span className="font-mono text-label-mono text-tertiary-green">Online</span>
          </span>
          <span className="text-right text-status-label text-on-surface-variant/60">
            v1.0 · Enterprise
          </span>
        </div>
      </div>
    </aside>
  );
}
