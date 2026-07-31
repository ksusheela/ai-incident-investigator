/** Mirrors `backend/src/app/evaluation/models.py`. */

export interface QualityCheck {
  name: string;
  passed: boolean;
  detail: string;
}

export interface QualityScore {
  score: number;
  checks: QualityCheck[];
}

export interface EvaluationResult {
  incident_id: string;
  evaluated_at: string;
  response_time_seconds: number;
  confidence_score: number;
  root_cause_quality: QualityScore;
  recommendation_quality: QualityScore;
}

export interface EvaluationSummary {
  evaluated_count: number;
  avg_response_time_seconds: number | null;
  avg_confidence_score: number | null;
  avg_root_cause_quality: number | null;
  avg_recommendation_quality: number | null;
}
