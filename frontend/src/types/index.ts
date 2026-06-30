export interface Finding {
  agent: string;
  hallazgo: string;
  detalle: string;
  impacto: 'Crítico' | 'Alto' | 'Medio' | 'Bajo';
  propuesta: string;
  ronda: number;
}

export interface ConsolidatedFinding {
  hallazgo: string;
  detalle: string;
  impacto: string;
  propuesta: string;
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
  rounds: {
    round_1: Finding[];
    round_2: Finding[];
    round_3: Finding[];
  };
  rounds_raw?: {
    context_preview?: string;
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
    name: 'Seguridad',
    icon: 'S',
    color: '#EF4444',
    specialty: 'OWASP, SQLi, XSS, Secrets',
  },
  {
    id: 'architecture',
    name: 'Arquitectura',
    icon: 'A',
    color: '#3B82F6',
    specialty: 'SOLID, Patrones, Acoplamiento',
  },
  {
    id: 'quality',
    name: 'Calidad',
    icon: 'Q',
    color: '#22C55E',
    specialty: 'Estilo, Tests, Complejidad',
  },
  {
    id: 'performance',
    name: 'Performance',
    icon: 'P',
    color: '#F59E0B',
    specialty: 'N+1, Caché, Cuellos de botella',
  },
  {
    id: 'ux',
    name: 'UX / Accesibilidad',
    icon: 'U',
    color: '#A855F7',
    specialty: 'a11y, i18n, Contraste',
  },
  {
    id: 'vision',
    name: 'Visión',
    icon: 'V',
    color: '#EC4899',
    specialty: 'Diseño, Consistencia Visual, UI',
  },
];

export type AppPhase = 'idle' | 'analyzing' | 'round1' | 'round2' | 'round3' | 'complete' | 'error';

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

export type ChatMessageData =
  | UserMessage
  | AgentProgressMessage
  | FindingMessage
  | ReportMessage
  | ErrorMessage
  | RoundTransitionMessage;
