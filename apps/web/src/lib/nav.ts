import {
  BarChart3,
  Bell,
  Bot,
  FlaskConical,
  LayoutDashboard,
  Lightbulb,
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
  { label: "Control Center", href: "/", icon: LayoutDashboard, built: true },
  { label: "Trust Engine", href: "/trust-engine", icon: ShieldCheck, built: false },
  { label: "AI Agents", href: "/agents", icon: Bot, built: true },
  { label: "Policy Brain", href: "/policies", icon: Scale, built: true },
  { label: "Decision Intelligence", href: "/decisions", icon: Workflow, built: true },
  { label: "Simulation Engine", href: "/simulations", icon: FlaskConical, built: true },
  { label: "Explain AI", href: "/explain", icon: Lightbulb, built: false },
  { label: "Governance Ledger", href: "/ledger", icon: ScrollText, built: false },
  { label: "Analytics", href: "/analytics", icon: BarChart3, built: false },
  { label: "Alerts", href: "/alerts", icon: Bell, built: false },
];

export const SETTINGS_ITEM: NavItem = {
  label: "Settings",
  href: "/settings",
  icon: Settings,
  built: false,
};
