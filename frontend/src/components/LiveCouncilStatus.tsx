import { useState, useEffect, useRef, useCallback } from 'react';
import type { Report } from '../types';
import { AGENTS } from '../types';
import { streamReview, type StreamReviewRequest, type StreamCallbacks } from '../api/streamReview';

/* ─── Types ─────────────────────────────────────────────────────────── */

type AgentStatus = 'pending' | 'analyzing' | 'complete' | 'error';

interface AgentState {
  id: string;
  name: string;
  icon: string;
  color: string;
  status: AgentStatus;
  findingsCount: number;
}

interface RoundState {
  round: number;
  totalRounds: number;
  started: boolean;
  complete: boolean;
  agentsComplete: number;
  totalFindings: number;
}

interface LiveCouncilStatusProps {
  isRunning: boolean;
  payload: StreamReviewRequest;
  onComplete?: (sessionId: string, report: Report) => void;
  onError?: (error: string) => void;
}

/* ─── Helpers ───────────────────────────────────────────────────────── */

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function roundLabel(round: number): string {
  switch (round) {
    case 1:
      return 'Individual Analysis';
    case 2:
      return 'Cross-Debate';
    case 3:
      return 'Refinement';
    default:
      return `Round ${round}`;
  }
}

/* ─── LiveCouncilStatus Component ──────────────────────────────────── */

export default function LiveCouncilStatus({
  isRunning,
  payload,
  onComplete,
  onError,
}: LiveCouncilStatusProps) {
  /* ── State ──────────────────────────────────────────────────────── */

  const [agents, setAgents] = useState<AgentState[]>(() =>
    AGENTS.map((a) => ({
      id: a.id,
      name: a.name,
      icon: a.icon,
      color: a.color,
      status: 'pending' as AgentStatus,
      findingsCount: 0,
    })),
  );

  const [currentRound, setCurrentRound] = useState<RoundState>({
    round: 0,
    totalRounds: 3,
    started: false,
    complete: false,
    agentsComplete: 0,
    totalFindings: 0,
  });

  const [elapsed, setElapsed] = useState(0);
  const [statusText, setStatusText] = useState('Initializing council...');
  const [negotiationActive, setNegotiationActive] = useState(false);
  const [negotiationResolved, setNegotiationResolved] = useState(0);
  const [hasCompleted, setHasCompleted] = useState(false);

  /* ── Refs ───────────────────────────────────────────────────────── */

  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startTimeRef = useRef<number>(0);

  /* ── Timer management ───────────────────────────────────────────── */

  const startTimer = useCallback(() => {
    startTimeRef.current = Date.now();
    setElapsed(0);
    timerRef.current = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTimeRef.current) / 1000));
    }, 1000);
  }, []);

  const stopTimer = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  // Cleanup timer on unmount
  useEffect(() => {
    return () => stopTimer();
  }, [stopTimer]);

  /* ── Reset state when isRunning changes ─────────────────────────── */

  useEffect(() => {
    if (!isRunning) {
      stopTimer();
      return;
    }

    // Reset everything
    setAgents(
      AGENTS.map((a) => ({
        id: a.id,
        name: a.name,
        icon: a.icon,
        color: a.color,
        status: 'pending' as AgentStatus,
        findingsCount: 0,
      })),
    );
    setCurrentRound({
      round: 0,
      totalRounds: 3,
      started: false,
      complete: false,
      agentsComplete: 0,
      totalFindings: 0,
    });
    setElapsed(0);
    setStatusText('Initializing council...');
    setNegotiationActive(false);
    setNegotiationResolved(0);
    setHasCompleted(false);

    startTimer();

    /* ── Build SSE callbacks ────────────────────────────────────── */

    const callbacks: StreamCallbacks = {
      onRoundStart: (round, totalRounds) => {
        setCurrentRound((prev) => ({
          ...prev,
          round,
          totalRounds,
          started: true,
          complete: false,
          agentsComplete: 0,
          totalFindings: 0,
        }));
        setStatusText(`Round ${round}/${totalRounds}: ${roundLabel(round)}`);
        // Reset agents to pending for new round
        setAgents(
          AGENTS.map((a) => ({
            id: a.id,
            name: a.name,
            icon: a.icon,
            color: a.color,
            status: 'pending' as AgentStatus,
            findingsCount: 0,
          })),
        );
      },

      onAgentStart: (agentId, _round) => {
        setAgents((prev) =>
          prev.map((a) =>
            a.id === agentId ? { ...a, status: 'analyzing' as AgentStatus } : a,
          ),
        );
        const agent = AGENTS.find((a) => a.id === agentId);
        setStatusText(`Analyzing: ${agent?.name ?? agentId}...`);
      },

      onAgentComplete: (agentId, _round, findingsCount) => {
        setAgents((prev) => {
          const updated = prev.map((a) =>
            a.id === agentId
              ? { ...a, status: 'complete' as AgentStatus, findingsCount }
              : a,
          );
          // Count how many are complete
          const completeCount = updated.filter(
            (a) => a.status === 'complete' || a.status === 'error',
          ).length;
          setCurrentRound((r) => ({ ...r, agentsComplete: completeCount }));
          return updated;
        });
      },

      onRoundComplete: (_round, totalFindings) => {
        setCurrentRound((prev) => ({
          ...prev,
          complete: true,
          totalFindings,
        }));
        setStatusText(`Round ${_round} complete — ${totalFindings} findings`);
      },

      onSynthesisComplete: (consolidatedCount) => {
        setStatusText(`Synthesizing — ${consolidatedCount} consolidated findings`);
      },

      onNegotiationStart: (disputedCount) => {
        setNegotiationActive(true);
        setStatusText(`Negotiating ${disputedCount} disputed findings...`);
      },

      onNegotiationComplete: (resolved) => {
        setNegotiationResolved(resolved);
        setNegotiationActive(false);
        setStatusText(`Negotiation complete — ${resolved} resolved`);
      },

      onComplete: (sessionId, report) => {
        setHasCompleted(true);
        setStatusText('Council complete!');
        stopTimer();
        onComplete?.(sessionId, report);
      },

      onError: (error) => {
        setStatusText(`Error: ${error}`);
        onError?.(error);
        stopTimer();
      },
    };

    // Start the stream
    streamReview(payload, callbacks).catch((err: unknown) => {
      const msg = err instanceof Error ? err.message : 'Stream failed';
      setStatusText(`Error: ${msg}`);
      stopTimer();
    });
  }, [isRunning]); // eslint-disable-line react-hooks/exhaustive-deps

  /* ── Render ────────────────────────────────────────────────────── */

  if (!isRunning) return null;

  const totalRounds = currentRound.totalRounds;
  const roundProgress =
    currentRound.round > 0
      ? ((currentRound.round - 1) / totalRounds) * 100 +
        (currentRound.round <= totalRounds
          ? (currentRound.agentsComplete / AGENTS.length) * (100 / totalRounds)
          : 0)
      : 0;

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] px-4">
      <div className="w-full max-w-lg border border-retro-border bg-retro-surface p-5">
        {/* Header */}
        <div className="flex items-center gap-2 mb-4 pb-3 border-b border-retro-border">
          <span className="w-2 h-2 bg-retro-green status-dot" />
          <span className="text-sm font-bold text-retro-cyan uppercase tracking-widest">
            &gt; Council in Progress...
          </span>
          <span className="ml-auto text-[10px] font-mono text-gray-600">
            {formatElapsed(elapsed)}
          </span>
        </div>

        {/* Status text */}
        <p className="text-xs text-gray-500 font-mono mb-4 uppercase tracking-wider">
          {statusText}
        </p>

        {/* Progress bar */}
        <div className="h-1.5 bg-retro-border mb-4">
          <div
            className="h-full bg-retro-green transition-all duration-500 ease-out"
            style={{ width: `${Math.min(roundProgress, 100)}%` }}
            role="progressbar"
            aria-valuenow={Math.round(roundProgress)}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={`Council progress: ${Math.round(roundProgress)}%`}
          />
        </div>

        {/* Round indicators */}
        <div className="flex gap-2 mb-4">
          {Array.from({ length: totalRounds }, (_, idx) => {
            const roundNum = idx + 1;
            const isActive = currentRound.round === roundNum && currentRound.started;
            const isDone = currentRound.round > roundNum || (currentRound.round === roundNum && currentRound.complete);
            const isPending = currentRound.round < roundNum;

            return (
              <div
                key={roundNum}
                className={`flex-1 text-center py-1 border text-[10px] font-bold uppercase tracking-wider transition-colors ${
                  isActive
                    ? 'border-retro-green bg-retro-green/10 text-retro-green'
                    : isDone
                      ? 'border-retro-green/50 text-retro-green/60'
                      : isPending
                        ? 'border-retro-border text-gray-700'
                        : 'border-retro-border text-gray-700'
                }`}
                aria-label={`Round ${roundNum}: ${isDone ? 'complete' : isActive ? 'in progress' : 'pending'}`}
              >
                {isDone ? `[${roundNum}] ✓` : isActive ? `[${roundNum}] ▶` : `[${roundNum}]`}
              </div>
            );
          })}
        </div>

        {/* Agent list */}
        <div className="space-y-1 mb-4" role="list" aria-label="Agent progress">
          {agents.map((agent) => (
            <div
              key={agent.id}
              className="flex items-center gap-2 px-2.5 py-1.5 border border-retro-border text-xs"
              style={{
                borderLeft: `3px solid ${agent.color}`,
                opacity: agent.status === 'pending' ? 0.5 : 1,
              }}
              role="listitem"
              aria-label={`${agent.name}: ${agent.status}`}
            >
              {/* Agent icon */}
              <span className="text-xs font-bold" style={{ color: agent.color }} aria-hidden="true">
                [{agent.icon}]
              </span>

              {/* Agent name */}
              <span className="text-gray-300 font-bold flex-1">{agent.name}</span>

              {/* Status indicator */}
              {agent.status === 'pending' && (
                <span className="text-[10px] text-gray-700 font-mono">⏳ Pending</span>
              )}
              {agent.status === 'analyzing' && (
                <span className="flex items-center gap-1">
                  <span className="flex gap-0.5">
                    <span className="w-1 h-1 bg-current animate-pulse" style={{ color: agent.color }} />
                    <span className="w-1 h-1 bg-current animate-pulse" style={{ color: agent.color, animationDelay: '200ms' }} />
                    <span className="w-1 h-1 bg-current animate-pulse" style={{ color: agent.color, animationDelay: '400ms' }} />
                  </span>
                </span>
              )}
              {agent.status === 'complete' && (
                <span className="flex items-center gap-1 text-[10px] text-retro-green font-mono">
                  <span className="text-retro-green">[✓]</span>
                  {agent.findingsCount > 0 && (
                    <span className="text-gray-600">({agent.findingsCount})</span>
                  )}
                </span>
              )}
              {agent.status === 'error' && (
                <span className="text-[10px] text-retro-red font-mono">[ERR]</span>
              )}
            </div>
          ))}
        </div>

        {/* Negotiation status (if active) */}
        {negotiationActive && (
          <div className="flex items-center gap-2 px-2.5 py-1.5 border border-retro-yellow/50 bg-retro-yellow/5 text-xs text-retro-yellow font-mono mb-4">
            <span className="w-1.5 h-1.5 bg-retro-yellow status-dot" />
            <span>Negotiating disputed findings...</span>
          </div>
        )}

        {/* Negotiation complete */}
        {negotiationResolved > 0 && !negotiationActive && (
          <div className="px-2.5 py-1.5 border border-retro-green/30 text-xs text-retro-green/80 font-mono mb-4">
            ✓ {negotiationResolved} disputed finding{negotiationResolved !== 1 ? 's' : ''} resolved
          </div>
        )}

        {/* Completion message */}
        {hasCompleted && (
          <div className="px-2.5 py-2 border border-retro-green bg-retro-green/10 text-xs text-retro-green font-bold uppercase tracking-wider text-center">
            ✓ Council Complete — Generating Report
          </div>
        )}

        {/* Elapsed time footer */}
        <div className="mt-3 pt-2 border-t border-retro-border flex items-center gap-2 text-[10px] text-gray-700 font-mono">
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <circle cx="12" cy="12" r="10" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6l4 2" />
          </svg>
          <span>Elapsed: {formatElapsed(elapsed)}</span>
        </div>
      </div>
    </div>
  );
}
