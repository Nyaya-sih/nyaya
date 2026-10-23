export interface SimilarityDimension {
  name: string;
  score: number;
  reason: string;
}

export interface SearchResult {
  rank: number;
  case_id: number;
  case_title: string;
  court: string;
  date_of_judgment: string;
  case_type: string;
  verdict: string;
  combined_score: number;
  similarity_explanation: string;
  common_statutes: string[];
  statutes_cited: string[];
  sections_invoked: string[];
  dimensions: SimilarityDimension[];
}

export interface SearchResponse {
  query_summary: string;
  total_results: number;
  search_time_ms: number;
  results: SearchResult[];
  filters_applied: Record<string, string | number | null>;
  disclaimer: string;
  retrieval_mode: "full" | "degraded" | "rejected";
  warnings: string[];
}

export interface CaseDetail {
  case_id: number;
  case_title: string;
  court: string;
  date_of_judgment: string | null;
  case_type: string;
  verdict: string;
  statutes_cited: string[];
  sections_invoked: string[];
  charges: string[];
  key_arguments_petitioner: string | null;
  key_arguments_respondent: string | null;
  court_reasoning: string | null;
  precedents_cited: {
    case_name: string;
    citation: string | null;
    year: number | null;
    court: string | null;
    legal_principle: string | null;
  }[];
  headnotes: string[];
  full_text: string;
  average_confidence: number;
  validation_status: string;
}

export interface SearchFilters {
  courts: string[];
  case_types: string[];
  verdicts: string[];
  similarity_modes: Array<"combined" | "factual" | "legal" | "fulltext">;
  year_range: { min: number | null; max: number | null };
}

export interface SearchParams {
  text?: string;
  court?: string;
  case_type?: string;
  year_from?: number;
  year_to?: number;
  verdict?: string;
  top_k?: number;
  similarity_mode?: "combined" | "factual" | "legal" | "fulltext";
}

export interface AssistantSessionResponse {
  session_id: string;
  created_at: string;
  expires_at: string;
  ttl_minutes: number;
}

export interface AssistantCitation {
  citation_id: string;
  source_type: "case" | "statute" | "constitution" | "document" | "other";
  title: string;
  act_or_case: string;
  section_or_article: string | null;
  excerpt: string;
  score: number;
}

export interface AssistantConfidence {
  overall: number;
  retrieval_support: number;
  citation_coverage: number;
  risk_flags: string[];
}

export interface AssistantQueryResponse {
  session_id: string;
  answer_text: string;
  citations: AssistantCitation[];
  confidence: AssistantConfidence;
  disclaimer: string;
  warnings: string[];
  retrieval_mode: "placeholder" | "retrieval" | "degraded";
  created_at: string;
}

export interface AssistantQueryRequest {
  session_id: string;
  question: string;
  top_k?: number;
  include_history?: boolean;
}

export interface AssistantDeleteResponse {
  session_id: string;
  deleted: boolean;
}

export type CourtroomMode = "quick" | "full";
export type CourtroomStatus =
  | "queued"
  | "running"
  | "completed"
  | "degraded"
  | "failed"
  | "cancelled";

export interface CourtroomAnalyzeRequest {
  mode: CourtroomMode;
  include_rebuttal?: boolean;
  source_type: "text" | "case_id";
  case_text?: string;
  case_id?: number;
  top_k_legal?: number;
  top_k_cases?: number;
  role_model_overrides?: Record<string, Array<{ provider: string; model: string }>>;
  max_cost_usd?: number;
}

export interface CourtroomCreateResponse {
  analysis_id: string;
  status: CourtroomStatus;
  mode: CourtroomMode;
  created_at: string;
  eta_seconds: number;
  warnings: string[];
}

export interface CourtroomRoleAnalysis {
  role_name: string;
  analysis_text: string;
  citations: string[];
  confidence: number;
  provider?: string | null;
  model?: string | null;
  degraded: boolean;
  public_explanation?: CourtroomPublicExplanation | null;
  source_evidence?: Array<Record<string, string>>;
}

export interface CourtroomPublicExplanation {
  conclusion_basis: string;
  supporting_evidence: Array<{
    source_ref: string;
    quote: string;
    relevance: string;
    quote_verified: boolean;
  }>;
  assumptions: string[];
  counterarguments: string[];
  uncertainty: string[];
  change_summary: string | null;
}

export interface CourtroomDocument {
  text: string;
  filename: string;
  page_count: number | null;
  extracted_characters: number;
  truncated: boolean;
  warnings: string[];
}

export interface CourtroomCitation {
  doc_id: string;
  section_ref: string;
  quoted_text: string | null;
}

export interface CourtroomTrialEvent {
  event_id: string;
  session_id: string;
  stage: "ingestion" | "group_deliberation" | "rebuttal" | "judicial" | "verdict";
  role: string;
  agent_id: string;
  model_provider: string;
  model_id: string;
  round: number;
  event_type: "frame" | "position" | "revision" | "objection" | "rebuttal" | "synthesis" | "vote" | "verdict";
  content: string;
  responding_to: string | null;
  citations: CourtroomCitation[];
  confidence: number;
  timestamp: string;
  public_explanation?: CourtroomPublicExplanation | null;
}

export interface CourtroomCriteriaScores {
  legal_accuracy: number;
  constitutional_alignment: number;
  logical_coherence: number;
  precedent_usage: number;
  fairness_balance: number;
  practical_applicability: number;
}

export interface CourtroomEvaluationItem {
  evaluator_role: string;
  target_role: string;
  criteria_scores: CourtroomCriteriaScores;
  weighted_score: number;
  justification: string;
}

export interface CourtroomSynthesis {
  executive_summary: string;
  recommended_outcome: string;
  confidence: number;
  consensus_points: string[];
  disagreement_points: string[];
  unresolved_issues: string[];
  legal_principles_applied: string[];
}

export interface CourtroomTransparency {
  consensus_meter: number;
  disagreement_index: number;
  estimated_cost_usd: number;
  total_runtime_ms: number;
  estimated_token_usage: number;
  score_matrix: Record<string, Record<string, number>>;
  criteria_averages: Record<string, number>;
  evaluator_summary: Record<string, Record<string, number>>;
}

export interface CourtroomAnalysisResponse {
  analysis_id: string;
  status: CourtroomStatus;
  mode: CourtroomMode;
  created_at: string;
  completed_at: string | null;
  role_analyses: CourtroomRoleAnalysis[];
  evaluation_breakdown: CourtroomEvaluationItem[];
  rebuttal_enabled: boolean;
  rebuttal_changes: string[];
  initial_role_analyses: CourtroomRoleAnalysis[];
  judge_review?: {
    approved: boolean;
    reasoning: string;
    required_changes: string[];
    confidence: number;
    degraded?: boolean;
    provider: string;
    model: string;
    public_explanation?: CourtroomPublicExplanation | null;
  } | null;
  synthesis: CourtroomSynthesis | null;
  transparency_dashboard: CourtroomTransparency | null;
  trial_events: CourtroomTrialEvent[];
  disclaimer: string;
  warnings: string[];
}

export interface CourtroomStatusResponse {
  analysis_id: string;
  status: CourtroomStatus;
  stage: string;
  progress_percent: number;
  updated_at: string;
  warnings: string[];
}

export interface CourtroomCancelResponse {
  analysis_id: string;
  cancelled: boolean;
  status: CourtroomStatus;
}

export interface TendencyRequest {
  mode?: "baseline" | "ml";
  source_type: "text" | "case_id";
  case_text?: string;
  case_id?: number;
  top_k_similar?: number;
  year_from?: number;
  year_to?: number;
}

export interface TendencyOutcomeBucket {
  label: string;
  count: number;
  percentage: number;
}

export interface TendencySentenceDistribution {
  average_years: number;
  median_years: number;
  min_years: number;
  max_years: number;
}

export interface TendencyTrendPoint {
  year: number;
  dominant_outcome: string;
  dominant_percentage: number;
}

export interface TendencyKeyFactor {
  name: string;
  influence_percent: number;
}

export interface TendencyExplainabilitySignal {
  factor: string;
  influence_percent: number;
  evidence_note: string;
}

export interface TendencyConfidenceBand {
  level: string;
  lower_bound: number;
  upper_bound: number;
  method: string;
  reliability_score: number;
}

export interface TendencyBiasSliceMetric {
  slice_name: string;
  dominant_outcome: string;
  dominant_rate_percent: number;
  sample_size: number;
}

export interface TendencyBiasAudit {
  disparity_flag: boolean;
  drift_flag: boolean;
  max_slice_gap_percent: number;
  slice_metrics: TendencyBiasSliceMetric[];
  notes: string[];
}

export interface TendencyResponse {
  analysis_id: string;
  status: "completed" | "insufficient_data";
  created_at: string;
  summary_text: string;
  sample_size: number;
  outcome_distribution: TendencyOutcomeBucket[];
  sentence_distribution: TendencySentenceDistribution | null;
  trend_analysis: TendencyTrendPoint[];
  key_factors: TendencyKeyFactor[];
  explainability_signals: TendencyExplainabilitySignal[];
  confidence_band: TendencyConfidenceBand;
  confidence_notes: string[];
  bias_audit: TendencyBiasAudit;
  cohort_filters: Record<string, string | number | null>;
  limitations: string[];
  disclaimer: string;
  warnings: string[];
}
