import { useState, useRef, useEffect, useCallback, type DragEvent, type ChangeEvent } from 'react';

interface ChatInputProps {
  onSubmit: (code: string, files: { filename: string; content: string }[], imageUrl?: string, instruction?: string) => void;
  onChatSubmit: (message: string) => void;
  disabled: boolean;
}

const ACCEPTED_EXTENSIONS = [
  '.py', '.js', '.ts', '.jsx', '.tsx', '.html', '.css', '.json',
  '.md', '.txt', '.sql', '.java', '.cpp', '.c', '.go', '.rs',
  '.rb', '.php', '.swift', '.kt', '.yaml', '.yml', '.toml',
  '.sh', '.bash', '.zsh', '.dockerfile', '.graphql', '.proto',
];

const ACCEPT_STRING = ACCEPTED_EXTENSIONS.join(',');
const MAX_FILE_SIZE = 50 * 1024; // 50 KB

interface SelectedFile {
  name: string;
  size: number;
  content: string;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function truncateFileName(name: string, maxLen = 30): string {
  if (name.length <= maxLen) return name;
  const ext = name.lastIndexOf('.');
  if (ext === -1) return name.slice(0, maxLen - 3) + '...';
  const extStr = name.slice(ext);
  const base = name.slice(0, ext);
  const available = maxLen - extStr.length - 3;
  if (available < 1) return name.slice(0, maxLen - 3) + '...';
  return base.slice(0, available) + '...' + extStr;
}

export default function ChatInput({ onSubmit, onChatSubmit, disabled }: ChatInputProps) {
  const [files, setFiles] = useState<SelectedFile[]>([]);
  const [showImageInput, setShowImageInput] = useState(false);
  const [imageUrl, setImageUrl] = useState('');
  const [instruction, setInstruction] = useState('');
  const [isDragOver, setIsDragOver] = useState(false);
  const [chatText, setChatText] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Reset file input value
  useEffect(() => {
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, [files]);

  const readFiles = useCallback((fileList: FileList) => {
    const pending: SelectedFile[] = [];
    let hasOversized = false;
    for (const f of Array.from(fileList)) {
      if (f.size > MAX_FILE_SIZE) {
        hasOversized = true;
        continue;
      }
      pending.push({ name: f.name, size: f.size, content: '' });
    }
    if (hasOversized) {
      alert(`Some files were skipped (max ${formatFileSize(MAX_FILE_SIZE)} each).`);
    }
    if (pending.length === 0) return;

    let loaded = 0;
    const results: SelectedFile[] = [];
    for (const pf of pending) {
      const found = Array.from(fileList).find((f) => f.name === pf.name);
      if (!found) continue;
      const reader = new FileReader();
      reader.onload = () => {
        results.push({ name: pf.name, size: pf.size, content: reader.result as string });
        loaded++;
        if (loaded === pending.length) {
          setFiles((prev) => [...prev, ...results]);
        }
      };
      reader.onerror = () => {
        loaded++;
        if (loaded === pending.length) {
          // just skip failed files
        }
      };
      reader.readAsText(found);
    }
  }, []);

  const handleFileSelect = useCallback(
    (e: ChangeEvent<HTMLInputElement>) => {
      const fl = e.target.files;
      if (!fl || fl.length === 0) return;
      readFiles(fl);
    },
    [readFiles]
  );

  const handleDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragOver(false);
      const fl = e.dataTransfer.files;
      if (!fl || fl.length === 0) return;
      readFiles(fl);
    },
    [readFiles]
  );

  const handleDragOver = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  }, []);

  const handleRemoveFile = useCallback((index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const handleSubmit = useCallback(() => {
    if (files.length === 0 || disabled) return;
    // Always send as files[] — backend builds the multi-file context.
    // Code param is empty to avoid duplication in the context.
    const payload = files.map((f) => ({
      filename: f.name,
      content: f.content,
    }));
    onSubmit('', payload, imageUrl.trim() || undefined, instruction.trim() || undefined);
    setFiles([]);
    setInstruction('');
    setImageUrl('');
    setShowImageInput(false);
  }, [files, imageUrl, instruction, disabled, onSubmit]);

  const handleChatSubmit = useCallback(() => {
    if (!chatText.trim() || disabled) return;
    onChatSubmit(chatText.trim());
    setChatText('');
  }, [chatText, disabled, onChatSubmit]);

  const handleKeyDownChat = useCallback(
    (e: React.KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        handleChatSubmit();
      }
    },
    [handleChatSubmit]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit]
  );

  const canSubmit = files.length > 0 && !disabled;

  return (
    <div className="border-t-2 border-retro-border bg-retro-surface pt-3 pb-4 px-4">
      {/* Image URL input (expandable) */}
      {showImageInput && (
        <div className="mb-2 animate-fade-in">
          <div className="flex items-center gap-2">
            <svg
              className="w-5 h-5 text-retro-cyan flex-shrink-0"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1.5}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z"
              />
            </svg>
            <input
              type="url"
              value={imageUrl}
              onChange={(e) => setImageUrl(e.target.value)}
              placeholder="Paste image URL for additional context..."
              className="flex-1 bg-retro-bg border border-retro-border px-3 py-2 text-sm text-gray-200 placeholder:text-gray-600 outline-none focus:border-retro-cyan transition-colors font-mono"
              aria-label="Optional image URL"
              disabled={disabled}
            />
            {imageUrl && (
              <button
                onClick={() => setImageUrl('')}
                className="text-gray-500 hover:text-retro-cyan transition-colors"
                aria-label="Clear image URL"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>
          {imageUrl && (
            <div className="mt-2 max-h-32 overflow-hidden border border-retro-border">
              <img
                src={imageUrl}
                alt="Preview"
                className="w-full h-auto object-contain max-h-32"
                onError={(e) => {
                  (e.target as HTMLImageElement).style.display = 'none';
                }}
              />
            </div>
          )}
        </div>
      )}

      {/* File drop zone / file list */}
      <div className="flex items-end gap-2">
        <div className="flex-1 relative">
          {files.length === 0 ? (
            /* ── Drop zone ── */
            <div
              role="button"
              tabIndex={0}
              aria-label="Drop file here or click to browse"
              className={`drop-zone flex flex-col items-center justify-center gap-2 px-4 py-6 transition-colors ${
                isDragOver ? 'drag-over' : ''
              }`}
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onClick={() => fileInputRef.current?.click()}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  fileInputRef.current?.click();
                }
              }}
            >
              <svg
                className="w-8 h-8 text-retro-cyan"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={1.5}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
                />
              </svg>
              <p className="text-xs text-gray-500 tracking-wider uppercase">
                DROP FILE HERE
              </p>
              <p className="text-[10px] text-gray-600">
                or click to browse
              </p>
              <p className="text-[9px] text-gray-700 mt-1">
                max 50 KB &middot; .py .js .ts .html .css .json ...
              </p>
            </div>
          ) : (
            /* ── Selected files list ── */
            <div className="max-h-48 overflow-y-auto space-y-1.5 pr-1">
              {files.map((f, idx) => (
                <div
                  key={`${f.name}-${idx}`}
                  className="flex items-center gap-3 px-3 py-2 bg-[#0d1117] border border-retro-border rounded"
                >
                  {/* File icon */}
                  <svg
                    className="w-6 h-6 text-retro-cyan flex-shrink-0"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={1.5}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"
                    />
                  </svg>
                  {/* File details */}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-gray-200 font-bold truncate">
                      {truncateFileName(f.name)}
                    </p>
                    <p className="text-[10px] text-gray-500">
                      {formatFileSize(f.size)} / 50 KB max
                    </p>
                  </div>
                  {/* Remove button */}
                  <button
                    onClick={() => handleRemoveFile(idx)}
                    className="p-1 text-gray-500 hover:text-retro-red transition-colors flex-shrink-0"
                    aria-label={`Remove ${f.name}`}
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              ))}
              {/* Add more files button */}
              <button
                onClick={() => fileInputRef.current?.click()}
                className="w-full flex items-center justify-center gap-1.5 px-3 py-1.5 border border-dashed border-retro-border text-gray-500 hover:text-retro-cyan hover:border-retro-cyan transition-colors text-xs"
                aria-label="Add more files"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
                </svg>
                Add more files
              </button>
            </div>
          )}

          {/* Hidden file input */}
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPT_STRING}
            multiple={true}
            className="hidden"
            onChange={handleFileSelect}
            aria-hidden="true"
          />

          {/* Instruction textarea — visible when files are selected */}
          {files.length > 0 && (
            <textarea
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
              placeholder="Add instructions for the council... (e.g. 'Focus on security, ignore style issues')"
              className="w-full bg-retro-bg border border-retro-border px-3 py-2 text-xs text-gray-300 placeholder:text-gray-600 outline-none focus:border-retro-cyan transition-colors font-mono resize-none mt-2"
              rows={2}
              disabled={disabled}
              aria-label="Instructions for the council"
            />
          )}
        </div>

        {/* Buttons */}
        <div className="flex items-center gap-1.5 flex-shrink-0 pb-0.5">
          {/* Attach image toggle */}
          <button
            onClick={() => setShowImageInput(!showImageInput)}
            className={`p-2.5 border-2 transition-colors ${
              showImageInput
                ? 'bg-retro-cyan/10 border-retro-cyan text-retro-cyan'
                : 'border-retro-border text-gray-500 hover:text-retro-cyan hover:border-retro-cyan'
            }`}
            aria-label={showImageInput ? 'Hide image field' : 'Attach image URL'}
            disabled={disabled}
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z"
              />
            </svg>
          </button>

          {/* Send button */}
          <button
            onClick={handleSubmit}
            disabled={!canSubmit}
            className="p-2.5 border-2 border-retro-cyan bg-retro-cyan text-black font-bold hover:bg-transparent hover:text-retro-cyan transition-colors duration-150 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-retro-cyan disabled:hover:text-black"
            aria-label="Send code for review"
          >
            {disabled ? (
              <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                />
              </svg>
            ) : (
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14M12 5l7 7-7 7" />
              </svg>
            )}
          </button>
        </div>
      </div>

      {/* Separator between file mode and chat mode */}
      {files.length > 0 && (
        <div className="flex items-center gap-2 my-2">
          <div className="flex-1 h-px bg-retro-border" />
          <span className="text-[10px] text-gray-600 uppercase tracking-wider font-mono">or ask a question</span>
          <div className="flex-1 h-px bg-retro-border" />
        </div>
      )}

      {/* Chat text input */}
      <div className="flex gap-2">
        <textarea
          value={chatText}
          onChange={(e) => setChatText(e.target.value)}
          onKeyDown={handleKeyDownChat}
          placeholder={files.length > 0 ? "Ask a question about the attached files..." : "Ask a question to the expert panel..."}
          className="flex-1 bg-retro-bg border border-retro-border px-3 py-2 text-sm text-gray-200 placeholder:text-gray-600 outline-none focus:border-retro-cyan transition-colors font-mono resize-none"
          rows={2}
          disabled={disabled}
          aria-label="Ask a question"
        />
        <button
          onClick={handleChatSubmit}
          disabled={!chatText.trim() || disabled}
          className="p-2.5 border-2 border-retro-cyan bg-retro-cyan text-black font-bold hover:bg-transparent hover:text-retro-cyan transition-colors disabled:opacity-40"
          aria-label="Send question"
        >
          {disabled ? (
            <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          ) : (
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          )}
        </button>
      </div>

      {/* Hint */}
      {!disabled && files.length === 0 && !chatText.trim() && (
        <p className="text-[10px] text-gray-600 mt-1.5 text-center">
          <kbd className="px-1 py-0.5 bg-retro-bg text-gray-500 text-[10px] font-mono border border-retro-border">
            Ctrl+Enter
          </kbd>{' '}
          to send
        </p>
      )}
    </div>
  );
}
