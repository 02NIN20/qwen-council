import { useState, useEffect } from 'react';
import { getSessions } from '../api/council';
import type { SessionSummary } from '../types';

interface SidebarProps {
  onNewChat: () => void;
  onSelectSession: (sessionId: string) => void;
  activeSessionId?: string;
  collapsed: boolean;
  onToggle: () => void;
}

export default function Sidebar({ onNewChat, onSelectSession, activeSessionId, collapsed, onToggle }: SidebarProps) {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    getSessions()
      .then(setSessions)
      .catch(() => {}) // silent fail if no DB
      .finally(() => setLoading(false));
  }, []);

  if (collapsed) {
    return (
      <div className="flex flex-col items-center bg-retro-surface border-r border-retro-border py-3 px-2 gap-3">
        <button onClick={onToggle} className="text-retro-cyan hover:text-retro-green transition-colors" aria-label="Expand sidebar">
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
          </svg>
        </button>
        <button onClick={onNewChat} className="text-retro-cyan hover:text-retro-green transition-colors" aria-label="New chat">
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
        </button>
      </div>
    );
  }

  return (
    <div className="w-64 bg-retro-surface border-r border-retro-border flex flex-col h-full">
      {/* Header */}
      <div className="p-3 border-b border-retro-border flex items-center justify-between">
        <span className="text-xs font-bold text-retro-cyan uppercase tracking-widest">&gt; Qwen Council</span>
        <button onClick={onToggle} className="text-gray-500 hover:text-retro-cyan transition-colors" aria-label="Collapse sidebar">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
          </svg>
        </button>
      </div>

      {/* New Chat button */}
      <div className="p-2">
        <button
          onClick={onNewChat}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 border border-retro-border text-xs text-retro-cyan hover:bg-retro-bg transition-colors font-bold uppercase tracking-wider"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
          New Review
        </button>
      </div>

      {/* Sessions list */}
      <div className="flex-1 overflow-y-auto scrollbar-retro px-2 py-1 space-y-1">
        {loading && <p className="text-[10px] text-gray-600 text-center py-4">Loading...</p>}
        {!loading && sessions.length === 0 && (
          <p className="text-[10px] text-gray-700 text-center py-4">No sessions yet</p>
        )}
        {sessions.map((session) => (
          <button
            key={session.id}
            onClick={() => onSelectSession(session.id)}
            className={`w-full text-left px-3 py-2 text-xs transition-colors border ${
              activeSessionId === session.id
                ? 'bg-retro-bg border-retro-cyan text-gray-200'
                : 'bg-transparent border-transparent text-gray-500 hover:bg-retro-bg hover:border-retro-border hover:text-gray-300'
            }`}
          >
            <p className="font-bold truncate">{session.code_preview.slice(0, 40)}</p>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-[10px] text-gray-600">{session.created_at?.slice(0, 10) || ''}</span>
              <span className="text-[10px] text-gray-600">{session.finding_count} findings</span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
