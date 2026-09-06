"use client";

import { useEffect, useState } from "react";

import type { ActivityItem } from "@/lib/types";
import { cn, formatTime } from "@/lib/utils";

const ACTIVITY_TONE: Record<ActivityItem["tone"], string> = {
  info: "bg-outline",
  success: "bg-tertiary",
  warning: "bg-brand-amber",
  danger: "bg-error",
};

//: How many items stay in view — matches the dashboard's prior server-fetched
//: default (`fetchDashboard`'s activity list), so a fresh page load and a
//: page that's been open a while show a comparably-sized feed.
const MAX_ITEMS = 20;

/**
 * The dashboard's activity feed, live. Renders `initialActivity` immediately
 * (server-fetched, correct on first paint and with JS disabled), then opens an
 * EventSource against the same-origin proxy route and prepends what arrives.
 *
 * No token handling here at all — `/api/atlas/stream` is same-origin, so the
 * browser attaches the session cookie automatically, and the proxy route
 * attaches the actual API credential server-side. Same "page scripts never
 * hold a credential" rule as every other browser->API call in this app
 * (see lib/api-client.ts).
 */
export function LiveActivityFeed({
  initialActivity,
  className,
}: {
  initialActivity: ActivityItem[];
  className?: string;
}) {
  const [items, setItems] = useState(initialActivity);
  // Ids that arrived over the stream rather than in the server render — only
  // those animate in, so the first paint is not a wall of moving rows.
  const [streamed, setStreamed] = useState<Set<string>>(() => new Set());

  useEffect(() => {
    const source = new EventSource("/api/atlas/stream");

    source.onmessage = (event) => {
      const item = JSON.parse(event.data) as ActivityItem;
      setItems((current) => {
        if (current.some((existing) => existing.id === item.id)) return current;
        return [item, ...current].slice(0, MAX_ITEMS);
      });
      setStreamed((current) => new Set(current).add(item.id));
    };

    // EventSource reconnects on its own after a drop — nothing custom needed
    // beyond letting the browser do that and closing the connection this
    // effect opened when the component unmounts.
    return () => source.close();
  }, []);

  return (
    <ul className={cn("custom-scrollbar divide-y divide-outline-variant", className)}>
      {items.map((item) => (
        <li
          key={item.id}
          className={cn(
            "flex gap-2.5 px-4 py-2.5",
            streamed.has(item.id) && "animate-slide-in",
          )}
        >
          <span
            className={cn(
              "mt-[7px] size-1.5 shrink-0 rounded-full",
              ACTIVITY_TONE[item.tone],
            )}
            aria-hidden
          />
          <div className="min-w-0 flex-1">
            <p className="text-body-sm text-on-surface">{item.message}</p>
            <p className="mt-0.5 font-mono text-label-mono-xs text-outline">
              {formatTime(item.at)}
            </p>
          </div>
        </li>
      ))}
    </ul>
  );
}
