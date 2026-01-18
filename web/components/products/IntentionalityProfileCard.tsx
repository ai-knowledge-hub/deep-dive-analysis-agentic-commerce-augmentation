import type { Product } from "../../lib/types";

type Props = {
  product?: Product;
  alignmentScore?: number;
  baselineScore?: number;
};

export function IntentionalityProfileCard({
  product,
  alignmentScore,
  baselineScore,
}: Props) {
  if (!product?.intentionality_profile) return null;
  const profile = product.intentionality_profile;
  const baseline =
    baselineScore !== undefined ? Math.max(0, Math.min(1, baselineScore)) : undefined;
  const current =
    alignmentScore !== undefined ? Math.max(0, Math.min(1, alignmentScore)) : undefined;
  const delta =
    baseline !== undefined && current !== undefined ? current - baseline : undefined;
  return (
    <div className="profile-card">
      <div className="profile-card__title">Intentionality Profile</div>
      {alignmentScore !== undefined ? (
        <div className="profile-card__score">
          <span className="profile-card__label">Alignment</span>
          <span className="profile-card__value">
            {(alignmentScore * 100).toFixed(0)}%
          </span>
        </div>
      ) : null}
      {baseline !== undefined && current !== undefined ? (
        <div className="profile-card__delta">
          <span className="profile-card__label">Discoverability Delta</span>
          <div className="profile-card__legend">
            <span>Baseline</span>
            <span>Optimized</span>
          </div>
          <div className="profile-card__delta-row">
            <div className="profile-card__bar">
              <span style={{ width: `${Math.round(baseline * 100)}%` }} />
            </div>
            <div className="profile-card__bar profile-card__bar--current">
              <span style={{ width: `${Math.round(current * 100)}%` }} />
            </div>
          </div>
          <span className="profile-card__value profile-card__delta-value">
            {delta >= 0 ? "+" : ""}
            {(delta * 100).toFixed(0)}%
          </span>
        </div>
      ) : null}
      <div className="profile-card__section">
        <span className="profile-card__label">Capabilities</span>
        <span className="profile-card__value">
          {profile.capabilities_enabled?.join(", ") || "Not captured"}
        </span>
      </div>
      <div className="profile-card__section">
        <span className="profile-card__label">Goals Served</span>
        <span className="profile-card__value">
          {profile.goals_served?.join(", ") || "Not captured"}
        </span>
      </div>
      {profile.outcomes_expected?.length ? (
        <div className="profile-card__section">
          <span className="profile-card__label">Outcomes</span>
          <span className="profile-card__value">
            {profile.outcomes_expected.join(", ")}
          </span>
        </div>
      ) : null}
    </div>
  );
}
