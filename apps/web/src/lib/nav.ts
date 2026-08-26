import {
  BarChart3,
  Bell,
  Bot,
  FlaskConical,
  LayoutDashboard,
  Lightbulb,
  Medal,
  ScrollText,
  Scale,
  Settings,
  ShieldCheck,
  Workflow,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
  /** False for sections that have nav entries but no design yet. */
  built: boolean;
}

/**
 * Mirrors the sidebar in the Stitch screens. Items without a designed screen
 * still route — to an honest placeholder rather than a 404.
 */
export const NAV_ITEMS: NavItem[] = [
  { label: "Control Center", href: "/console", icon: LayoutDashboard, built: true },
  { label: "Trust Engine", href: "/console/trust-engine", icon: ShieldCheck, built: true },
  { label: "AI Agents", href: "/console/agents", icon: Bot, built: true },
  { label: "Policy Brain", href: "/console/policies", icon: Scale, built: true },
  { label: "Decision Intelligence", href: "/console/decisions", icon: Workflow, built: true },
  { label: "Simulation Engine", href: "/console/simulations", icon: FlaskConical, built: true },
  { label: "Explain AI", href: "/console/explain", icon: Lightbulb, built: true },
  { label: "Governance Ledger", href: "/console/ledger", icon: ScrollText, built: true },
  { label: "Agent Benchmark", href: "/console/benchmark", icon: Medal, built: true },
  { label: "Analytics", href: "/console/analytics", icon: BarChart3, built: true },
  { label: "Alerts", href: "/console/alerts", icon: Bell, built: false },
];

export const SETTINGS_ITEM: NavItem = {
  label: "Settings",
  href: "/console/settings",
  icon: Settings,
  built: false,
};
