export interface PerAppResult {
  name: string;
  single: number;
  multi: number;
}

export interface CategoryItem {
  name: string;
  single: boolean;
  multi: boolean;
}

export interface BenchmarkDataSet {
  totalFindings: { single: number; multi: number };
  precision: { single: number; multi: number };
  recall: { single: number; multi: number };
  f1Score: { single: number; multi: number };
  categoriesCovered: { single: number; multi: number; total: number };
  avgSeverity: { single: number; multi: number };
  executionTime: { single: number; multi: number };
  cost: { single: number; multi: number };
  perApp: PerAppResult[];
  overlap: { overlapping: number; singleTotal: number; singleUnique: number; multiUnique: number };
  severityDistribution: Record<string, { single: number; multi: number }>;
  categoryCoverage: CategoryItem[];
  falsePositivesPer100: { single: number; multi: number };
}

export const BENCHMARK_DATA: BenchmarkDataSet = {
  totalFindings: { single: 14, multi: 33 },
  precision: { single: 54.2, multi: 41.0 },
  recall: { single: 92.9, multi: 66.1 },
  f1Score: { single: 69.6, multi: 52.2 },
  categoriesCovered: { single: 4, multi: 6, total: 6 },
  avgSeverity: { single: 3.0, multi: 3.2 },
  executionTime: { single: 8.2, multi: 32.5 },
  cost: { single: 0.004, multi: 0.028 },
  perApp: [
    { name: 'vulnerable_app.py', single: 8, multi: 18 },
    { name: 'flask_app.py', single: 6, multi: 15 },
    { name: 'api_service.py', single: 4, multi: 8 },
  ],
  overlap: {
    overlapping: 12,
    singleTotal: 14,
    singleUnique: 2,
    multiUnique: 19,
  },
  severityDistribution: {
    Critical: { single: 3, multi: 8 },
    High: { single: 4, multi: 7 },
    Medium: { single: 3, multi: 5 },
    Low: { single: 1, multi: 1 },
  },
  categoryCoverage: [
    { name: 'Security', single: true, multi: true },
    { name: 'Architecture', single: false, multi: true },
    { name: 'Quality', single: true, multi: true },
    { name: 'Performance', single: true, multi: true },
    { name: 'UX', single: false, multi: true },
    { name: 'Visual', single: false, multi: true },
  ],
  falsePositivesPer100: { single: 1.04, multi: 2.64 },
};
