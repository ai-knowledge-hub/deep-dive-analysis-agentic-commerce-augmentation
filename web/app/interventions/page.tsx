"use client";

import React from "react";
import { ControlPlanePlaceholder } from "../../components/layout/ControlPlanePlaceholder";

export default function InterventionsPage() {
  return (
    <ControlPlanePlaceholder
      title="Interventions"
      subtitle="Focused queue for operator approvals, pauses, retries, and escalations."
      badge="Primary"
      summary="Interventions will separate decision-making from general timeline browsing so operators can act quickly without losing audit context."
      nextItems={[
        "Approve or reject queued actions",
        "Pause, cancel, or retry runs",
        "Downgrade autonomy profile",
        "Escalate to manual review with rationale",
      ]}
    />
  );
}
