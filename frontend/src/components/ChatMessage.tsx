import { useState } from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import type {
  ChatMessageData,
  UserMessage,
  AgentProgressMessage,
  FindingMessage,
  ReportMessage,
  ErrorMessage,
} from '../types';

/* ─── Severity badge config ─────────────────────────────────────────── */

const severityConfig: Record<string, { label: string; dot: string; bg: string; text: string }> = {
  Crítico: { label: 'Crítico', dot: 'bg-red-500', bg: 'bg-red-500/10', text: 'text-red-400' },
  Alto: { label: 'Alto', dot: 'bg-orange-500', bg: 'bg-orange-500/10', text: 'text-orange-400' },
  Medio: { label: 'Medio', dot: 'bg-yellow-500', bg: 'bg-yellow-500/10', text: 'text-yellow-400' },
  Bajo: { label: 'Bajo', dot: 'bg-green-500', bg: 'bg-green-500/10', text: 'text-green-400' },
};

function SeverityBadge({ severity }: { severity: string }) {
  const cfg = severityConfig[severity] ?? severityConfig.Bajo;
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-semibold ${cfg.bg} ${cfg.text}`}
    >
      <span className={`w-2 h-2 rounded-full ${cfg.dot}`} />
      {cfg.label}
    </span>
  );
}

/* ─── Collapsible section ───────────────────────────────────────────── */

function CollapsibleSection({
  title,
  children,
  defaultOpen = false,
}: {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border border-slate-700/50 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between gap-2 px-3 py-2 text-xs font-medium text-slate-400 hover:text-slate-200 hover:bg-slate-700/30 transition-colors"
        aria-expanded={open}
        aria-label={title}
      >
        <span>{title}</span>
        <svg
          className={`w-3.5 h-3.5 transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {open && <div className="px-3 pb-3 text-sm text-slate-300 leading-relaxed">{children}</div>}
    </div>
  );
}

/* ─── Sub-views ─────────────────────────────────────────────────────── */

function UserMessageView({ message }: { message: UserMessage }) {
  return (
    <div className="flex items-start gap-3 animate-fade-in">
      {/* User avatar */}
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-sm font-bold text-white shadow-md">
        U
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1.5">
          <span className="text-sm font-semibold text-slate-200">Tú</span>
          <span className="text-[10px] text-slate-600">
            {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
        </div>
        <div className="rounded-xl overflow-hidden border border-slate-700/60 bg-slate-850">
          <SyntaxHighlighter
            language="typescript"
            style={oneDark}
            showLineNumbers
            customStyle={{
              margin: 0,
              borderRadius: 0,
              fontSize: '0.8rem',
              lineHeight: '1.5',
              maxHeight: '400px',
            }}
            wrapLongLines
          >
            {message.code}
          </SyntaxHighlighter>
        </div>
      </div>
    </div>
  );
}

function AgentProgressView({ message }: { message: AgentProgressMessage }) {
  const allDone = message.agents.every((a) => a.status === 'complete' || a.status === 'error');
  return (
    <div className="animate-fade-in">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-sm font-semibold text-slate-300">{message.label}</span>
        {!allDone && (
          <span className="flex gap-0.5">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-bounce" style={{ animationDelay: '0ms' }} />
            <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-bounce" style={{ animationDelay: '150ms' }} />
            <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-bounce" style={{ animationDelay: '300ms' }} />
          </span>
        )}
        {allDone && (
          <span className="text-xs text-green-400 font-medium">
            <svg className="w-3.5 h-3.5 inline-block mr-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
            Completado
          </span>
        )}
      </div>
      <div className="flex flex-wrap gap-2">
        {message.agents.map((agent) => (
          <div
            key={agent.id}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs transition-all duration-300 ${
              agent.status === 'analyzing'
                ? 'bg-slate-700/60 ring-1 ring-slate-500/30'
                : agent.status === 'complete'
                  ? 'bg-slate-700/30 opacity-80'
                  : agent.status === 'error'
                    ? 'bg-red-900/20'
                    : 'bg-slate-800/50 opacity-60'
            }`}
            style={{
              borderLeft: `3px solid ${agent.color}`,
            }}
            role="status"
            aria-label={`${agent.name}: ${agent.status}`}
          >
            <span
              className="text-xs font-bold"
              style={{ color: agent.color }}
              aria-hidden="true"
            >
              {agent.icon}
            </span>
            <span className="font-medium text-slate-200">{agent.name}</span>
            {agent.status === 'analyzing' && (
              <span className="flex gap-0.5 ml-1">
                <span className="w-1 h-1 rounded-full bg-current animate-pulse" style={{ color: agent.color }} />
                <span className="w-1 h-1 rounded-full bg-current animate-pulse" style={{ color: agent.color, animationDelay: '200ms' }} />
                <span className="w-1 h-1 rounded-full bg-current animate-pulse" style={{ color: agent.color, animationDelay: '400ms' }} />
              </span>
            )}
            {agent.status === 'complete' && (
              <svg className="w-3 h-3 text-green-400 ml-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            )}
            {agent.status === 'error' && (
              <svg className="w-3 h-3 text-red-400 ml-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function FindingView({ message }: { message: FindingMessage }) {
  const { finding, agentName, agentIcon, agentColor, round } = message;

  return (
    <div className="flex items-start gap-3 animate-fade-in">
      {/* Agent avatar */}
      <div
        className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-lg shadow-md"
        style={{ backgroundColor: `${agentColor}20` }}
        aria-label={agentName}
      >
        <span className="text-xs font-bold" aria-hidden="true">
          {agentIcon}
        </span>
      </div>
      <div className="flex-1 min-w-0">
        {/* Header */}
        <div className="flex items-center gap-2 mb-1.5 flex-wrap">
          <span className="text-sm font-semibold" style={{ color: agentColor }}>
            {agentName}
          </span>
          <SeverityBadge severity={finding.impacto} />
          <span className="text-[10px] text-slate-600 bg-slate-700/40 px-1.5 py-0.5 rounded-full font-mono">
            R{round}
          </span>
        </div>

        {/* Finding conclusion (bold, prominent) */}
        <div className="mb-2">
          <p className="text-sm font-bold text-white leading-relaxed">
            {finding.hallazgo}
          </p>
        </div>

        {/* Detail (collapsible) */}
        {finding.detalle && (
          <div className="mb-1.5">
            <CollapsibleSection title="Detalle">
              <p>{finding.detalle}</p>
            </CollapsibleSection>
          </div>
        )}

        {/* Proposal (collapsible) */}
        {finding.propuesta && (
          <CollapsibleSection title="Propuesta">
            <p>{finding.propuesta}</p>
          </CollapsibleSection>
        )}
      </div>
    </div>
  );
}

function ReportView({ message }: { message: ReportMessage }) {
  const { report, sessionId } = message;

  // Count by severity
  const counts: Record<string, number> = { Crítico: 0, Alto: 0, Medio: 0, Bajo: 0 };
  for (const f of report.findings) {
    if (counts[f.impacto] !== undefined) counts[f.impacto]++;
    else counts.Bajo++;
  }

  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);

  return (
    <div className="animate-fade-in">
      {/* Report header */}
      <div className="flex items-center gap-2 mb-3">
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-emerald-600/30 flex items-center justify-center">
          <svg className="w-4 h-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
          </svg>
        </div>
        <div>
          <h3 className="text-sm font-bold text-white">Reporte Consolidado</h3>
          <p className="text-[10px] text-slate-500 font-mono">
            {report.participants.length} agentes · {report.rounds} rondas · ID: {sessionId.slice(0, 8)}...
          </p>
        </div>
      </div>

      {/* Executive summary */}
      <div className="bg-slate-700/20 border border-slate-700/50 rounded-lg p-3 mb-3">
        <p className="text-xs text-slate-400 font-semibold uppercase tracking-wider mb-1">
          Resumen Ejecutivo
        </p>
        <p className="text-sm text-slate-200 leading-relaxed whitespace-pre-wrap">
          {report.summary}
        </p>
      </div>

      {/* Severity distribution */}
      <div className="flex flex-wrap gap-2 mb-3">
        {Object.entries(counts).map(([sev, count]) => {
          if (count === 0) return null;
          const cfg = severityConfig[sev] ?? severityConfig.Bajo;
          return (
            <span
              key={sev}
              className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${cfg.bg} ${cfg.text}`}
            >
              <span className={`w-2 h-2 rounded-full ${cfg.dot}`} />
              {count} {sev}
            </span>
          );
        })}
        <span className="text-xs text-slate-500 self-center">
          {report.findings.length} hallazgo{report.findings.length !== 1 ? 's' : ''} en total
        </span>
      </div>

      {/* Consolidated findings */}
      <div className="space-y-2">
        {report.findings.map((finding, idx) => (
          <div
            key={idx}
            className="border border-slate-700/50 rounded-lg overflow-hidden transition-colors hover:border-slate-600/50"
          >
            <button
              onClick={() => setExpandedIdx(expandedIdx === idx ? null : idx)}
              className="w-full flex items-center justify-between gap-3 px-3 py-2.5 text-left"
              aria-expanded={expandedIdx === idx}
              aria-label={`Hallazgo ${idx + 1}`}
            >
              <div className="flex items-center gap-2 min-w-0">
                <span className="text-xs text-slate-500 font-mono flex-shrink-0 w-5">
                  {idx + 1}
                </span>
                <SeverityBadge severity={finding.impacto} />
                <span className="text-sm font-medium text-slate-200 truncate">
                  {finding.hallazgo}
                </span>
              </div>
              <svg
                className={`w-3.5 h-3.5 text-slate-500 flex-shrink-0 transition-transform duration-200 ${
                  expandedIdx === idx ? 'rotate-180' : ''
                }`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {expandedIdx === idx && (
              <div className="px-3 pb-3 space-y-2 border-t border-slate-700/50 pt-2">
                <p className="text-sm text-slate-300">
                  <span className="text-slate-500 font-medium">Detalle: </span>
                  {finding.detalle}
                </p>
                <p className="text-sm text-slate-300">
                  <span className="text-slate-500 font-medium">Propuesta: </span>
                  {finding.propuesta}
                </p>
                {Object.keys(finding.votes).length > 0 && (
                  <div>
                    <span className="text-xs text-slate-500 font-medium">Votos: </span>
                    <div className="flex flex-wrap gap-1.5 mt-1">
                      {Object.entries(finding.votes).map(([agentId, vote]) => (
                        <span
                          key={agentId}
                          className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded bg-slate-700/40 text-slate-400"
                        >
                          {agentId}: {vote}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                <div className="flex items-center gap-2 text-xs text-slate-500">
                  <span>Consenso: {Math.round(finding.consensus_score * 100)}%</span>
                  <span className="text-slate-700">·</span>
                  <span>{finding.consensus_level}</span>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Session ID footer */}
      <p className="text-[10px] text-slate-600 font-mono text-center mt-3">
        Sesión: {sessionId}
      </p>
    </div>
  );
}

function ErrorView({ message }: { message: ErrorMessage }) {
  return (
    <div
      className="flex items-start gap-3 animate-fade-in p-4 rounded-xl border border-red-500/30 bg-red-500/5"
      role="alert"
    >
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-red-500/20 flex items-center justify-center">
        <svg className="w-4 h-4 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
        </svg>
      </div>
      <div>
        <p className="text-sm font-semibold text-red-400 mb-1">Error</p>
        <p className="text-sm text-slate-300">{message.text}</p>
      </div>
    </div>
  );
}

/* ─── Main component ────────────────────────────────────────────────── */

interface ChatMessageProps {
  message: ChatMessageData;
}

export default function ChatMessage({ message }: ChatMessageProps) {
  switch (message.role) {
    case 'user':
      return <UserMessageView message={message} />;
    case 'agent-progress':
      return <AgentProgressView message={message} />;
    case 'finding':
      return <FindingView message={message} />;
    case 'report':
      return <ReportView message={message} />;
    case 'error':
      return <ErrorView message={message} />;
    default:
      return null;
  }
}
