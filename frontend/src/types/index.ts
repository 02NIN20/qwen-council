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

export type AgentId = 'security' | 'architecture' | 'quality' | 'performance' | 'ux' | 'vision';

export type AgentStatus = 'waiting' | 'analyzing' | 'complete' | 'error';

export interface AgentInfo {
  id: AgentId;
  name: string;
  icon: string;
  color: string;
  specialty: string;
}

export const AGENTS: AgentInfo[] = [
  {
    id: 'security',
    name: 'Security',
    icon: 'S',
    color: '#EF4444',
    specialty: 'OWASP, SQLi, XSS, Secrets',
  },
  {
    id: 'architecture',
    name: 'Architecture',
    icon: 'A',
    color: '#3B82F6',
    specialty: 'SOLID, Patterns, Coupling',
  },
  {
    id: 'quality',
    name: 'Quality',
    icon: 'Q',
    color: '#22C55E',
    specialty: 'Style, Tests, Complexity',
  },
  {
    id: 'performance',
    name: 'Performance',
    icon: 'P',
    color: '#F59E0B',
    specialty: 'N+1, Caching, Bottlenecks',
  },
  {
    id: 'ux',
    name: 'UX / Accessibility',
    icon: 'U',
    color: '#A855F7',
    specialty: 'a11y, i18n, Contrast',
  },
  {
    id: 'vision',
    name: 'Vision',
    icon: 'V',
    color: '#EC4899',
    specialty: 'Design, Visual Consistency, UI',
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
