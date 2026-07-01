export interface Finding {
  agent: string;
  title: string;
  detail: string;
  impact: 'Critical' | 'High' | 'Medium' | 'Low';
  proposal: string;
  round_num: number;
}

export interface ConsolidatedFinding {
  title: string;
  detail: string;
  impact: string;
  proposal: string;
  votes: Record<string, string>;
  consensus_level: string;
  consensus_score: number;
}

export interface Report {
  findings: ConsolidatedFinding[];
  summary: string;
  rounds: number;
  participants: string[];
}

export interface ReviewResponse {
  session_id: string;
  report: Report;
  rounds_raw: {
    round_1: Record<string, Finding[]>;
    round_2: Record<string, Finding[]>;
    round_3: Record<string, Finding[]>;
    context_preview?: string;
    instruction?: string;
    files?: { filename: string; size: number; language?: string }[];
    report?: Report;
  };
}

export interface SessionDetail {
  id: string;
  code: string;
  findings_json: any;
  score: number;
  created_at: string;
  last_referenced_at: string | null;
}

export interface SessionSummary {
  id: string;
  code_preview: string;
  score: number;
  created_at: string;
  finding_count: number;
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
