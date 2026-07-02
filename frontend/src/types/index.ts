export interface Finding {
  title: string;
  detail: string;
  impact: 'Critical' | 'High' | 'Medium' | 'Low';
  proposal: string;
  agent: string;
  round_num: number;
}

export interface AgentMetrics {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  findings_count: number;
}

export interface BudgetCall {
  label: string;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
}

export interface BudgetInfo {
  config: {
    max_input_tokens: number;
    max_output_tokens: number;
    max_cost_usd: number;
    max_rounds: number;
  };
  used: {
    input_tokens: number;
    output_tokens: number;
    cost_usd: number;
    call_count: number;
  };
  exhausted: boolean;
  per_call: BudgetCall[];
}

export interface TokenUsage {
  per_agent: Record<string, AgentMetrics>;
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  estimated_cost_usd: number;
  model: string;
  budget: BudgetInfo;
}

export interface Report {
  session_id: string;
  created_at: string;
  findings: Finding[];
  summary: string;
  risk_overview: string;
  detailed_review: string;
  remediation_roadmap: string;
  rounds: number;
  participants: string[];
  agent_metrics: Record<string, AgentMetrics>;
  token_usage: TokenUsage;
}

export interface ReviewResponse {
  session_id: string;
  report: Report;
  round_data: {
    round_1: Record<string, Finding[]>;
    round_2: Record<string, Finding[]>;
    round_3: Record<string, Finding[]>;
  };
}

export interface SessionDetail {
  id: string;
  code_preview: string;
  finding_count: number;
  findings_json: any;
  created_at: string;
}

export interface SessionSummary {
  id: string;
  code_preview: string;
  finding_count: number;
  created_at: string;
}

export interface FileContent {
  filename: string;
  content: string;
  language?: string;
}

export type AgentId = 'critic' | 'analyst' | 'architect' | 'engineer' | 'researcher' | 'coordinator'
  | 'security' | 'architecture' | 'quality' | 'performance' | 'ux' | 'vision';

export type AgentStatus = 'waiting' | 'analyzing' | 'complete' | 'error';

export interface AgentInfo {
  id: AgentId;
  name: string;
  icon: string;
  color: string;
  specialty: string;
}

export const AGENTS: AgentInfo[] = [
  // ── Code Review Core Agents ──
  {
    id: 'critic',
    name: 'Critic',
    icon: 'C',
    color: '#EF4444',
    specialty: 'Security, Quality, Style, Validation',
  },
  {
    id: 'analyst',
    name: 'Analyst',
    icon: 'A',
    color: '#3B82F6',
    specialty: 'Patterns, Complexity, Static Analysis',
  },
  {
    id: 'architect',
    name: 'Architect',
    icon: 'R',
    color: '#22C55E',
    specialty: 'SOLID, Dependencies, Scalability',
  },
  {
    id: 'engineer',
    name: 'Engineer',
    icon: 'E',
    color: '#F59E0B',
    specialty: 'Fixes, Refactoring, Optimization',
  },
  {
    id: 'researcher',
    name: 'Researcher',
    icon: 'D',
    color: '#A855F7',
    specialty: 'Docs, Best Practices, References',
  },
  {
    id: 'coordinator',
    name: 'Coordinator',
    icon: 'O',
    color: '#EC4899',
    specialty: 'Orchestration, Synthesis, Escalation',
  },
];

export type AppPhase = 'idle' | 'analyzing' | 'round1' | 'round2' | 'round3' | 'complete' | 'error';

// ─── General Chat Types ──────────────────────────────────────────────────

export interface AgentContribution {
  agent: string;
  role_description: string;
  answer: string;
}

export interface ChatResponse {
  response: string;
  session_id: string;
  agent_contributions?: AgentContribution[];
}

// ─── Chat Interface Types ────────────────────────────────────────────────

export interface AgentProgress {
  id: string;
  name: string;
  icon: string;
  color: string;
  status: 'waiting' | 'analyzing' | 'complete' | 'error';
}

export interface UserMessage {
  id: string;
  role: 'user';
  content: string;
  code: string;
  fileInfo?: { name: string; size: number; language?: string }[];
  instruction?: string;
  contextPreview?: string;
  timestamp: number;
}

export interface AgentProgressMessage {
  id: string;
  role: 'agent-progress';
  agents: AgentProgress[];
  label: string;
}

export interface FindingMessage {
  id: string;
  role: 'finding';
  finding: Finding;
  agentName: string;
  agentIcon: string;
  agentColor: string;
  round: number;
}

export interface ReportMessage {
  id: string;
  role: 'report';
  report: Report;
  sessionId: string;
}

export interface ErrorMessage {
  id: string;
  role: 'error';
  text: string;
}

export interface RoundTransitionMessage {
  id: string;
  role: 'round-transition';
  round: number;
  label: string;
}

export interface AnswerMessage {
  id: string;
  role: 'answer';
  text: string;
  agentContributions?: AgentContribution[];
  sessionId?: string;
  timestamp?: number;
}

export type ChatMessageData =
  | UserMessage
  | AgentProgressMessage
  | FindingMessage
  | ReportMessage
  | ErrorMessage
  | RoundTransitionMessage
  | AnswerMessage;
