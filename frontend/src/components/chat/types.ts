// ── Structured Chat Message Types ────────────────────────────────────────────
// The backend returns messages with a `type` field that determines rendering.

export type MessageType =
  | "text"
  | "action_preview"
  | "progress"
  | "question"
  | "metrics";

export interface SequenceStepPreview {
  day: number;
  channel: "email" | "linkedin" | "sms" | "call";
  description: string;
}

export interface ActionPreviewData {
  title: string;
  target: string;
  qualified: string;
  sequence_name?: string;
  steps: SequenceStepPreview[];
  campaign_id?: string;
}

export interface ProgressStep {
  label: string;
  status: "done" | "in_progress" | "pending";
  detail?: string;
}

export interface ProgressData {
  steps: ProgressStep[];
}

export interface MetricItem {
  label: string;
  value: string | number;
  change?: string;
  changeDirection?: "up" | "down" | "neutral";
  progress?: number; // 0-100 for bar
}

export interface MetricAlert {
  type: "warning" | "info";
  text: string;
}

export interface MetricsData {
  title: string;
  metrics: MetricItem[];
  alerts?: MetricAlert[];
}

export interface QuestionOption {
  label: string;
  value: string;
  icon?: string;
}

export interface QuestionItem {
  question: string;
  options: QuestionOption[];
  multi?: boolean;
}

export interface QuestionData {
  questions: QuestionItem[];
}

export interface StructuredContent {
  type: MessageType;
  text?: string;
  data?: ActionPreviewData | ProgressData | MetricsData | QuestionData;
}

export interface ChatMessageData {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  structured?: StructuredContent;
  timestamp: Date;
  sources?: string[];
  isStreaming?: boolean;
}

// ── Slash Commands ──────────────────────────────────────────────────────────

export interface SlashCommand {
  command: string;
  description: string;
  icon: string;
}

export const SLASH_COMMANDS: SlashCommand[] = [
  { command: "/campaign", description: "Launch a new campaign", icon: "rocket" },
  { command: "/leads", description: "Find or manage leads", icon: "users" },
  { command: "/status", description: "Check performance", icon: "chart" },
  { command: "/deliverability", description: "Email health check", icon: "mail" },
  { command: "/sequences", description: "Active sequence summary", icon: "git-branch" },
  { command: "/warmup", description: "Warmup status and next steps", icon: "flame" },
  { command: "/compliance", description: "Compliance checklist", icon: "shield" },
  { command: "/help", description: "What can I do?", icon: "help" },
];

// ── Quick Action Chips ──────────────────────────────────────────────────────

export interface QuickAction {
  label: string;
  icon: string;
  message: string;
}

export const QUICK_ACTIONS: QuickAction[] = [
  { label: "New Campaign", icon: "rocket", message: "/campaign" },
  { label: "Status", icon: "chart", message: "/status" },
  { label: "Find Leads", icon: "search", message: "/leads" },
  { label: "Deliverability", icon: "mail", message: "/deliverability" },
];

// ── Placeholder rotation ────────────────────────────────────────────────────

export const PLACEHOLDER_EXAMPLES = [
  "Find me 50 periodontists in Texas...",
  "How's our email deliverability?",
  "Launch a campaign for oral surgeons in California",
  "What's our best performing sequence?",
  "Check compliance for our new lead list",
  "Show me reply inbox stats",
];
