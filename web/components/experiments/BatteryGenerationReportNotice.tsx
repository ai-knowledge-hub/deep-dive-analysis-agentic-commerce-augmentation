export type BatteryGenerationReport = {
  accepted_count: number;
  rejected_count: number;
  generated_count?: number;
  generated_preview?: { query_text: string; query_type?: string | null }[];
  required_category?: string | null;
  category_confidence?: number | null;
  category_candidates?: { category: string; score: number }[];
  clarification_required?: boolean;
  clarification_prompt?: string | null;
  regeneration_count?: number;
  acceptance_rate?: number;
  rejected?: { query_text: string; reason: string }[];
  audience_segments_generated?: number;
  audience_segment_labels?: string[];
  audience_segments_source?: "behavioral" | "canonical_fallback";
  audience_segments_fallback_reason?: string | null;
};

type BatteryGenerationReportNoticeProps = {
  report: BatteryGenerationReport;
  onOpenAdmin: () => void;
};

export function BatteryGenerationReportNotice({
  report,
  onOpenAdmin,
}: BatteryGenerationReportNoticeProps) {
  return (
    <div className="panel__notice panel__notice--info">
      {typeof report.generated_count === "number" ? (
        <>
          Generated: {report.generated_count} ·{" "}
        </>
      ) : null}
      Accepted: {report.accepted_count} · Rejected: {report.rejected_count}
      {typeof report.acceptance_rate === "number" ? (
        <>
          {" "}
          · Acceptance rate: {Math.round(report.acceptance_rate * 100)}%
        </>
      ) : null}
      {typeof report.regeneration_count === "number" ? (
        <> · Regenerations: {report.regeneration_count}</>
      ) : null}
      {typeof report.audience_segments_generated === "number" ? (
        <>
          {" "}
          · Audience segments: {report.audience_segments_generated}
        </>
      ) : null}
      {report.required_category ? (
        <>
          {" "}
          · Required category: {report.required_category}
        </>
      ) : null}
      {typeof report.category_confidence === "number" ? (
        <>
          {" "}
          · Category confidence: {Math.round(report.category_confidence * 100)}%
        </>
      ) : null}
      {report.clarification_required && report.clarification_prompt ? (
        <>
          <p className="panel__error">{report.clarification_prompt}</p>
          <button type="button" className="button button--ghost" onClick={onOpenAdmin}>
            Open Admin to set canonical spec
          </button>
        </>
      ) : null}
      {report.audience_segment_labels && report.audience_segment_labels.length > 0 ? (
        <>
          <p className="panel__muted">Behavioral segments applied</p>
          <ul className="panel__list">
            {report.audience_segment_labels.slice(0, 4).map((label) => (
              <li key={label}>{label}</li>
            ))}
          </ul>
        </>
      ) : null}
      {report.audience_segments_source === "canonical_fallback" &&
      report.audience_segments_fallback_reason ? (
        <p className="panel__muted">Fallback: {report.audience_segments_fallback_reason}</p>
      ) : null}
      {report.rejected && report.rejected.length > 0 ? (
        <ul className="panel__list">
          {report.rejected.slice(0, 5).map((item) => (
            <li key={`${item.query_text}-${item.reason}`}>
              <span className="panel__muted">{item.reason}:</span> {item.query_text}
            </li>
          ))}
        </ul>
      ) : null}
      {report.generated_preview && report.generated_preview.length > 0 ? (
        <>
          <p className="panel__muted">Pre-validation generated sample</p>
          <ul className="panel__list">
            {report.generated_preview.slice(0, 5).map((item, index) => (
              <li key={`${item.query_text}-${index}`}>{item.query_text}</li>
            ))}
          </ul>
        </>
      ) : null}
    </div>
  );
}
