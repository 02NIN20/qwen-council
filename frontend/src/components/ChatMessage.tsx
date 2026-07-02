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
  AnswerMessage,
  AgentContribution,
  TokenUsage,
} from '../types';
import { AGENTS } from '../types';

/* ─── Severity badge ─────────────────────────────────────────────────── */

function SeverityBadge({ severity }: { severity: string }) {
  const classMap: Record<string, string> = {
    Critical: 'sev-critical',
    High: 'sev-high',
    Medium: 'sev-medium',
    Low: 'sev-low',
  };
  const cls = classMap[severity] ?? 'sev-low';
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
            {new Date(message.timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}
        </span>
      </div>

      {/* User's text message */}
      {message.content && (
        <p className="text-sm text-gray-200 leading-relaxed whitespace-pre-wrap mb-3">
          {message.content}
        </p>
      )}

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
  const fileMatch = finding.detail.match(/`([\w\/.-]+\.[a-z]+)`/);
  const mentionedFile = fileMatch ? fileMatch[1] : null;

  const handleCopy = useCallback(() => {
    const text = `[${finding.impact}] ${finding.title}\n\nDetail: ${finding.detail}\n\nProposal: ${finding.proposal}`;
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
        <SeverityBadge severity={finding.impact} />
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
          {finding.title}
        </p>
      </div>

      {/* Detail */}
      {finding.detail && (
        <div className="mb-1.5">
          <CollapsibleSection title="DETAIL">
            <p>{finding.detail}</p>
          </CollapsibleSection>
        </div>
      )}

      {/* Proposal */}
      {finding.proposal && (
        <CollapsibleSection title="PROPOSAL">
          <p>{finding.proposal}</p>
        </CollapsibleSection>
      )}
    </div>
  );
}

function TokenUsageBadge({ usage }: { usage: TokenUsage }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border border-retro-border mb-3">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between gap-2 px-3 py-2 text-[10px] font-bold text-gray-500 hover:text-retro-cyan hover:bg-retro-bg transition-colors uppercase tracking-wider"
        aria-expanded={open}
      >
        <span>&gt; TOKEN USAGE &mdash; {usage.total_tokens.toLocaleString()} tokens &middot; ${usage.estimated_cost_usd.toFixed(2)}</span>
        <svg className={`w-3 h-3 transition-transform duration-200 ${open ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {open && (
        <div className="px-3 pb-3 border-t border-retro-border pt-2 space-y-2 text-[11px] font-mono">
          <div className="flex justify-between text-gray-500">
            <span>Model</span>
            <span className="text-gray-300">{usage.model}</span>
          </div>
          <div className="flex justify-between text-gray-500">
            <span>Total input</span>
            <span className="text-gray-300">{usage.total_input_tokens.toLocaleString()}</span>
          </div>
          <div className="flex justify-between text-gray-500">
            <span>Total output</span>
            <span className="text-gray-300">{usage.total_output_tokens.toLocaleString()}</span>
          </div>
          <div className="flex justify-between text-gray-500">
            <span>Estimated cost</span>
            <span className="text-retro-cyan">${usage.estimated_cost_usd.toFixed(2)}</span>
          </div>
          {usage.budget && (
            <>
              <div className="border-t border-retro-border pt-1 mt-1">
                <p className="text-[10px] text-retro-cyan font-bold uppercase tracking-wider mb-1">Budget</p>
                <div className="flex justify-between text-gray-500">
                  <span>Max input</span>
                  <span className="text-gray-300">{usage.budget.config.max_input_tokens.toLocaleString()}</span>
                </div>
                <div className="flex justify-between text-gray-500">
                  <span>Max output</span>
                  <span className="text-gray-300">{usage.budget.config.max_output_tokens.toLocaleString()}</span>
                </div>
                <div className="flex justify-between text-gray-500">
                  <span>Max cost</span>
                  <span className="text-gray-300">${usage.budget.config.max_cost_usd.toFixed(2)}</span>
                </div>
                {usage.budget.exhausted && (
                  <p className="text-retro-red text-[10px] mt-1">Budget exhausted</p>
                )}
              </div>
              {usage.budget.per_call.length > 0 && (
                <div className="border-t border-retro-border pt-1 mt-1">
                  <p className="text-[10px] text-retro-cyan font-bold uppercase tracking-wider mb-1">Per-call breakdown</p>
                  {usage.budget.per_call.map((call, i) => (
                    <div key={i} className="flex justify-between text-gray-500 text-[10px]">
                      <span>{call.label}</span>
                      <span className="text-gray-400">{call.input_tokens + call.output_tokens} tok / ${call.cost_usd.toFixed(4)}</span>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

function ReportView({ message }: { message: ReportMessage }) {
  const { report, sessionId } = message;

  const counts: Record<string, number> = { Critical: 0, High: 0, Medium: 0, Low: 0 };
  for (const f of report.findings) {
    if (counts[f.impact] !== undefined) counts[f.impact]++;
    else counts.Low++;
  }
  const totalFindings = report.findings.length;

  function extractFile(text: string): string | null {
    const match = text.match(/`([\w\/.-]+\.[a-z]+)`/);
    return match ? match[1] : null;
  }

  const fileGroups: Record<string, { findings: typeof report.findings; counts: Record<string, number> }> = {};
  let otherFindings: typeof report.findings = [];

  for (const f of report.findings) {
    const file = extractFile(f.detail) || extractFile(f.title);
    if (file) {
      if (!fileGroups[file]) {
        fileGroups[file] = { findings: [], counts: { Critical: 0, High: 0, Medium: 0, Low: 0 } };
      }
      fileGroups[file].findings.push(f);
      if (fileGroups[file].counts[f.impact] !== undefined) fileGroups[file].counts[f.impact]++;
    } else {
      otherFindings.push(f);
    }
  }

  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);
  const [filterFile, setFilterFile] = useState<string | null>(null);

  const filteredFindings = filterFile
    ? fileGroups[filterFile]?.findings ?? []
    : report.findings;

  return (
    <div className="message-enter">
      <div className="flex items-center gap-3 mb-3 px-1">
        <span className="text-sm font-bold text-retro-cyan uppercase tracking-wider">
          &gt; CONSOLIDATED REPORT
        </span>
        <span className="text-[10px] text-gray-600 font-mono">
          {report.participants.length} agents &middot; {report.rounds} rounds &middot; {sessionId.slice(0, 8)}
        </span>
      </div>

      {/* Executive summary */}
      <div className="finding-item mb-3">
        <p className="text-[10px] text-retro-cyan font-bold uppercase tracking-wider mb-1">
          &gt; EXECUTIVE SUMMARY
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
          Total: {totalFindings} finding{totalFindings !== 1 ? 's' : ''}
        </div>
      </div>

      {/* Risk overview */}
      {report.risk_overview && (
        <div className="finding-item mb-3">
          <p className="text-[10px] text-retro-cyan font-bold uppercase tracking-wider mb-1">
            &gt; RISK OVERVIEW
          </p>
          <p className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">
            {report.risk_overview}
          </p>
        </div>
      )}

      {/* Detailed review */}
      {report.detailed_review && (
        <CollapsibleSection title="DETAILED REVIEW">
          <p className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">
            {report.detailed_review}
          </p>
        </CollapsibleSection>
      )}

      {/* Remediation roadmap */}
      {report.remediation_roadmap && (
        <div className="finding-item mb-3">
          <p className="text-[10px] text-retro-cyan font-bold uppercase tracking-wider mb-1">
            &gt; REMEDIATION ROADMAP
          </p>
          <p className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">
            {report.remediation_roadmap}
          </p>
        </div>
      )}

      {/* Token usage */}
      {report.token_usage && (
        <TokenUsageBadge usage={report.token_usage} />
      )}

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
                            sev === 'Critical' ? 'text-retro-red'
                            : sev === 'High' ? 'text-retro-orange'
                            : sev === 'Medium' ? 'text-retro-yellow'
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

      {/* Findings list */}
      <div className="space-y-2">
        {filteredFindings.map((finding, idx) => {
          const agentMeta = AGENTS.find((a) => a.id === finding.agent);
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
                  <SeverityBadge severity={finding.impact} />
                  <span className="text-sm font-bold text-gray-200 truncate">
                    {finding.title}
                  </span>
                </div>
                <svg
                  className={`w-3.5 h-3.5 text-gray-600 flex-shrink-0 transition-transform duration-200 ${
                    expandedIdx === idx ? 'rotate-180' : ''
                  }`}
                  fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {expandedIdx === idx && (
                <div className="mt-2 pt-2 space-y-2 border-t border-retro-border">
                  <div className="flex items-center gap-2 text-[10px] text-gray-600 font-mono mb-1">
                    {agentMeta && (
                      <span style={{ color: agentMeta.color }}>
                        [{agentMeta.icon}] {agentMeta.name}
                      </span>
                    )}
                    <span className="text-gray-700">Round {finding.round_num}</span>
                  </div>
                  <p className="text-sm text-gray-400">
                    <span className="text-retro-cyan font-bold text-[10px] uppercase tracking-wider">Detail: </span>
                    {finding.detail}
                  </p>
                  <p className="text-sm text-gray-400">
                    <span className="text-retro-cyan font-bold text-[10px] uppercase tracking-wider">Proposal: </span>
                    {finding.proposal}
                  </p>
                </div>
              )}
            </div>
          );
        })}
      </div>

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

/* ─── Answer View (General Chat) ──────────────────────────────────── */

function AgentContributionCard({ contribution }: { contribution: AgentContribution }) {
  const agentInfo = AGENTS.find((a) => a.name.toLowerCase() === contribution.agent.toLowerCase());
  const icon = agentInfo?.icon ?? '?';
  const color = agentInfo?.color ?? '#666';

  return (
    <div
      className="border border-retro-border bg-retro-bg p-3"
      style={{ borderLeft: `3px solid ${color}` }}
    >
      <div className="flex items-center gap-2 mb-1.5">
        <span className="text-xs font-bold" style={{ color }}>
          [{icon}] {contribution.agent}
        </span>
        <span className="text-[10px] text-gray-600 font-mono italic">
          {contribution.role_description}
        </span>
      </div>
      <p className="text-xs text-gray-400 leading-relaxed whitespace-pre-wrap">
        {contribution.answer}
      </p>
    </div>
  );
}

function AnswerMessageView({ message }: { message: AnswerMessage }) {
  const hasContributions = message.agentContributions && message.agentContributions.length > 0;

  return (
    <div className="chat-message chat-message-answer message-enter">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs font-bold text-retro-cyan">&gt; EXPERT PANEL</span>
        {message.timestamp && (
          <span className="text-[10px] text-gray-600">
          {new Date(message.timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}
          </span>
        )}
      </div>

      {/* The synthesized answer */}
      <div className="mb-3">
        <p className="text-sm text-gray-200 leading-relaxed whitespace-pre-wrap">
          {message.text}
        </p>
      </div>

      {/* Agent Contributions (collapsible) */}
      {hasContributions && (
        <CollapsibleSection title="AGENT CONTRIBUTIONS" defaultOpen={false}>
          <div className="space-y-2">
            {message.agentContributions!.map((contrib, idx) => (
              <AgentContributionCard key={idx} contribution={contrib} />
            ))}
          </div>
        </CollapsibleSection>
      )}

      {/* Session ID */}
      {message.sessionId && (
        <p className="text-[10px] text-gray-700 font-mono text-center mt-2">
          SESSION: {message.sessionId}
        </p>
      )}
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
    case 'answer':
      return <AnswerMessageView message={message} />;
    case 'error':
      return <ErrorView message={message} />;
    case 'round-transition':
      return <RoundTransitionView message={message} />;
    default:
      return null;
  }
}
