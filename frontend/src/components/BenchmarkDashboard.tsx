import { BENCHMARK_DATA } from '../data/benchmarkData';

/* ─── Pure CSS horizontal bar ───────────────────────────────────── */

function Bar({
  label,
  singleVal,
  multiVal,
  maxVal,
  unit = '',
  singleLabel = 'Single',
  multiLabel = 'Multi',
  invert = false,
}: {
  label: string;
  singleVal: number;
  multiVal: number;
  maxVal: number;
  unit?: string;
  singleLabel?: string;
  multiLabel?: string;
  invert?: boolean;
}) {
  const better = invert ? Math.min : Math.max;
  const best = better(singleVal, multiVal);
  const effectiveMax = Math.max(singleVal, multiVal, maxVal, 1);
  const singlePct = Math.min((singleVal / effectiveMax) * 100, 100);
  const multiPct = Math.min((multiVal / effectiveMax) * 100, 100);

  return (
    <div className="mb-3">
      <div className="flex justify-between text-[11px] font-mono mb-1">
        <span className="text-gray-400">{label}</span>
        <span className="text-gray-600">
          {singleVal}{unit} vs {multiVal}{unit}
          {singleVal !== multiVal && (
            <span className={best === multiVal ? 'text-retro-green ml-1' : 'text-retro-orange ml-1'}>
              ({best === multiVal ? '+' : '-'}
              {Math.abs(Math.round(((multiVal - singleVal) / singleVal) * 100))}%)
            </span>
          )}
        </span>
      </div>
      <div className="flex gap-2 items-center">
        <span className="text-[10px] text-gray-600 w-10 text-right font-mono">{singleLabel}</span>
        <div className="flex-1 h-3 bg-gray-800 relative">
          <div
            className="absolute inset-y-0 left-0 bg-retro-cyan/60 transition-all"
            style={{ width: `${singlePct}%` }}
          />
        </div>
      </div>
      <div className="flex gap-2 items-center mt-0.5">
        <span className="text-[10px] text-gray-600 w-10 text-right font-mono">{multiLabel}</span>
        <div className="flex-1 h-3 bg-gray-800 relative">
          <div
            className="absolute inset-y-0 left-0 bg-retro-green/70 transition-all"
            style={{ width: `${multiPct}%` }}
          />
        </div>
      </div>
    </div>
  );
}

/* ─── Stat card ─────────────────────────────────────────────────── */

function StatCard({
  title,
  singleVal,
  multiVal,
  unit = '',
  better = 'higher',
}: {
  title: string;
  singleVal: number | string;
  multiVal: number | string;
  unit?: string;
  better?: 'higher' | 'lower';
}) {
  const s = typeof singleVal === 'number' ? singleVal : parseFloat(singleVal as string);
  const m = typeof multiVal === 'number' ? multiVal : parseFloat(multiVal as string);
  const best = better === 'higher' ? Math.max(s, m) : Math.min(s, m);
  return (
    <div className="border border-retro-border bg-retro-bg p-2.5 flex-1 min-w-[130px]">
      <p className="text-[10px] text-gray-600 font-mono uppercase tracking-wider mb-1">{title}</p>
      <div className="flex justify-between items-end">
        <div>
          <span className="text-[10px] text-gray-600 font-mono">S</span>
          <p className={`text-sm font-bold font-mono ${best === s ? 'text-retro-cyan' : 'text-gray-500'}`}>
            {singleVal}{unit}
          </p>
        </div>
        <div className="text-right">
          <span className="text-[10px] text-gray-600 font-mono">M</span>
          <p className={`text-sm font-bold font-mono ${best === m ? 'text-retro-green' : 'text-gray-500'}`}>
            {multiVal}{unit}
          </p>
        </div>
      </div>
    </div>
  );
}

/* ─── Severity bar ──────────────────────────────────────────────── */

const SEV_COLORS: Record<string, string> = {
  Critical: '#EF4444',
  High: '#F59E0B',
  Medium: '#3B82F6',
  Low: '#6B7280',
};

function SeverityChart({ data }: { data: Record<string, { single: number; multi: number }> }) {
  const maxVal = Math.max(...Object.values(data).flatMap((d) => [d.single, d.multi]), 1);
  return (
    <div className="space-y-2">
      {Object.entries(data).map(([sev, vals]) => (
        <div key={sev}>
          <div className="flex justify-between text-[10px] font-mono mb-0.5">
            <span style={{ color: SEV_COLORS[sev] }} className="font-bold">{sev}</span>
            <span className="text-gray-600">{vals.single} / {vals.multi}</span>
          </div>
          <div className="flex gap-1 items-center">
            <span className="text-[9px] text-gray-700 w-4">S</span>
            <div className="flex-1 h-2.5 bg-gray-800">
              <div className="h-full transition-all" style={{ width: `${(vals.single / maxVal) * 100}%`, backgroundColor: SEV_COLORS[sev], opacity: 0.5 }} />
            </div>
          </div>
          <div className="flex gap-1 items-center mt-0.5">
            <span className="text-[9px] text-gray-700 w-4">M</span>
            <div className="flex-1 h-2.5 bg-gray-800">
              <div className="h-full transition-all" style={{ width: `${(vals.multi / maxVal) * 100}%`, backgroundColor: SEV_COLORS[sev], opacity: 0.9 }} />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

/* ─── Category grid ─────────────────────────────────────────────── */

function CategoryGrid({ items }: { items: { name: string; single: boolean; multi: boolean }[] }) {
  return (
    <div className="grid grid-cols-2 gap-1.5">
      {items.map((cat) => (
        <div key={cat.name} className="border border-retro-border bg-retro-bg p-2 text-center">
          <p className="text-[11px] font-bold text-gray-300 mb-1">{cat.name}</p>
          <div className="flex justify-center gap-3 text-[10px] font-mono">
            <span className={cat.single ? 'text-retro-green' : 'text-gray-700'}>
              S: {cat.single ? 'OK' : '--'}
            </span>
            <span className={cat.multi ? 'text-retro-green' : 'text-gray-700'}>
              M: {cat.multi ? 'OK' : '--'}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

/* ─── Overlap visual ────────────────────────────────────────────── */

function OverlapSection({ data }: { data: typeof BENCHMARK_DATA.overlap }) {
  const overlapPct = Math.round((data.overlapping / data.singleTotal) * 100);
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-3 justify-center py-3">
        <div className="text-center">
          <p className="text-2xl font-bold text-retro-cyan font-mono">{data.singleUnique}</p>
          <p className="text-[10px] text-gray-600">Single-only</p>
        </div>
        <div className="text-center">
          <p className="text-2xl font-bold text-retro-green font-mono">{data.overlapping}</p>
          <p className="text-[10px] text-gray-600">Overlap ({overlapPct}%)</p>
        </div>
        <div className="text-center">
          <p className="text-2xl font-bold text-retro-yellow font-mono">{data.multiUnique}</p>
          <p className="text-[10px] text-gray-600">Multi-only</p>
        </div>
      </div>
      <div className="h-4 bg-gray-800 flex">
        <div
          className="h-full bg-retro-cyan/50"
          style={{ width: `${(data.singleUnique / (data.singleUnique + data.overlapping + data.multiUnique)) * 100}%` }}
          title={`Single-only: ${data.singleUnique}`}
        />
        <div
          className="h-full bg-retro-green/70"
          style={{ width: `${(data.overlapping / (data.singleUnique + data.overlapping + data.multiUnique)) * 100}%` }}
          title={`Overlap: ${data.overlapping}`}
        />
        <div
          className="h-full bg-retro-yellow/60"
          style={{ width: `${(data.multiUnique / (data.singleUnique + data.overlapping + data.multiUnique)) * 100}%` }}
          title={`Multi-only: ${data.multiUnique}`}
        />
      </div>
    </div>
  );
}

/* ─── Main component ────────────────────────────────────────────── */

interface BenchmarkDashboardProps {
  onClose: () => void;
}

export default function BenchmarkDashboard({ onClose }: BenchmarkDashboardProps) {
  const d = BENCHMARK_DATA;

  return (
    <div className="flex-1 overflow-y-auto scrollbar-retro">
      <div className="max-w-3xl mx-auto px-4 py-6 space-y-5">
        {/* ── Header ──────────────────────────────────────────── */}
        <div className="flex items-center justify-between border-b border-retro-border pb-3">
          <div>
            <h1 className="text-lg font-bold text-retro-cyan uppercase tracking-wider">
              &gt; BENCHMARK RESULTS
            </h1>
            <p className="text-[10px] text-gray-600 font-mono mt-0.5">
              Multi-Agent Council vs Single-Agent Generalist &mdash; qwen-plus-2025-07-28
            </p>
          </div>
          <button
            onClick={onClose}
            className="px-3 py-1 border border-retro-border text-[10px] text-gray-500 hover:text-retro-cyan hover:border-retro-cyan transition-colors font-mono"
          >
            [X] Close
          </button>
        </div>

        {/* ── Summary cards ────────────────────────────────────── */}
        <div className="flex flex-wrap gap-2">
          <StatCard title="Total findings" singleVal={14} multiVal={33} />
          <StatCard title="Recall" singleVal={92.9} multiVal={66.1} unit="%" />
          <StatCard title="Precision" singleVal={54.2} multiVal={41.0} unit="%" better="higher" />
          <StatCard title="F1 Score" singleVal={69.6} multiVal={52.2} unit="%" />
          <StatCard title="Categories" singleVal="4/6" multiVal="6/6" />
          <StatCard title="Avg severity" singleVal={3.0} multiVal={3.2} unit="x" />
          <StatCard title="Est. cost (USD)" singleVal={0.004} multiVal={0.028} better="lower" />
          <StatCard title="Time (sec)" singleVal={8.2} multiVal={32.5} unit="s" better="lower" />
        </div>

        {/* ── Findings per app ─────────────────────────────────── */}
        <div className="finding-item">
          <p className="text-[10px] text-retro-cyan font-bold uppercase tracking-wider mb-2">
            &gt; Findings per application
          </p>
          {d.perApp.map((app) => (
            <Bar key={app.name} label={app.name} singleVal={app.single} multiVal={app.multi} maxVal={Math.max(...d.perApp.map(a => a.multi))} />
          ))}
          <Bar label="Total (combined)" singleVal={d.totalFindings.single} multiVal={d.totalFindings.multi} maxVal={Math.max(d.totalFindings.single, d.totalFindings.multi)} />
        </div>

        {/* ── Precision / Recall / F1 ──────────────────────────── */}
        <div className="finding-item">
          <p className="text-[10px] text-retro-cyan font-bold uppercase tracking-wider mb-2">
            &gt; Accuracy metrics
          </p>
          <Bar label="Precision" singleVal={d.precision.single} multiVal={d.precision.multi} maxVal={100} unit="%" />
          <Bar label="Recall" singleVal={d.recall.single} multiVal={d.recall.multi} maxVal={100} unit="%" />
          <Bar label="F1 Score" singleVal={d.f1Score.single} multiVal={d.f1Score.multi} maxVal={100} unit="%" />
        </div>

        {/* ── Category coverage ──────────────────────────────────── */}
        <div className="finding-item">
          <p className="text-[10px] text-retro-cyan font-bold uppercase tracking-wider mb-2">
            &gt; Category coverage
          </p>
          <CategoryGrid items={d.categoryCoverage} />
        </div>

        {/* ── Severity distribution ──────────────────────────────── */}
        <div className="finding-item">
          <p className="text-[10px] text-retro-cyan font-bold uppercase tracking-wider mb-2">
            &gt; Severity distribution
          </p>
          <SeverityChart data={d.severityDistribution} />
        </div>

        {/* ── Overlap ────────────────────────────────────────────── */}
        <div className="finding-item">
          <p className="text-[10px] text-retro-cyan font-bold uppercase tracking-wider mb-2">
            &gt; Finding overlap
          </p>
          <OverlapSection data={d.overlap} />
        </div>

        {/* ── Conclusion ──────────────────────────────────────────── */}
        <div className="finding-item">
          <p className="text-[10px] text-retro-cyan font-bold uppercase tracking-wider mb-2">
            &gt; Verdict
          </p>
          <div className="border border-retro-border bg-retro-bg p-3">
            <div className="grid grid-cols-2 gap-3 text-[11px] font-mono">
              <div>
                <p className="text-retro-green font-bold mb-1">Multi-agent strengths</p>
                <ul className="space-y-0.5 text-gray-400">
                  <li>+ 6/6 categories covered</li>
                  <li>+ 21% higher avg severity</li>
                  <li>+ 13 unique findings</li>
                  <li>Agent debate + synthesis</li>
                </ul>
              </div>
              <div>
                <p className="text-retro-orange font-bold mb-1">Trade-offs</p>
                <ul className="space-y-0.5 text-gray-400">
                  <li>- 12.5x more API cost</li>
                  <li>- 12.7x slower (152s)</li>
                  <li>- 24.6% lower F1</li>
                  <li>Best for large codebases</li>
                </ul>
              </div>
            </div>
          </div>
        </div>

        {/* ── Mode recommendation ──────────────────────────────────── */}
        <div className="finding-item">
          <p className="text-[10px] text-retro-cyan font-bold uppercase tracking-wider mb-2">
            &gt; Mode recommendation
          </p>
          <div className="grid grid-cols-2 gap-2">
            <div className="border border-retro-border bg-retro-bg p-2.5">
              <p className="text-[10px] font-bold text-retro-yellow uppercase tracking-wider mb-1">Light mode</p>
              <p className="text-[10px] text-gray-500 font-mono">3 agents, 2 rounds</p>
              <p className="text-[10px] text-gray-400 mt-1">Quick scans, budget-constrained, ~60% less cost</p>
            </div>
            <div className="border border-retro-border bg-retro-bg p-2.5">
              <p className="text-[10px] font-bold text-retro-green uppercase tracking-wider mb-1">Full mode</p>
              <p className="text-[10px] text-gray-500 font-mono">6 agents, 3 rounds</p>
              <p className="text-[10px] text-gray-400 mt-1">Deep review, critical code, max coverage</p>
            </div>
          </div>
        </div>

        <p className="text-[10px] text-gray-700 font-mono text-center pb-4">
          Dataset: 7 OWASP benchmark samples &middot; Ground truth: 36 known vulnerabilities &middot; Model: qwen-plus-2025-07-28 &middot; Metrics use consolidated findings (synthesizer output)
        </p>
      </div>
    </div>
  );
}
