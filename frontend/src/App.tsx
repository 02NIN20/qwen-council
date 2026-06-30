import { useState, useCallback, useRef, useEffect } from 'react';
import type {
  ChatMessageData,
  AgentProgress,
  Finding,
  ReviewResponse,
  RoundTransitionMessage,
} from './types';
import { AGENTS } from './types';
import { submitReview } from './api/council';
import ChatView from './components/ChatView';

/* ─── Helpers ───────────────────────────────────────────────────────── */

let idCounter = 0;
function uid(): string {
  idCounter += 1;
  return `msg-${Date.now().toString(36)}-${idCounter}`;
}

function allAgentProgress(status: AgentProgress['status']): AgentProgress[] {
  return AGENTS.map((a) => ({
    id: a.id,
    name: a.name,
    icon: a.icon,
    color: a.color,
    status,
  }));
}

/**
 * Build a finding message from a Finding and agent info.
 */
function findingToMessage(finding: Finding, round: number): ChatMessageData {
  const agent = AGENTS.find((a) => a.id === finding.agent);
  return {
    id: uid(),
    role: 'finding',
    finding,
    agentName: agent?.name ?? finding.agent,
    agentIcon: agent?.icon ?? '?',
    agentColor: agent?.color ?? '#64748B',
    round,
  };
}

/* ─── Progressive reveal logic ─────────────────────────────────────── */

/**
 * Given the full API response, dispatch messages with delays to simulate
 * a live council debate. Returns a cancel function.
 */
function buildProgressiveReveal(
  response: ReviewResponse,
  progressMsgId: string,
  onUpdateMessage: (id: string, msg: ChatMessageData) => void,
  onAddMessage: (msg: ChatMessageData) => void,
  onDone: () => void
): () => void {
  let cancelled = false;

  const roundKeys: (keyof typeof response.rounds)[] = [
    'round_1',
    'round_2',
    'round_3',
  ];

  function markProgress(statuses: AgentProgress[], label: string) {
    if (cancelled) return;
    onUpdateMessage(progressMsgId, {
      id: progressMsgId,
      role: 'agent-progress',
      agents: statuses,
      label,
    });
  }

  function releaseRound(roundIndex: number) {
    if (cancelled) return;

    const roundKey = roundKeys[roundIndex];
    const findings = response.rounds[roundKey];

    if (!findings || findings.length === 0) {
      if (roundIndex < 2) {
        setTimeout(() => releaseRound(roundIndex + 1), 400);
      } else {
        onDone();
      }
      return;
    }

    // Mark all agents as analyzing for this round
    const analyzingStatuses: AgentProgress[] = AGENTS.map((a) => ({
      id: a.id,
      name: a.name,
      icon: a.icon,
      color: a.color,
      status: 'analyzing' as const,
    }));
    markProgress(analyzingStatuses, `Ronda ${roundIndex + 1} — Analizando...`);

    // Release findings one by one
    const delays = findings.map((_, idx) => (idx + 1) * 700);

    findings.forEach((finding, idx) => {
      setTimeout(() => {
        if (cancelled) return;
        onAddMessage(findingToMessage(finding, roundIndex + 1));

        // Update progress for completed agents
        const completedIds = findings
          .slice(0, idx + 1)
          .map((f) => f.agent);
        const updatedStatuses: AgentProgress[] = AGENTS.map((a) => ({
          id: a.id,
          name: a.name,
          icon: a.icon,
          color: a.color,
          status: completedIds.includes(a.id)
            ? ('complete' as const)
            : ('analyzing' as const),
        }));
        markProgress(
          updatedStatuses,
          `Ronda ${roundIndex + 1} — ${
            completedIds.length === AGENTS.length
              ? 'Completada'
              : 'Analizando...'
          }`
        );
      }, delays[idx]);
    });

    // After all findings are released, move to next round or finish
    const totalDelay = Math.max(...delays, findings.length * 700) + 500;
    setTimeout(() => {
      if (cancelled) return;
      if (roundIndex < 2) {
        // Insert round transition before next round
        const nextRound = roundIndex + 2; // 2-indexed
        const labels = ['INDIVIDUAL ANALYSIS', 'CROSS-DEBATE', 'REFINEMENT'];
        onAddMessage({
          id: uid(),
          role: 'round-transition',
          round: nextRound,
          label: `ROUND ${nextRound}: ${labels[nextRound - 1]}`,
        });
        setTimeout(() => {
          if (cancelled) return;
          releaseRound(roundIndex + 1);
        }, 400);
      } else {
        onDone();
      }
    }, totalDelay);
  }

  // Start after a brief pause so the user sees "waiting" state first
  const labels = ['INDIVIDUAL ANALYSIS', 'CROSS-DEBATE', 'REFINEMENT'];
  const startTimeout = setTimeout(() => {
    if (cancelled) return;
    // Insert round transition for Round 1
    onAddMessage({
      id: uid(),
      role: 'round-transition',
      round: 1,
      label: `ROUND 1: ${labels[0]}`,
    });
    setTimeout(() => {
      if (cancelled) return;
      releaseRound(0);
    }, 400);
  }, 600);

  return () => {
    cancelled = true;
    clearTimeout(startTimeout);
  };
}

/* ─── App Component ─────────────────────────────────────────────────── */

export default function App() {
  const [messages, setMessages] = useState<ChatMessageData[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const cancelRef = useRef<(() => void) | null>(null);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      cancelRef.current?.();
    };
  }, []);

  /**
   * Replace a message in the list by id.
   */
  const updateMessage = useCallback((id: string, msg: ChatMessageData) => {
    setMessages((prev) => prev.map((m) => (m.id === id ? msg : m)));
  }, []);

  /**
   * Handle code submission.
   */
  const handleSubmit = useCallback(
    async (code: string, files?: { filename: string; content: string }[], _imageUrl?: string, instruction?: string) => {
      // Cancel any previous animation
      cancelRef.current?.();

      // Reset
      setIsLoading(true);

      const fileSummary = files && files.length > 0
        ? files.map(f => f.filename).join(', ')
        : (code.slice(0, 100) || 'code review');

      // 1. Create initial user message (without contextPreview — added after response)
      const userMsgId = uid();
      const initialUserMsg: ChatMessageData = {
        id: userMsgId,
        role: 'user',
        content: fileSummary,
        code: code || (files?.[0]?.content ?? ''),
        fileInfo: files?.map(f => ({
          name: f.filename,
          size: f.content.length,
          language: f.filename.split('.').pop(),
        })),
        instruction: instruction,
        timestamp: Date.now(),
      };

      // 2. Add progress message with "waiting" agents
      const progressMsg: ChatMessageData = {
        id: uid(),
        role: 'agent-progress',
        agents: allAgentProgress('waiting'),
        label: 'Iniciando revisión...',
      };

      setMessages([initialUserMsg, progressMsg]);

      try {
        const response = await submitReview(code, files, instruction);

        // Update user message with context preview from response
        updateMessage(userMsgId, {
          ...initialUserMsg,
          contextPreview: response.rounds_raw?.context_preview,
        });

        // Start progressive reveal
        cancelRef.current = buildProgressiveReveal(
          response,
          progressMsg.id,
          updateMessage,
          (msg) => {
            setMessages((prev) => [...prev, msg]);
          },
          () => {
            // All rounds done → add report
            const reportMsg: ChatMessageData = {
              id: uid(),
              role: 'report',
              report: response.report,
              sessionId: response.session_id,
            };
            setMessages((prev) => [...prev, reportMsg]);
            setIsLoading(false);
            cancelRef.current = null;
          }
        );
      } catch (err) {
        const errorMsg: ChatMessageData = {
          id: uid(),
          role: 'error',
          text:
            err instanceof Error
              ? err.message
              : 'Error desconocido al conectar con el backend',
        };
        setMessages((prev) => [...prev, errorMsg]);
        setIsLoading(false);
      }
    },
    [updateMessage]
  );

  return (
    <ChatView messages={messages} onSubmit={handleSubmit} disabled={isLoading} />
  );
}
