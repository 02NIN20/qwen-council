import type { Report as ReportType } from '../types';
import { AGENTS } from '../types';

interface FinalReportProps {
  report: ReportType;
  onNewReview: () => void;
  onHistory?: () => void;
}

function getAgentColor(agentId: string): string {
  const agent = AGENTS.find((a) => a.id === agentId);
  return agent?.color ?? '#64748B';
}

function getAgentIcon(agentId: string): string {
  const agent = AGENTS.find((a) => a.id === agentId);
  return agent?.icon ?? '\u{1F916}';
}

function getAgentName(agentId: string): string {
  const agent = AGENTS.find((a) => a.id === agentId);
  return agent?.name ?? agentId;
}

function getConsensoColor(consenso: number): string {
  if (consenso >= 0.8) return 'text-green-400';
  if (consenso >= 0.5) return 'text-yellow-400';
  return 'text-red-400';
}

function getConsensoBar(consenso: number): string {
  if (consenso >= 0.8) return 'bg-green-500';
  if (consenso >= 0.5) return 'bg-yellow-500';
  return 'bg-red-500';
}

const impactColors: Record<string, string> = {
  Crítico: 'text-red-400 bg-red-400/10',
  Alto: 'text-orange-400 bg-orange-400/10',
  Medio: 'text-yellow-400 bg-yellow-400/10',
  Bajo: 'text-slate-400 bg-slate-400/10',
};

export default function FinalReport({ report, onNewReview, onHistory }: FinalReportProps) {
  if (!report || report.findings.length === 0) {
    return null;
  }

  return (
    <section className="card p-4 mb-6" aria-label="Final report">
      <div className="flex items-center justify-between mb-4">
        <h2 className="card-header flex items-center gap-2">
          <span className="text-lg" role="img" aria-hidden="true">
            📋
          </span>
          Reporte Final
        </h2>

        <div className="flex items-center gap-2 text-xs text-slate-500">
          <span>{report.participants.length} agentes</span>
          <span className="text-slate-700">·</span>
          <span>{report.rounds} rondas</span>
        </div>
      </div>

      {/* Summary */}
      <div className="bg-slate-700/30 border border-slate-700 rounded-lg p-4 mb-6">
        <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-2">
          Resumen Ejecutivo
        </h3>
        <p className="text-slate-200 text-sm leading-relaxed whitespace-pre-wrap">
          {report.summary}
        </p>
      </div>

      {/* Findings table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-700">
              <th className="text-left py-3 px-2 text-slate-400 font-semibold text-xs uppercase tracking-wider">
                #
              </th>
              <th className="text-left py-3 px-2 text-slate-400 font-semibold text-xs uppercase tracking-wider">
                Hallazgo
              </th>
              <th className="text-left py-3 px-2 text-slate-400 font-semibold text-xs uppercase tracking-wider hidden md:table-cell">
                Impacto
              </th>
              <th className="text-left py-3 px-2 text-slate-400 font-semibold text-xs uppercase tracking-wider hidden lg:table-cell">
                Votos
              </th>
              <th className="text-left py-3 px-2 text-slate-400 font-semibold text-xs uppercase tracking-wider">
                Consenso
              </th>
            </tr>
          </thead>
          <tbody>
            {report.findings.map((finding, idx) => {
              const voters = Object.entries(finding.votes);
              return (
                <tr
                  key={idx}
                  className="border-b border-slate-700/50 hover:bg-slate-700/20 transition-colors"
                >
                  <td className="py-3 px-2 text-slate-500 font-mono">{idx + 1}</td>
                  <td className="py-3 px-2">
                    <p className="text-white font-medium text-sm">{finding.hallazgo}</p>
                    <p className="text-slate-400 text-xs mt-0.5 line-clamp-2">
                      {finding.detalle}
                    </p>
                  </td>
                  <td className="py-3 px-2 hidden md:table-cell">
                    <span
                      className={`inline-block text-xs font-semibold px-2 py-0.5 rounded ${
                        impactColors[finding.impacto] ?? 'text-slate-400 bg-slate-400/10'
                      }`}
                    >
                      {finding.impacto}
                    </span>
                  </td>
                  <td className="py-3 px-2 hidden lg:table-cell">
                    <div className="flex flex-wrap gap-1.5">
                      {voters.map(([agentId, vote]) => (
                        <span
                          key={agentId}
                          className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded bg-slate-700/50"
                          title={`${getAgentName(agentId)}: ${vote}`}
                        >
                          <span style={{ color: getAgentColor(agentId) }}>
                            {getAgentIcon(agentId)}
                          </span>
                          <span className="text-slate-300">{vote}</span>
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="py-3 px-2">
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-500 ${getConsensoBar(finding.consensus_score)}`}
                          style={{ width: `${Math.round(finding.consensus_score * 100)}%` }}
                        />
                      </div>
                      <span className={`text-xs font-semibold ${getConsensoColor(finding.consensus_score)}`}>
                        {Math.round(finding.consensus_score * 100)}%
                      </span>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Actions */}
      <div className="flex flex-wrap items-center gap-3 mt-6 pt-4 border-t border-slate-700">
        <button
          onClick={onNewReview}
          className="btn-primary flex items-center gap-2"
          aria-label="Iniciar nueva revisión"
        >
          <span className="text-lg" role="img" aria-hidden="true">
            🔄
          </span>
          Nuevo Review
        </button>

        {onHistory && (
          <button
            onClick={onHistory}
            className="btn-secondary flex items-center gap-2"
            aria-label="Ver historial de revisiones"
          >
            <span className="text-lg" role="img" aria-hidden="true">
              📜
            </span>
            Ver historial
          </button>
        )}
      </div>
    </section>
  );
}
