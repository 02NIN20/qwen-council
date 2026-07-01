import { useState, useEffect, useCallback } from 'react';
import { getSessions, deleteSession } from '../api/council';
import type { SessionSummary } from '../types';

interface SidebarProps {
  onNewChat: () => void;
  onSelectSession: (sessionId: string) => void;
  activeSessionId?: string;
  collapsed: boolean;
  onToggle: () => void;
  refreshKey?: number;
}

export default function Sidebar({ onNewChat, onSelectSession, activeSessionId, collapsed, onToggle, refreshKey }: SidebarProps) {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [loading, setLoading] = useState(false);

  const loadSessions = useCallback(() => {
    setLoading(true);
    getSessions()
      .then(setSessions)
      .catch(() => {}) // silent fail if no DB
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    loadSessions();
  }, [refreshKey, loadSessions]);

  const handleDelete = useCallback(async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    e.preventDefault();
    if (!confirm('Delete this session permanently?')) return;
    try {
      await deleteSession(sessionId);
      loadSessions(); // refresh list after delete
    } catch {
      alert('Failed to delete session');
    }
  }, [loadSessions]);

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
        {sessions.map((session) => {
          const isChat = session.id.startsWith('chat-');
          const isActive = activeSessionId === session.id;
          return (
          <div
            key={session.id}
            className={`group flex items-start gap-1 px-2 py-2 text-xs transition-colors border cursor-pointer ${
              isActive
                ? 'bg-retro-bg border-retro-cyan text-gray-200'
                : 'bg-transparent border-transparent text-gray-500 hover:bg-retro-bg hover:border-retro-border hover:text-gray-300'
            }`}
            onClick={() => onSelectSession(session.id)}
          >
            {/* Type indicator */}
            <span className={`mt-0.5 text-[10px] font-mono flex-shrink-0 ${isChat ? 'text-retro-cyan' : 'text-gray-700'}`}>
              {isChat ? '💬' : '📄'}
            </span>
            {/* Session info */}
            <div className="flex-1 min-w-0">
              <p className={`font-bold truncate ${isActive ? '' : ''}`}>
                {isActive ? '> ' : ''}{session.code_preview.slice(0, 40)}
              </p>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-[10px] text-gray-600">{session.created_at?.slice(0, 10) || ''}</span>
                {isChat ? (
                  <span className="text-[10px] text-retro-cyan/70">Chat</span>
                ) : (
                  <span className="text-[10px] text-gray-600">{session.finding_count} findings</span>
                )}
              </div>
            </div>
            {/* Delete button — visible on hover */}
            <button
              onClick={(e) => handleDelete(e, session.id)}
              className="p-1 text-gray-600 opacity-0 group-hover:opacity-100 hover:text-retro-red transition-all flex-shrink-0"
              aria-label={`Delete session ${session.id}`}
              title="Delete session"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
              </svg>
            </button>
          </div>
          );
        })}
      </div>
    </div>
  );
}
