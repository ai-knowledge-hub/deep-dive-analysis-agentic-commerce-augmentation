"use client";

import React from "react";
import { ControlPlanePlaceholder } from "../../components/layout/ControlPlanePlaceholder";

export default function LearningsPage() {
  return (
    <ControlPlanePlaceholder
      title="Learnings"
      subtitle="A compact view of what changed across evidence, calibration, and execution."
      badge="Primary"
      summary="Learnings will absorb the most useful cross-cutting insights from overview, alignment, and evidence pages into one operator-friendly review surface."
      nextItems={[
        "Belief and calibration changes",
        "Validation accuracy deltas",
        "Protocol readiness changes",
        "Skill and harness performance trends",
      ]}
    />
  );
}
