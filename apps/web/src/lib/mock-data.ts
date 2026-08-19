import type {
  ActivityItem,
  Agent,
  DashboardMetric,
  Decision,
  PipelineStage,
  Policy,
  SimulationRun,
} from "@/lib/types";

/**
 * Deterministic fixtures for Phase 1.
 *
 * Timestamps are hard-coded ISO strings rather than computed from `Date.now()`
 * so server and client render identically (no hydration mismatch).
 */

export const DASHBOARD_METRICS: DashboardMetric[] = [
  { key: "agents", label: "Active AI Agents", value: "184", tone: "secondary", icon: "bot" },
  { key: "decisions", label: "Protected Decisions Today", value: "2.4M", tone: "secondary", icon: "shield" },
  { key: "trust", label: "Average Trust Score", value: "94", tone: "tertiary", icon: "verified" },
  { key: "compliance", label: "Policy Compliance", value: "99.98%", tone: "secondary", icon: "policy" },
  { key: "explainability", label: "Explainability Coverage", value: "98.6%", tone: "secondary", icon: "brain" },
  { key: "review", label: "Human Review Rate", value: "4.2%", tone: "error", icon: "gavel" },
];

export const COMPOSITE_TRUST = {
  score: 94,
  predicted: 96,
  factors: [
    { key: "behavior", label: "Behavior Consistency", score: 96, weight: 0.22 },
    { key: "policy", label: "Policy Compliance", score: 99, weight: 0.24 },
    { key: "risk", label: "Risk Exposure", score: 88, weight: 0.2 },
    { key: "context", label: "Context Awareness", score: 91, weight: 0.14 },
    { key: "history", label: "Historical Reliability", score: 95, weight: 0.2 },
  ],
  /** Sparkline samples, oldest → newest. */
  trend: [88, 90, 89, 92, 91, 93, 92, 94, 93, 95, 94, 96],
};

export const LIVE_PIPELINE: { transactionId: string; stages: PipelineStage[] } = {
  transactionId: "TRX-992A",
  stages: [
    { key: "request", label: "Agent Request", status: "done", detail: "Travel Agent" },
    { key: "trust", label: "Trust Engine", status: "done", detail: "Score 94" },
    { key: "policy", label: "Policy Brain", status: "done", detail: "6/6 passed" },
    { key: "simulation", label: "Simulation Engine", status: "done", detail: "Risk 12" },
    { key: "decision", label: "Governance Decision", status: "active", detail: "Approving" },
    { key: "explain", label: "Explain AI", status: "pending" },
    { key: "ledger", label: "Governance Ledger", status: "pending" },
    { key: "execute", label: "Enterprise System", status: "pending" },
  ],
};

export const ACTIVITY_FEED: ActivityItem[] = [
  { id: "a1", message: "Travel Agent approved booking TRX-992A.", at: "2026-08-19T14:52:10Z", tone: "success" },
  { id: "a2", message: "Expense Agent routed for human review.", at: "2026-08-19T14:49:38Z", tone: "warning" },
  { id: "a3", message: "Trust Score updated for Dispute Agent (91 → 87).", at: "2026-08-19T14:46:02Z", tone: "info" },
  { id: "a4", message: "Policy version v2.4.1 deployed to production.", at: "2026-08-19T14:41:55Z", tone: "info" },
  { id: "a5", message: "Simulation predicted compliance violation — blocked.", at: "2026-08-19T14:38:19Z", tone: "danger" },
  { id: "a6", message: "Governance Ledger synchronized (18,402 entries).", at: "2026-08-19T14:35:44Z", tone: "info" },
];

export const AGENTS: Agent[] = [
  {
    id: "agt-travel-01",
    name: "Travel Booking Agent",
    capability: "Travel & Expense",
    owner: "Corporate Services",
    lifecycle: "trusted",
    trustScore: 94,
    trustDelta: 1.2,
    decisionsToday: 4820,
    lastActiveAt: "2026-08-19T14:52:10Z",
    factors: [
      { key: "behavior", label: "Behavior Consistency", score: 96, weight: 0.22 },
      { key: "policy", label: "Policy Compliance", score: 99, weight: 0.24 },
      { key: "risk", label: "Risk Exposure", score: 90, weight: 0.2 },
      { key: "context", label: "Context Awareness", score: 92, weight: 0.14 },
      { key: "history", label: "Historical Reliability", score: 95, weight: 0.2 },
    ],
    model: "GPT-4-Turbo",
    authorityLevel: 2,
    lastAuditAt: "2026-08-12",
    lastDecision: "Approved booking TRX-992A",
  },
  {
    id: "agt-expense-02",
    name: "Expense Approval Agent",
    capability: "Travel & Expense",
    owner: "Finance Operations",
    lifecycle: "review",
    trustScore: 72,
    trustDelta: -6.4,
    decisionsToday: 1930,
    lastActiveAt: "2026-08-19T14:49:38Z",
    factors: [
      { key: "behavior", label: "Behavior Consistency", score: 68, weight: 0.22 },
      { key: "policy", label: "Policy Compliance", score: 81, weight: 0.24 },
      { key: "risk", label: "Risk Exposure", score: 64, weight: 0.2 },
      { key: "context", label: "Context Awareness", score: 75, weight: 0.14 },
      { key: "history", label: "Historical Reliability", score: 73, weight: 0.2 },
    ],
    model: "Claude-Sonnet-4",
    authorityLevel: 2,
    lastAuditAt: "2026-07-30",
    lastDecision: "Escalated reimbursement TRX-9917",
  },
  {
    id: "agt-dispute-03",
    name: "Dispute Resolution Agent",
    capability: "Customer Servicing",
    owner: "Card Member Services",
    lifecycle: "anomaly",
    trustScore: 87,
    trustDelta: -4.1,
    decisionsToday: 2610,
    lastActiveAt: "2026-08-19T14:46:02Z",
    factors: [
      { key: "behavior", label: "Behavior Consistency", score: 82, weight: 0.22 },
      { key: "policy", label: "Policy Compliance", score: 94, weight: 0.24 },
      { key: "risk", label: "Risk Exposure", score: 85, weight: 0.2 },
      { key: "context", label: "Context Awareness", score: 88, weight: 0.14 },
      { key: "history", label: "Historical Reliability", score: 89, weight: 0.2 },
    ],
    model: "GPT-4o",
    authorityLevel: 3,
    lastAuditAt: "2026-08-05",
    lastDecision: "Issued goodwill credit TRX-9902",
  },
  {
    id: "agt-fraud-04",
    name: "Fraud Detection Agent",
    capability: "Risk & Fraud",
    owner: "Global Risk",
    lifecycle: "trusted",
    trustScore: 97,
    trustDelta: 0.4,
    decisionsToday: 12470,
    lastActiveAt: "2026-08-19T14:53:01Z",
    factors: [
      { key: "behavior", label: "Behavior Consistency", score: 98, weight: 0.22 },
      { key: "policy", label: "Policy Compliance", score: 99, weight: 0.24 },
      { key: "risk", label: "Risk Exposure", score: 95, weight: 0.2 },
      { key: "context", label: "Context Awareness", score: 96, weight: 0.14 },
      { key: "history", label: "Historical Reliability", score: 97, weight: 0.2 },
    ],
    model: "ATLAS-Risk-v3",
    authorityLevel: 4,
    lastAuditAt: "2026-08-18",
    lastDecision: "Froze card TRX-9871",
  },
  {
    id: "agt-payment-05",
    name: "Payment Orchestration Agent",
    capability: "Payments",
    owner: "Payments Platform",
    lifecycle: "healthy",
    trustScore: 89,
    trustDelta: 2.0,
    decisionsToday: 8340,
    lastActiveAt: "2026-08-19T14:51:22Z",
    factors: [
      { key: "behavior", label: "Behavior Consistency", score: 90, weight: 0.22 },
      { key: "policy", label: "Policy Compliance", score: 93, weight: 0.24 },
      { key: "risk", label: "Risk Exposure", score: 84, weight: 0.2 },
      { key: "context", label: "Context Awareness", score: 87, weight: 0.14 },
      { key: "history", label: "Historical Reliability", score: 90, weight: 0.2 },
    ],
    model: "Claude-Opus-4",
    authorityLevel: 3,
    lastAuditAt: "2026-08-09",
    lastDecision: "Blocked settlement TRX-9884",
  },
  {
    id: "agt-onboard-06",
    name: "Merchant Onboarding Agent",
    capability: "Merchant Services",
    owner: "Merchant Platform",
    lifecycle: "onboarding",
    trustScore: 58,
    trustDelta: 5.8,
    decisionsToday: 210,
    lastActiveAt: "2026-08-19T14:30:07Z",
    factors: [
      { key: "behavior", label: "Behavior Consistency", score: 55, weight: 0.22 },
      { key: "policy", label: "Policy Compliance", score: 70, weight: 0.24 },
      { key: "risk", label: "Risk Exposure", score: 48, weight: 0.2 },
      { key: "context", label: "Context Awareness", score: 60, weight: 0.14 },
      { key: "history", label: "Historical Reliability", score: 52, weight: 0.2 },
    ],
    model: "Llama-4-70B",
    authorityLevel: 1,
    lastAuditAt: "2026-08-16",
    lastDecision: "Deferred KYC review MRC-221",
  },
];

export const DECISIONS: Decision[] = [
  {
    id: "EXP-8892-BL",
    agentId: "agt-expense-02",
    agentName: "Expense Approval Agent",
    action: "Approve reimbursement — TechSolutions Inc",
    amountUsd: 12450,
    outcome: "blocked",
    trustScore: 71,
    riskScore: 84,
    policyChecks: [
      { policyId: "pol-04", policyName: "Entertainment Spend Limit", passed: false, detail: "$12,450 exceeds $2,000 cap" },
      { policyId: "pol-14", policyName: "Vendor Transaction Variance", passed: false, detail: "5.9× the vendor's historical average" },
      { policyId: "pol-15", policyName: "Operating-Hours Window", passed: false, detail: "Originated 03:14 EST" },
      { policyId: "pol-06", policyName: "Sanctions Screening", passed: true },
    ],
    decidedAt: "2026-08-19T07:14:22Z",
    latencyMs: 214,
    rationale:
      "Blocked pending human review. Three compounding risk factors crossed the autonomous execution threshold simultaneously, and the agent's trust score had already fallen 23 points in the preceding 24 hours.",
    investigation: {
      summary:
        "The transaction requested by the Expense Approval Agent for $12,450.00 to vendor 'TechSolutions Inc' was blocked due to multiple compounding risk factors crossing the autonomous execution threshold.",
      criticalFactors: [
        {
          key: "threshold",
          title: "Spending Threshold Anomaly",
          detail:
            "Vendor 'TechSolutions Inc' has a historical average transaction size of $2,100. This request exceeds the 3-sigma standard deviation for the vendor category.",
          severity: "critical",
        },
        {
          key: "timing",
          title: "Behavioural Timing",
          detail:
            "Request originated at 03:14 EST, outside normal operating hours for the initiating department.",
          severity: "high",
        },
      ],
      actionRequired:
        "A human operator with Level 2 clearance must review the vendor history and confirm the legitimacy of this off-hours, high-value request.",
      trustBefore: 94,
      confidence: 98,
      riskVector: { financial: 90, fraud: 85, operational: 35, regulatory: 20 },
      merchant: "TechSolutions Inc",
      requestedAtLocal: "03:14 EST",
      trace: [
        { key: "request", label: "Ingestion", status: "done" },
        { key: "policy", label: "Validation", status: "done" },
        { key: "trust", label: "Model Eval", status: "done" },
        { key: "simulation", label: "Risk Assessment", status: "failed", detail: "Block triggered" },
        { key: "ledger", label: "Gov Ledger", status: "done" },
      ],
    },
  },
  {
    id: "TRX-992A",
    agentId: "agt-travel-01",
    agentName: "Travel Booking Agent",
    action: "Book flight LHR → JFK, business class",
    amountUsd: 4820,
    outcome: "approved",
    trustScore: 94,
    riskScore: 12,
    policyChecks: [
      { policyId: "pol-01", policyName: "Travel Spend Ceiling", passed: true, detail: "$4,820 under $6,000 cap" },
      { policyId: "pol-02", policyName: "Preferred Carrier", passed: true },
      { policyId: "pol-03", policyName: "Advance Booking Window", passed: true, detail: "21 days ahead" },
      { policyId: "pol-06", policyName: "Sanctions Screening", passed: true },
    ],
    decidedAt: "2026-08-19T14:52:10Z",
    latencyMs: 284,
    rationale:
      "Approved. The agent's trust score (94) exceeds the 85 threshold for travel bookings above $2,500. All six applicable policies passed, and simulation projected a 96% probability of a compliant, low-impact outcome. No behavioural drift detected in the last 30 days.",
  },
  {
    id: "TRX-9917",
    agentId: "agt-expense-02",
    agentName: "Expense Approval Agent",
    action: "Approve reimbursement — client dinner, 14 attendees",
    amountUsd: 3180,
    outcome: "escalated",
    trustScore: 72,
    riskScore: 61,
    policyChecks: [
      { policyId: "pol-04", policyName: "Entertainment Spend Limit", passed: false, detail: "$3,180 exceeds $2,000 cap" },
      { policyId: "pol-05", policyName: "Receipt Completeness", passed: true },
      { policyId: "pol-06", policyName: "Sanctions Screening", passed: true },
    ],
    decidedAt: "2026-08-19T14:49:38Z",
    latencyMs: 412,
    rationale:
      "Escalated to human review. The agent's trust score fell to 72 after six policy exceptions in the last 24 hours — below the 80 threshold required for autonomous approval at this amount. The entertainment spend cap was also breached by $1,180.",
  },
  {
    id: "TRX-9902",
    agentId: "agt-dispute-03",
    agentName: "Dispute Resolution Agent",
    action: "Issue goodwill credit — disputed charge",
    amountUsd: 240,
    outcome: "approved",
    trustScore: 87,
    riskScore: 24,
    policyChecks: [
      { policyId: "pol-07", policyName: "Goodwill Credit Ceiling", passed: true, detail: "$240 under $500 cap" },
      { policyId: "pol-08", policyName: "Repeat Claimant Check", passed: true },
    ],
    decidedAt: "2026-08-19T14:46:02Z",
    latencyMs: 198,
    rationale:
      "Approved. Credit amount is well within the goodwill ceiling and the card member has no repeat-claim history. Trust score dipped 4.1 points this week but remains above the 85 threshold for this action class.",
  },
  {
    id: "TRX-9884",
    agentId: "agt-payment-05",
    agentName: "Payment Orchestration Agent",
    action: "Route settlement batch — EU corridor",
    amountUsd: 1284000,
    outcome: "blocked",
    trustScore: 89,
    riskScore: 88,
    policyChecks: [
      { policyId: "pol-09", policyName: "Cross-Border Settlement Cap", passed: false, detail: "$1.28M exceeds $1M single-batch cap" },
      { policyId: "pol-06", policyName: "Sanctions Screening", passed: true },
      { policyId: "pol-10", policyName: "Liquidity Buffer", passed: false, detail: "Buffer would fall to 3.2%" },
    ],
    decidedAt: "2026-08-19T14:38:19Z",
    latencyMs: 631,
    rationale:
      "Blocked before execution. Simulation projected a 71% probability of breaching the intraday liquidity buffer. Two policies failed, including a hard cap on single-batch cross-border settlement. Recommended action: split into three batches under $500K.",
  },
  {
    id: "TRX-9871",
    agentId: "agt-fraud-04",
    agentName: "Fraud Detection Agent",
    action: "Freeze card — suspected account takeover",
    amountUsd: null,
    outcome: "approved",
    trustScore: 97,
    riskScore: 8,
    policyChecks: [
      { policyId: "pol-11", policyName: "Freeze Authorization", passed: true },
      { policyId: "pol-12", policyName: "Card Member Notification", passed: true },
    ],
    decidedAt: "2026-08-19T14:31:47Z",
    latencyMs: 94,
    rationale:
      "Approved. Highest-trust agent in the estate (97) acting within its designated authority. Device fingerprint and geo-velocity signals both indicate account takeover with high confidence.",
  },
];

export const POLICIES: Policy[] = [
  { id: "pol-01", name: "Travel Spend Ceiling", version: "v2.4.1", scope: "Travel & Expense agents", enabled: true, severity: "high", updatedAt: "2026-08-19T14:41:55Z", evaluations24h: 48200, violations24h: 12 },
  { id: "pol-04", name: "Entertainment Spend Limit", version: "v1.9.0", scope: "Expense agents", enabled: true, severity: "medium", updatedAt: "2026-08-17T09:12:00Z", evaluations24h: 19300, violations24h: 61 },
  { id: "pol-06", name: "Sanctions Screening", version: "v5.0.2", scope: "All agents", enabled: true, severity: "critical", updatedAt: "2026-08-12T16:04:30Z", evaluations24h: 241000, violations24h: 0 },
  { id: "pol-09", name: "Cross-Border Settlement Cap", version: "v3.1.0", scope: "Payment agents", enabled: true, severity: "critical", updatedAt: "2026-08-15T11:22:10Z", evaluations24h: 8340, violations24h: 3 },
  { id: "pol-10", name: "Liquidity Buffer", version: "v2.0.4", scope: "Payment agents", enabled: true, severity: "high", updatedAt: "2026-08-18T08:47:19Z", evaluations24h: 8340, violations24h: 7 },
  { id: "pol-07", name: "Goodwill Credit Ceiling", version: "v1.4.2", scope: "Servicing agents", enabled: true, severity: "low", updatedAt: "2026-08-10T13:55:41Z", evaluations24h: 26100, violations24h: 18 },
  { id: "pol-13", name: "After-Hours Autonomy Freeze", version: "v0.9.0", scope: "All agents", enabled: false, severity: "medium", updatedAt: "2026-08-05T18:20:00Z", evaluations24h: 0, violations24h: 0 },
];

export const SIMULATIONS: SimulationRun[] = [
  {
    id: "sim-4472",
    decisionId: "EXP-8892-BL",
    scenario: "Auto-approve $12,450 reimbursement to TechSolutions Inc at 03:14 EST",
    agentName: "Expense Approval Agent",
    amountUsd: 12450,
    trustScore: 71,
    confidence: 99.2,
    request: [
      { label: "Agent", value: "Expense Approval Agent" },
      { label: "Department", value: "Finance Operations" },
      { label: "Action", value: "Approve Reimbursement" },
      { label: "Amount", value: "$12,450.00" },
      { label: "Merchant", value: "TechSolutions Inc" },
      { label: "Time", value: "03:14 EST" },
      { label: "Current Trust", value: "71 / 100" },
      { label: "Policy Active", value: "v2.4.1" },
    ],
    outcomes: [
      {
        label: "Approve",
        probability: 0.18,
        financialImpactUsd: -12450,
        riskScore: 84,
        compliant: false,
        customerExperience: "High",
        complianceRisk: "Medium",
      },
      {
        label: "Human Review",
        probability: 0.64,
        financialImpactUsd: -12450,
        riskScore: 22,
        compliant: true,
        customerExperience: "Good",
        complianceRisk: "Safe",
        recommended: true,
      },
      {
        label: "Block",
        probability: 0.18,
        financialImpactUsd: 0,
        riskScore: 31,
        compliant: true,
        customerExperience: "Poor",
        complianceRisk: "Safe",
      },
    ],
    recommendation: "escalated",
    ranAt: "2026-08-19T07:14:22Z",
    durationMs: 214,
  },
  {
    id: "sim-4471",
    decisionId: "TRX-9884",
    scenario: "Route $1.28M EU settlement batch as a single transfer",
    agentName: "Payment Orchestration Agent",
    amountUsd: 1284000,
    trustScore: 89,
    confidence: 97.4,
    request: [
      { label: "Agent", value: "Payment Orchestration Agent" },
      { label: "Department", value: "Payments Platform" },
      { label: "Action", value: "Route Settlement Batch" },
      { label: "Amount", value: "$1,284,000.00" },
      { label: "Corridor", value: "EU" },
      { label: "Current Trust", value: "89 / 100" },
    ],
    outcomes: [
      { label: "Settles cleanly", probability: 0.29, financialImpactUsd: 0, riskScore: 22, compliant: true, customerExperience: "Good", complianceRisk: "Safe" },
      { label: "Breaches liquidity buffer", probability: 0.71, financialImpactUsd: -184000, riskScore: 88, compliant: false, customerExperience: "Poor", complianceRisk: "High" },
      { label: "Split into three batches", probability: 0.92, financialImpactUsd: -2400, riskScore: 18, compliant: true, customerExperience: "Good", complianceRisk: "Safe", recommended: true },
    ],
    recommendation: "blocked",
    ranAt: "2026-08-19T14:38:19Z",
    durationMs: 631,
  },
  {
    id: "sim-4470",
    decisionId: "TRX-992A",
    scenario: "Book business-class LHR to JFK at $4,820",
    agentName: "Travel Booking Agent",
    amountUsd: 4820,
    trustScore: 94,
    confidence: 99.6,
    request: [
      { label: "Agent", value: "Travel Booking Agent" },
      { label: "Department", value: "Corporate Services" },
      { label: "Action", value: "Book Flight" },
      { label: "Amount", value: "$4,820.00" },
      { label: "Route", value: "LHR to JFK" },
      { label: "Current Trust", value: "94 / 100" },
    ],
    outcomes: [
      { label: "Compliant booking", probability: 0.96, financialImpactUsd: -4820, riskScore: 12, compliant: true, customerExperience: "High", complianceRisk: "Safe", recommended: true },
      { label: "Fare change breaches cap", probability: 0.04, financialImpactUsd: -6400, riskScore: 58, compliant: false, customerExperience: "Good", complianceRisk: "Medium" },
    ],
    recommendation: "approved",
    ranAt: "2026-08-19T14:52:10Z",
    durationMs: 284,
  },
];

export function getAgent(id: string): Agent | undefined {
  return AGENTS.find((a) => a.id === id);
}

export function getDecision(id: string): Decision | undefined {
  return DECISIONS.find((d) => d.id === id);
}

export function getSimulationForDecision(decisionId: string): SimulationRun | undefined {
  return SIMULATIONS.find((s) => s.decisionId === decisionId);
}
