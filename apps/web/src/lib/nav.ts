import {
  Activity,
  BarChart3,
  Bell,
  Boxes,
  ClipboardList,
  Cpu,
  FlaskConical,
  Gauge,
  LayoutGrid,
  Medal,
  Scale,
  ScrollText,
  Search,
  Settings,
  ShieldCheck,
  SquareStack,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
  /** False for sections that have nav entries but no screen yet. */
  built: boolean;
  /** Longer name for the top bar breadcrumb, when the nav label is clipped. */
  breadcrumb?: string;
}

export interface NavSection {
  /** Section kicker in the sidebar. */
  label: string;
  items: NavItem[];
}

/**
 * Grouped by the question each screen answers, which is also the order a
 * governance investigation actually runs in: what happened → what rule
 * governed it → how is the agent behaving → what is the system doing.
 *
 * Every route the console has ever had appears here; nothing was dropped in
 * the reorganisation, and two previously unreachable screens (System Status,
 * and per-agent detail) are now navigable.
 */
export const NAV_SECTIONS: NavSection[] = [
  {
    label: "Mission Control",
    items: [
      { label: "Overview", href: "/console", icon: LayoutGrid, built: true, breadcrumb: "Mission Control" },
      { label: "Decisions", href: "/console/decisions", icon: SquareStack, built: true },
      { label: "Investigations", href: "/console/explain", icon: Search, built: true },
    ],
  },
  {
    label: "Governance",
    items: [
      { label: "Policies", href: "/console/policies", icon: Scale, built: true },
      { label: "Ledger", href: "/console/ledger", icon: ScrollText, built: true },
      { label: "Audit", href: "/console/audit", icon: ClipboardList, built: true },
    ],
  },
  {
    label: "Agents",
    items: [
      { label: "Registry", href: "/console/agents", icon: Boxes, built: true, breadcrumb: "Agent Registry" },
      { label: "Trust & Risk", href: "/console/trust-engine", icon: ShieldCheck, built: true },
      { label: "Benchmark", href: "/console/benchmark", icon: Medal, built: true },
      { label: "Capacity", href: "/console/capacity", icon: Gauge, built: true, breadcrumb: "Capacity Planning" },
    ],
  },
  {
    label: "System",
    items: [
      { label: "Simulation", href: "/console/simulations", icon: FlaskConical, built: true },
      { label: "Model Lifecycle", href: "/console/models", icon: Cpu, built: true },
      { label: "Analytics", href: "/console/analytics", icon: BarChart3, built: true },
      { label: "Status", href: "/console/status", icon: Activity, built: true, breadcrumb: "System Status" },
      { label: "Alerts", href: "/console/alerts", icon: Bell, built: false },
    ],
  },
];

/** Flat list — used for breadcrumb resolution and the mobile nav. */
export const NAV_ITEMS: NavItem[] = NAV_SECTIONS.flatMap((section) => section.items);

export const SETTINGS_ITEM: NavItem = {
  label: "Settings",
  href: "/console/settings",
  icon: Settings,
  built: false,
};

const CONSOLE_ROOT = "/console";

/**
 * The console root is a prefix of every other console route, so it only counts
 * as active on an exact match — otherwise Overview would light up everywhere.
 * Deeper routes still match their children, so /console/decisions/DEC-1 keeps
 * Decisions highlighted.
 */
export function isNavItemActive(pathname: string, href: string): boolean {
  if (href === CONSOLE_ROOT) return pathname === CONSOLE_ROOT;
  return pathname === href || pathname.startsWith(`${href}/`);
}

/** The deepest nav entry matching this path — what the top bar names. */
export function resolveNavItem(pathname: string): NavItem | null {
  const matches = [...NAV_ITEMS, SETTINGS_ITEM].filter((item) =>
    isNavItemActive(pathname, item.href),
  );
  if (matches.length === 0) return null;
  return matches.reduce((deepest, item) =>
    item.href.length > deepest.href.length ? item : deepest,
  );
}
