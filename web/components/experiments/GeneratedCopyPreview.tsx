import type { LoopGeneratedVariantCandidate } from "../../lib/types";

type GeneratedCopyPreviewProps = {
  candidates: LoopGeneratedVariantCandidate[];
  selectedIndex: number;
  onSelect: (index: number) => void;
  radioName: string;
};

export function GeneratedCopyPreview({
  candidates,
  selectedIndex,
  onSelect,
  radioName,
}: GeneratedCopyPreviewProps) {
  if (!candidates.length) return null;

  return (
    <div className="panel__card">
      <div className="panel__header">
        <h4>Generated copy preview</h4>
        <span className="panel__badge panel__badge--secondary">{candidates.length}</span>
      </div>
      <ul className="panel__list">
        {candidates.map((candidate, index) => (
          <li key={`${candidate.label}-${index}`}>
            <div className="panel__meta">
              <label className="panel__toggle">
                <input
                  type="radio"
                  name={radioName}
                  checked={selectedIndex === index}
                  onChange={() => onSelect(index)}
                />
                <span>
                  {index + 1}. {candidate.label}
                </span>
              </label>
              <span className="panel__badge panel__badge--secondary">
                conf {candidate.confidence.toFixed(2)}
              </span>
            </div>
            <pre className="panel__pre">{candidate.description}</pre>
            {candidate.rationale ? <p className="panel__muted">{candidate.rationale}</p> : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
