"use client";

import { useEffect, useState } from "react";

import type { ActivityItem } from "@/lib/types";
import { cn, formatTime } from "@/lib/utils";

const ACTIVITY_TONE: Record<ActivityItem["tone"], string> = {
  info: "bg-secondary",
  success: "bg-tertiary-green",
  warning: "bg-brand-amber",
  danger: "bg-error",
};

//: How many items stay in view — matches the dashboard's prior server-fetched
//: default (`fetchDashboard`'s activity list), so a fresh page load and a
//: page that's been open a while show a comparably-sized feed.
const MAX_ITEMS = 20;

/**
 * The dashboard's Activity Feed, live — the first client component in this
 * app with an ongoing data subscription (every console page before this one
 * is a Server Component rendering one fetched payload once). Renders
 * `initialActivity` immediately (server-fetched, correct on first paint and
 * with JS disabled), then opens an EventSource against the same-origin proxy
 * route and prepends whatever arrives.
 *
 * No token handling here at all — `/api/atlas/stream` is same-origin, so the
 * browser attaches the session cookie automatically, and the proxy route
 * attaches the actual API credential server-side. Same "page scripts never
 * hold a credential" rule as every other browser->API call in this app
 * (see lib/api-client.ts).
 */
export function LiveActivityFeed({ initialActivity }: { initialActivity: ActivityItem[] }) {
  const [items, setItems] = useState(initialActivity);

  useEffect(() => {
    const source = new EventSource("/api/atlas/stream");

    source.onmessage = (event) => {
      const item = JSON.parse(event.data) as ActivityItem;
      setItems((current) => {
        if (current.some((existing) => existing.id === item.id)) return current;
        return [item, ...current].slice(0, MAX_ITEMS);
      });
    };

    // EventSource reconnects on its own after a drop — nothing custom
    // needed here beyond letting the browser do that and cleaning up the
    // connection this effect opened when the component unmounts.
    return () => source.close();
  }, []);

  return (
    <ul className="custom-scrollbar flex-1 divide-y divide-white/5 overflow-y-auto">
      {items.map((item) => (
        <li key={item.id} className="flex gap-3 px-6 py-3.5 transition-colors hover:bg-white/[0.02]">
          <span className={cn("mt-1.5 h-8 w-0.5 shrink-0 rounded", ACTIVITY_TONE[item.tone])} />
          <div className="min-w-0">
            <p className="text-body-sm text-on-surface">{item.message}</p>
            <p className="mt-1 font-mono text-status-label text-outline">{formatTime(item.at)}</p>
          </div>
        </li>
      ))}
    </ul>
  );
}
