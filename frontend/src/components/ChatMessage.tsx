import { useState, useCallback } from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import type {
  ChatMessageData,
  UserMessage,
  AgentProgressMessage,
  FindingMessage,
  ReportMessage,
  ErrorMessage,
  RoundTransitionMessage,
} from '../types';
import { AGENTS } from '../types';

/* ─── Severity badge ─────────────────────────────────────────────────── */

function SeverityBadge({ severity }: { severity: string }) {
  const classMap: Record<string, string> = {
    Crítico: 'sev-critico',
    Alto: 'sev-alto',
    Medio: 'sev-medio',
    Bajo: 'sev-bajo',
  };
  const cls = classMap[severity] ?? 'sev-bajo';
  return <span className={cls}>{severity.toUpperCase()}</span>;
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
    <div className="border border-retro-border">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between gap-2 px-3 py-2 text-xs font-bold text-gray-500 hover:text-retro-cyan hover:bg-retro-bg transition-colors uppercase tracking-wider"
        aria-expanded={open}
        aria-label={title}
      >
        <span>&gt; {title}</span>
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
      {open && <div className="px-3 pb-3 text-sm text-gray-300 leading-relaxed border-t border-retro-border pt-2">{children}</div>}
    </div>
  );
}

/* ─── Sub-views ─────────────────────────────────────────────────────── */

function UserMessageView({ message }: { message: UserMessage }) {
  const hasFileInfo = message.fileInfo && message.fileInfo.length > 0;
  return (
    <div className="chat-message chat-message-user message-enter">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs font-bold text-retro-cyan">&gt; USER</span>
        <span className="text-[10px] text-gray-600">
          {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </span>
      </div>

      {/* File cards */}
      {hasFileInfo && (
        <div className="flex flex-wrap gap-2 mb-3">
          {message.fileInfo!.map((file, idx) => (
            <div
              key={idx}
              className="inline-flex items-center gap-2 px-3 py-2 border border-retro-border bg-retro-surface text-xs"
            >
              {/* File icon */}
              <span className="text-retro-cyan font-bold text-sm" aria-hidden="true">
                &#x1F4C4;
              </span>
              <div className="flex flex-col">
                <span className="text-gray-200 font-bold leading-tight">{file.name}</span>
                <span className="text-[10px] text-gray-600">
                  {file.size} bytes
                </span>
              </div>
              {file.language && (
                <span className="text-[10px] uppercase tracking-wider text-retro-green border border-retro-border px-1 py-0.5 ml-1">
                  {file.language}
                </span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Code block (only if no fileInfo or as supplementary) */}
      {message.code && (
        <div className="border border-retro-border overflow-hidden mb-3">
          <SyntaxHighlighter
            language="typescript"
            style={oneDark}
            showLineNumbers
            customStyle={{
              margin: 0,
              borderRadius: 0,
              fontSize: '0.75rem',
              lineHeight: '1.5',
              maxHeight: '400px',
              fontFamily: "'Courier New', Courier, monospace",
            }}
            wrapLongLines
          >
            {message.code}
          </SyntaxHighlighter>
        </div>
      )}

      {/* Instruction */}
      {message.instruction && (
        <div className="mt-2 pl-3 border-l-2 border-retro-magenta">
          <p className="text-[10px] text-retro-magenta font-bold uppercase tracking-wider mb-1">
            &gt; INSTRUCTION
          </p>
          <p className="text-xs text-gray-400 italic leading-relaxed">
            {message.instruction}
          </p>
        </div>
      )}

      {/* Context preview collapsible */}
      {message.contextPreview && (
        <CollapsibleSection title="VIEW CONTEXT SENT TO AGENTS">
          <pre className="text-[11px] text-gray-400 font-mono whitespace-pre-wrap overflow-auto max-h-[300px] leading-relaxed border border-retro-border bg-retro-bg p-2">
            {message.contextPreview}
          </pre>
        </CollapsibleSection>
      )}
    </div>
  );
}

function AgentProgressView({ message }: { message: AgentProgressMessage }) {
  const allDone = message.agents.every((a) => a.status === 'complete' || a.status === 'error');
  const analyzingAgents = message.agents.filter((a) => a.status === 'analyzing');

  return (
    <div className="message-enter">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xs font-bold text-gray-400 uppercase tracking-wider">&gt; {message.label}</span>
        {!allDone && (
          <span className="flex gap-0.5">
            <span className="w-1.5 h-1.5 bg-retro-cyan status-dot" />
            <span className="w-1.5 h-1.5 bg-retro-cyan status-dot" style={{ animationDelay: '0.3s' }} />
            <span className="w-1.5 h-1.5 bg-retro-cyan status-dot" style={{ animationDelay: '0.6s' }} />
          </span>
        )}
        {allDone && (
          <span className="text-[10px] text-retro-green font-bold uppercase">
            [OK]
          </span>
        )}
      </div>

      {/* Show which agents are analyzing with their files */}
      {analyzingAgents.length > 0 && (
        <div className="text-[10px] text-gray-600 mb-2 font-mono">
          Reviewing: {analyzingAgents.map((a) => a.name).join(', ')}...
        </div>
      )}

      {allDone && (
        <div className="text-[10px] text-retro-green mb-2 font-mono">
          Round complete &middot; {message.agents.filter((a) => a.status === 'complete').length} agents finished
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        {message.agents.map((agent) => (
          <div
            key={agent.id}
            className="agent-pill"
            style={{
              borderLeft: `3px solid ${agent.color}`,
              opacity: agent.status === 'waiting' ? 0.5 : 1,
            }}
            role="status"
            aria-label={`${agent.name}: ${agent.status}`}
          >
            <span className="text-xs font-bold" style={{ color: agent.color }} aria-hidden="true">
              [{agent.icon}]
            </span>
            <span className="text-gray-300">{agent.name}</span>
            {agent.status === 'analyzing' && (
              <span className="flex gap-0.5 ml-1">
                <span className="w-1 h-1 bg-current animate-pulse" style={{ color: agent.color }} />
                <span className="w-1 h-1 bg-current animate-pulse" style={{ color: agent.color, animationDelay: '200ms' }} />
                <span className="w-1 h-1 bg-current animate-pulse" style={{ color: agent.color, animationDelay: '400ms' }} />
              </span>
            )}
            {agent.status === 'complete' && (
              <span className="text-retro-green text-[10px] ml-1">[OK]</span>
            )}
            {agent.status === 'error' && (
              <span className="text-retro-red text-[10px] ml-1">[ERR]</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function FindingView({ message }: { message: FindingMessage }) {
  const { finding, agentName, agentIcon, agentColor, round } = message;

  // Extract possible filename from finding detail
  const fileMatch = finding.detalle.match(/`([\w\/.-]+\.[a-z]+)`/);
  const mentionedFile = fileMatch ? fileMatch[1] : null;

  const handleCopy = useCallback(() => {
    const text = `[${finding.impacto}] ${finding.hallazgo}\n\nDetail: ${finding.detalle}\n\nProposal: ${finding.propuesta}`;
    navigator.clipboard.writeText(text).catch(() => {});
  }, [finding]);

  return (
    <div
      className="chat-message chat-message-finding message-enter"
      style={{ borderLeftColor: agentColor }}
    >
      {/* Header */}
      <div className="flex items-center gap-2 mb-2 flex-wrap">
        <span className="text-xs font-bold" style={{ color: agentColor }}>
          [{agentIcon}] {agentName}
        </span>
        {mentionedFile && (
          <span className="text-[10px] font-mono text-retro-yellow border border-retro-border px-1.5 py-0.5">
            [{mentionedFile}]
          </span>
        )}
        <SeverityBadge severity={finding.impacto} />
        <span className="text-[10px] text-gray-600 border border-retro-border px-1.5 py-0.5 font-mono">
          R{round}
        </span>
        <button
          onClick={handleCopy}
          className="ml-auto text-gray-600 hover:text-retro-cyan transition-colors"
          aria-label="Copy finding"
          title="Copy finding"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9a.75.75 0 01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184" />
          </svg>
        </button>
      </div>

      {/* Finding conclusion */}
      <div className="mb-2">
        <p className="text-sm font-bold text-gray-100 leading-relaxed">
          {finding.hallazgo}
        </p>
      </div>

      {/* Detail */}
      {finding.detalle && (
        <div className="mb-1.5">
          <CollapsibleSection title="DETALLE">
            <p>{finding.detalle}</p>
          </CollapsibleSection>
        </div>
      )}

      {/* Proposal */}
      {finding.propuesta && (
        <CollapsibleSection title="PROPUESTA">
          <p>{finding.propuesta}</p>
        </CollapsibleSection>
      )}
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
  const totalFindings = report.findings.length;

  // Extract possible file names from findings
  function extractFile(text: string): string | null {
    const match = text.match(/`([\w\/.-]+\.[a-z]+)`/);
    return match ? match[1] : null;
  }

  // Group findings by detected file
  const fileGroups: Record<string, { findings: typeof report.findings; counts: Record<string, number> }> = {};
  let otherFindings: typeof report.findings = [];

  for (const f of report.findings) {
    const file =
      extractFile(f.detalle) || extractFile(f.hallazgo);
    if (file) {
      if (!fileGroups[file]) {
        fileGroups[file] = { findings: [], counts: { Crítico: 0, Alto: 0, Medio: 0, Bajo: 0 } };
      }
      fileGroups[file].findings.push(f);
      if (fileGroups[file].counts[f.impacto] !== undefined) fileGroups[file].counts[f.impacto]++;
    } else {
      otherFindings.push(f);
    }
  }

  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);
  const [filterFile, setFilterFile] = useState<string | null>(null);

  const filteredFindings = filterFile
    ? fileGroups[filterFile]?.findings ?? []
    : report.findings;

  // Calculate average consensus
  const avgConsensus =
    totalFindings > 0
      ? Math.round(
          (report.findings.reduce((sum, f) => sum + f.consensus_score, 0) /
            totalFindings) *
            100
        )
      : 0;

  return (
    <div className="message-enter">
      {/* Report header */}
      <div className="flex items-center gap-3 mb-3 px-1">
        <span className="text-sm font-bold text-retro-cyan uppercase tracking-wider">
          &gt; REPORTE CONSOLIDADO
        </span>
        <span className="text-[10px] text-gray-600 font-mono">
          {report.participants.length} agents &middot; {report.rounds} rounds &middot; {sessionId.slice(0, 8)}
        </span>
      </div>

      {/* Executive summary */}
      <div className="finding-item mb-3">
        <p className="text-[10px] text-retro-cyan font-bold uppercase tracking-wider mb-1">
          &gt; RESUMEN EJECUTIVO
        </p>
        <p className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">
          {report.summary}
        </p>
      </div>

      {/* Severity dashboard */}
      <div className="finding-item mb-3">
        <p className="text-[10px] text-retro-cyan font-bold uppercase tracking-wider mb-2">
          &gt; SEVERITY DASHBOARD
        </p>
        <div className="flex flex-wrap gap-2 mb-2">
          {Object.entries(counts).map(([sev, count]) => (
            <span
              key={sev}
              className="inline-flex items-center gap-1 px-2 py-1 border border-retro-border bg-retro-bg text-[10px] font-mono"
            >
              <SeverityBadge severity={sev} />
              <span className="text-gray-400 font-bold">: {count}</span>
            </span>
          ))}
        </div>
        <div className="text-[10px] text-gray-600 font-mono">
          Total: {totalFindings} finding{totalFindings !== 1 ? 's' : ''} &middot; Consensus: {avgConsensus}%
        </div>
      </div>

      {/* Findings by file */}
      {Object.keys(fileGroups).length > 0 && (
        <div className="finding-item mb-3">
          <p className="text-[10px] text-retro-cyan font-bold uppercase tracking-wider mb-2">
            &gt; FINDINGS BY FILE
          </p>
          <div className="space-y-1">
            {Object.entries(fileGroups).map(([fileName, group]) => (
              <button
                key={fileName}
                onClick={() => setFilterFile(filterFile === fileName ? null : fileName)}
                className={`w-full flex items-center justify-between gap-2 px-2 py-1 text-xs font-mono border border-retro-border transition-colors ${
                  filterFile === fileName
                    ? 'bg-retro-cyan/10 border-retro-cyan'
                    : 'bg-retro-bg hover:border-retro-cyan'
                }`}
                aria-label={`Filter by ${fileName}`}
              >
                <span className="text-gray-200 font-bold truncate">{fileName}</span>
                <span className="text-gray-600 flex-shrink-0">
                  {group.findings.length} finding{group.findings.length !== 1 ? 's' : ''}
                  {Object.entries(group.counts)
                    .filter(([, c]) => c > 0)
                    .map(([sev, c]) => (
                      <span key={sev} className="ml-2 text-[10px]">
                        <span
                          className={
                            sev === 'Crítico'
                              ? 'text-retro-red'
                              : sev === 'Alto'
                                ? 'text-retro-orange'
                                : sev === 'Medio'
                                  ? 'text-retro-yellow'
                                  : 'text-retro-green'
                          }
                        >
                          {c} {sev}
                        </span>
                      </span>
                    ))}
                </span>
              </button>
            ))}
            {otherFindings.length > 0 && (
              <button
                onClick={() => setFilterFile('__other__')}
                className={`w-full flex items-center justify-between gap-2 px-2 py-1 text-xs font-mono border border-retro-border transition-colors ${
                  filterFile === '__other__'
                    ? 'bg-retro-cyan/10 border-retro-cyan'
                    : 'bg-retro-bg hover:border-retro-cyan'
                }`}
                aria-label="Show findings without file reference"
              >
                <span className="text-gray-400 italic">(other)</span>
                <span className="text-gray-600">
                  {otherFindings.length} finding{otherFindings.length !== 1 ? 's' : ''}
                </span>
              </button>
            )}
          </div>
        </div>
      )}

      {/* Consolidated findings */}
      <div className="space-y-2">
        {filteredFindings.map((finding, idx) => {
          const voteEntries = Object.entries(finding.votes);
          return (
            <div key={idx} className="finding-item">
              <button
                onClick={() => setExpandedIdx(expandedIdx === idx ? null : idx)}
                className="w-full flex items-center justify-between gap-3 text-left"
                aria-expanded={expandedIdx === idx}
                aria-label={`Finding ${idx + 1}`}
              >
                <div className="flex items-center gap-2 min-w-0">
                  <span className="text-xs text-gray-600 font-mono flex-shrink-0">
                    [{idx + 1}]
                  </span>
                  <SeverityBadge severity={finding.impacto} />
                  <span className="text-sm font-bold text-gray-200 truncate">
                    {finding.hallazgo}
                  </span>
                </div>
                <svg
                  className={`w-3.5 h-3.5 text-gray-600 flex-shrink-0 transition-transform duration-200 ${
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
                <div className="mt-2 pt-2 space-y-2 border-t border-retro-border">
                  <p className="text-sm text-gray-400">
                    <span className="text-retro-cyan font-bold text-[10px] uppercase tracking-wider">Detalle: </span>
                    {finding.detalle}
                  </p>
                  <p className="text-sm text-gray-400">
                    <span className="text-retro-cyan font-bold text-[10px] uppercase tracking-wider">Propuesta: </span>
                    {finding.propuesta}
                  </p>
                  {voteEntries.length > 0 && (
                    <div>
                      <span className="text-[10px] text-gray-600 font-bold uppercase tracking-wider">Votos: </span>
                      <div className="flex flex-wrap gap-1.5 mt-1">
                        {voteEntries.map(([agentId, vote]) => {
                          const agent = AGENTS.find((a) => a.id === agentId);
                          const sevClass = (sev: string) => {
                            if (sev.toLowerCase().includes('crit') || sev.toLowerCase().includes('alto')) return 'text-retro-red';
                            if (sev.toLowerCase().includes('med')) return 'text-retro-yellow';
                            return 'text-retro-green';
                          };
                          return (
                            <span
                              key={agentId}
                              className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 border border-retro-border bg-retro-bg text-gray-400 font-mono"
                            >
                              <span style={{ color: agent?.color ?? '#666' }}>{agentId}</span>
                              : <span className={sevClass(vote)}>{vote}</span>
                            </span>
                          );
                        })}
                      </div>
                    </div>
                  )}
                  <div className="flex items-center gap-2 text-[10px] text-gray-600 font-mono">
                    <span>Consensus: {Math.round(finding.consensus_score * 100)}%</span>
                    <span className="text-retro-border">|</span>
                    <span>{finding.consensus_level}</span>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Session ID footer */}
      <p className="text-[10px] text-gray-700 font-mono text-center mt-3">
        SESSION: {sessionId}
      </p>
    </div>
  );
}

function ErrorView({ message }: { message: ErrorMessage }) {
  return (
    <div className="chat-message message-enter border-retro-red" role="alert">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-xs font-bold text-retro-red">[ERROR]</span>
      </div>
      <p className="text-sm text-gray-300">{message.text}</p>
    </div>
  );
}

/* ─── Round Transition View ────────────────────────────────────────── */

function RoundTransitionView({ message }: { message: RoundTransitionMessage }) {
  const stageLabel =
    message.round === 1 ? 'INDIVIDUAL ANALYSIS' : message.round === 2 ? 'CROSS-DEBATE' : 'REFINEMENT';
  return (
    <div className="message-enter py-3">
      <div className="flex items-center gap-3 border-t border-b border-retro-border py-2">
        <span className="text-xs font-bold text-retro-cyan uppercase tracking-widest">
          &gt; {message.label}
        </span>
        <span className="text-[10px] text-gray-600 font-mono border border-retro-border px-1.5 py-0.5">
          {stageLabel}
        </span>
        {/* Progress bar */}
        <div className="flex-1 h-1 bg-retro-border max-w-[120px] ml-auto">
          <div
            className="h-full bg-retro-cyan transition-all duration-500"
            style={{ width: `${(message.round / 3) * 100}%` }}
          />
        </div>
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
    case 'round-transition':
      return <RoundTransitionView message={message} />;
    default:
      return null;
  }
}
