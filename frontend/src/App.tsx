import { useState, useCallback, useRef } from 'react';
import type {
  ChatMessageData,
  Report,
} from './types';
import { getSession, sendChatMessage } from './api/council';
import type { StreamReviewRequest } from './api/streamReview';
import { ErrorBoundary } from './components/ErrorBoundary';
import ChatView from './components/ChatView';
import Sidebar from './components/Sidebar';
import LiveCouncilStatus from './components/LiveCouncilStatus';

/* ─── Helpers ───────────────────────────────────────────────────────── */

let idCounter = 0;
function uid(): string {
  idCounter += 1;
  return `msg-${Date.now().toString(36)}-${idCounter}`;
}

/* ─── App Component ─────────────────────────────────────────────────── */

export default function App() {
  const [messages, setMessages] = useState<ChatMessageData[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [activeSessionId, setActiveSessionId] = useState<string | undefined>();
  const [refreshKey, setRefreshKey] = useState(0);

  // Stores the latest stream payload so LiveCouncilStatus can read it
  const streamPayloadRef = useRef<StreamReviewRequest | null>(null);

  // New Chat — reset everything
  const handleNewChat = useCallback(() => {
    setMessages([]);
    setIsLoading(false);
    setActiveSessionId(undefined);
    streamPayloadRef.current = null;
  }, []);

  // Load a past session
  const handleSelectSession = useCallback(async (sessionId: string) => {
    setIsLoading(true);
    try {
      const session = await getSession(sessionId);
      setActiveSessionId(sessionId);
      setRefreshKey(k => k + 1);
      // Detect chat session (findings_json contains chat data, not a review report)
      const reportData = session.findings_json;
      const isChat = Array.isArray(reportData) && reportData[0]?.question !== undefined;

      if (isChat) {
        // ── Chat session — load ALL conversation turns ──────────
        const allMessages: ChatMessageData[] = [];
        for (const entry of reportData) {
          const question = entry.question || '';
          const response = entry.response || '';
          if (question) {
            allMessages.push({
              id: uid(),
              role: 'user',
              content: question,
              code: '',
              timestamp: Date.now(),
            });
          }
          if (response) {
            allMessages.push({
              id: uid(),
              role: 'answer',
              text: response,
              agentContributions: entry.agent_contributions || [],
              sessionId: session.id,
              timestamp: Date.now(),
            });
          }
        }
        setMessages(allMessages.length > 0 ? allMessages : [
          {
            id: uid(),
            role: 'error',
            text: 'No messages in this session',
          },
        ]);
      } else {
        // ── Review session ──────────────────────────────────────
        const userMsg: ChatMessageData = {
          id: uid(),
          role: 'user',
          content: session.code.slice(0, 100),
          code: session.code,
          timestamp: Date.now(),
        };
        // Handle both new format (object with `report` key) and old format (flat array)
        const report = reportData?.report
          ? reportData.report
          : {
              findings: Array.isArray(reportData) ? [] : (reportData?.findings || []),
              summary: 'Past session',
              rounds: 3,
              participants: []
            };
        const reportMsg: ChatMessageData = {
          id: uid(),
          role: 'report',
          report,
          sessionId: session.id,
        };
        setMessages([userMsg, reportMsg]);
      }
    } catch {
      setMessages([{
        id: uid(),
        role: 'error',
        text: 'Failed to load session',
      }]);
    }
    setIsLoading(false);
  }, []);

  /**
   * Called by LiveCouncilStatus when the SSE stream completes.
   */
  const handleStreamComplete = useCallback(
    (sessionId: string, report: Report) => {
      setActiveSessionId(sessionId);
      const reportMsg: ChatMessageData = {
        id: uid(),
        role: 'report',
        report,
        sessionId,
      };
      setMessages((prev) => [...prev, reportMsg]);
      setIsLoading(false);
      setRefreshKey(k => k + 1);
    },
    [],
  );

  /**
   * Called by LiveCouncilStatus when the SSE stream errors.
   */
  const handleStreamError = useCallback((error: string) => {
    const errorMsg: ChatMessageData = {
      id: uid(),
      role: 'error',
      text: error,
    };
    setMessages((prev) => [...prev, errorMsg]);
    setIsLoading(false);
  }, []);

  /**
   * Handle code submission — starts the SSE stream.
   */
  const handleSubmit = useCallback(
    (code: string, files?: { filename: string; content: string }[], images?: { filename: string; content: string; mime_type: string }[], instruction?: string) => {
      // Build the payload
      const payload: StreamReviewRequest = {
        code: code || undefined,
        files: files?.map((f) => ({
          filename: f.filename,
          content: f.content,
          language: f.filename.split('.').pop(),
        })),
        images: images,
        instruction: instruction || undefined,
      };
      streamPayloadRef.current = payload;

      const fileSummary = files && files.length > 0
        ? files.map(f => f.filename).join(', ')
        : (code.slice(0, 100) || 'code review');

      // Create initial user message
      const initialUserMsg: ChatMessageData = {
        id: uid(),
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

      setMessages([initialUserMsg]);
      setIsLoading(true);
    },
    [],
  );

  /**
   * Handle chat question submission — sends free-text to the multi-agent chat API.
   * Supports optional file attachments for agent analysis.
   */
  const handleChatSubmit = useCallback(
    async (question: string, files?: { filename: string; content: string; language?: string }[], images?: { filename: string; content: string; mime_type: string }[]) => {
      // Create user message with file context
      const userMsg: ChatMessageData = {
        id: uid(),
        role: 'user',
        content: question,
        code: '',
        fileInfo: files?.map(f => ({
          name: f.filename,
          size: f.content.length,
          language: f.language,
        })),
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, userMsg]);
      setIsLoading(true);

      try {
        const response = await sendChatMessage(question, activeSessionId, undefined, files, images);

        // Create answer message with agent contributions
        const answerMsg: ChatMessageData = {
          id: uid(),
          role: 'answer',
          text: response.response,
          agentContributions: response.agent_contributions,
          sessionId: response.session_id,
          timestamp: Date.now(),
        };
        setMessages((prev) => [...prev, answerMsg]);
        setActiveSessionId(response.session_id);
        setRefreshKey(k => k + 1);
      } catch (err: unknown) {
        const errorText = err instanceof Error ? err.message : 'Failed to get response';
        const errorMsg: ChatMessageData = {
          id: uid(),
          role: 'error',
          text: errorText,
        };
        setMessages((prev) => [...prev, errorMsg]);
      }
      setIsLoading(false);
    },
    [activeSessionId],
  );

  return (
    <ErrorBoundary>
      <div className="flex h-screen bg-retro-bg">
        <Sidebar
          onNewChat={handleNewChat}
          onSelectSession={handleSelectSession}
          activeSessionId={activeSessionId}
          collapsed={sidebarCollapsed}
          onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
          refreshKey={refreshKey}
        />
        <div className="flex-1 flex flex-col min-w-0">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-2 border-b border-retro-border bg-retro-surface">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-retro-cyan uppercase tracking-widest">
                &gt; QWEN COUNCIL
              </span>
              {activeSessionId && (
                <span className="text-[10px] text-gray-600 font-mono">
                  {activeSessionId.slice(0, 12)}
                </span>
              )}
            </div>
            <button
              onClick={handleNewChat}
              className="flex items-center gap-1.5 px-3 py-1.5 border border-retro-border text-xs text-gray-400 hover:text-retro-cyan hover:border-retro-cyan transition-colors"
              aria-label="New session"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
              </svg>
              New Session
            </button>
          </div>
          {/* Chat / Live Council Status */}
          {isLoading && streamPayloadRef.current ? (
            <div className="flex-1 overflow-y-auto scrollbar-retro">
              <LiveCouncilStatus
                isRunning={isLoading}
                payload={streamPayloadRef.current}
                onComplete={handleStreamComplete}
                onError={handleStreamError}
              />
            </div>
          ) : (
            <ChatView
              messages={messages}
              onSubmit={handleSubmit}
              onChatSubmit={handleChatSubmit}
              disabled={isLoading}
              sessionId={activeSessionId}
            />
          )}
        </div>
      </div>
    </ErrorBoundary>
  );
}
