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

export type AgentId = 'security' | 'architecture' | 'quality' | 'performance' | 'ux';

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
    icon: '\u{1F6E1}\uFE0F',
    color: '#EF4444',
    specialty: 'OWASP, SQLi, XSS, Secrets',
  },
  {
    id: 'architecture',
    name: 'Arquitectura',
    icon: '\u{1F3D7}\uFE0F',
    color: '#3B82F6',
    specialty: 'SOLID, Patrones, Acoplamiento',
  },
  {
    id: 'quality',
    name: 'Calidad',
    icon: '\u{1F4D0}',
    color: '#22C55E',
    specialty: 'Estilo, Tests, Complejidad',
  },
  {
    id: 'performance',
    name: 'Performance',
    icon: '\u26A1',
    color: '#F59E0B',
    specialty: 'N+1, Caché, Cuellos de botella',
  },
  {
    id: 'ux',
    name: 'UX / Accesibilidad',
    icon: '\u267F',
    color: '#A855F7',
    specialty: 'a11y, i18n, Contraste',
  },
];

export type AppPhase = 'idle' | 'analyzing' | 'round1' | 'round2' | 'round3' | 'complete' | 'error';
