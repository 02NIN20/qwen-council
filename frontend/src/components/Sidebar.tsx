import { useState, useEffect, useCallback, useMemo } from 'react';
import { getSessions, deleteSession } from '../api/council';
import type { SessionSummary } from '../types';

interface SidebarProps {
  onNewChat: () => void;
  onSelectSession: (sessionId: string) => void;
  activeSessionId?: string;
  collapsed: boolean;
  onToggle: () => void;
  refreshKey?: number;
  onOpenBenchmark?: () => void;
}

function timeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  if (!then) return '';
  const diff = Math.max(0, now - then);
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

type FilterMode = 'all' | 'review' | 'chat';

export default function Sidebar({ onNewChat, onSelectSession, activeSessionId, collapsed, onToggle, refreshKey, onOpenBenchmark }: SidebarProps) {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState<FilterMode>('all');

  const loadSessions = useCallback(() => {
    setLoading(true);
    getSessions()
      .then(setSessions)
      .catch(() => {})
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
      loadSessions();
    } catch {
      alert('Failed to delete session');
    }
  }, [loadSessions]);

  const filteredSessions = useMemo(() => {
    if (filter === 'all') return sessions;
    const isChat = filter === 'chat';
    return sessions.filter(s => s.id.startsWith('chat-') === isChat);
  }, [sessions, filter]);

  const counts = useMemo(() => ({
    all: sessions.length,
    review: sessions.filter(s => !s.id.startsWith('chat-')).length,
    chat: sessions.filter(s => s.id.startsWith('chat-')).length,
  }), [sessions]);

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
        {onOpenBenchmark && (
          <button onClick={onOpenBenchmark} className="text-gray-600 hover:text-retro-yellow transition-colors" aria-label="Benchmark" title="Benchmark">
            <span className="text-[11px] font-mono font-bold">[B]</span>
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="w-64 bg-retro-surface border-r border-retro-border flex flex-col h-full">
      <div className="p-3 border-b border-retro-border flex items-center justify-between">
        <span className="text-xs font-bold text-retro-cyan uppercase tracking-widest">&gt; Qwen Council</span>
        <button onClick={onToggle} className="text-gray-500 hover:text-retro-cyan transition-colors" aria-label="Collapse sidebar">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
          </svg>
        </button>
      </div>

      <div className="p-2 space-y-1">
        <button
          onClick={onNewChat}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 border border-retro-border text-xs text-retro-cyan hover:bg-retro-bg transition-colors font-bold uppercase tracking-wider"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
          New Session
        </button>
        {onOpenBenchmark && (
          <button
            onClick={onOpenBenchmark}
            className="w-full flex items-center justify-center gap-2 px-3 py-1.5 border border-retro-border text-[10px] text-gray-500 hover:text-retro-yellow hover:border-retro-yellow transition-colors font-mono uppercase tracking-wider"
          >
            [B] Benchmark
          </button>
        )}
      </div>

      {/* Filter tabs */}
      <div className="flex gap-0.5 px-2 pb-1">
        {(['all', 'review', 'chat'] as const).map((mode) => (
          <button
            key={mode}
            onClick={() => setFilter(mode)}
            className={`flex-1 py-1 text-[10px] font-bold uppercase tracking-wider border transition-colors ${
              filter === mode
                ? 'border-retro-cyan bg-retro-cyan/10 text-retro-cyan'
                : 'border-transparent text-gray-600 hover:text-gray-400 hover:border-retro-border'
            }`}
          >
            {mode === 'all' ? `All ${counts.all}` : mode === 'review' ? `R:${counts.review}` : `C:${counts.chat}`}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-retro px-2 py-1 space-y-1">
        {loading && (
          <div className="space-y-2 py-4">
            {[1,2,3,4].map(i => (
              <div key={i} className="px-2 py-2 animate-pulse">
                <div className="h-3 bg-gray-800 rounded w-3/4 mb-1.5" />
                <div className="h-2 bg-gray-800 rounded w-1/2" />
              </div>
            ))}
          </div>
        )}
        {!loading && filteredSessions.length === 0 && (
          <p className="text-[10px] text-gray-700 text-center py-4">
            {filter === 'all' ? 'No sessions yet' : `No ${filter} sessions`}
          </p>
        )}
        {filteredSessions.map((session) => {
          const isChat = session.id.startsWith('chat-');
          const isActive = activeSessionId === session.id;
          return (
          <div
            key={session.id}
            className={`group flex items-start gap-1.5 px-2 py-2 text-xs transition-colors border cursor-pointer ${
              isActive
                ? 'bg-retro-bg border-retro-cyan text-gray-200'
                : 'bg-transparent border-transparent text-gray-500 hover:bg-retro-bg hover:border-retro-border hover:text-gray-300'
            }`}
            onClick={() => onSelectSession(session.id)}
          >
            {/* Type icon */}
            <span className={`mt-0.5 text-[11px] font-mono flex-shrink-0 ${isChat ? 'text-retro-cyan' : 'text-retro-yellow'}`}>
              {isChat ? '[C]' : '[R]'}
            </span>
            <div className="flex-1 min-w-0">
              <p className="font-bold truncate flex items-center gap-1.5">
                {isActive && <span className="text-retro-cyan">&gt;</span>}
                {session.code_preview.slice(0, 36) || 'Untitled'}
              </p>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-[10px] text-gray-700 font-mono" title={new Date(session.created_at).toLocaleString()}>
                  {timeAgo(session.created_at)}
                </span>
                {isChat ? (
                  <span className="text-[10px] text-retro-cyan/60 font-mono">chat</span>
                ) : (
                  <span className="text-[10px] text-gray-700 font-mono">{session.finding_count} find{session.finding_count !== 1 ? 'ings' : 'ing'}</span>
                )}
              </div>
            </div>
            <button
              onClick={(e) => handleDelete(e, session.id)}
              className="p-1 text-gray-700 opacity-0 group-hover:opacity-100 hover:text-retro-red transition-all flex-shrink-0"
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