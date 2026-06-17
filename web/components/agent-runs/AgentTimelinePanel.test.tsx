import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";

import { AgentTimelinePanel } from "./AgentTimelinePanel";

const noop = vi.fn();

describe("AgentTimelinePanel", () => {
  it("keeps presets primary and moves custom filters plus technical event detail behind disclosures", () => {
    render(
      <AgentTimelinePanel
        events={[
          {
            id: "event-1",
            actionId: "action-1",
            sequence: 1,
            capability: "run variant",
            status: "executed",
            note: "Variant completed.",
            toolId: "experiment.run_variant",
            skillId: "optimize-product-representation",
            effectClass: "write_low_risk",
          },
        ]}
        actionCount={1}
        livePollingActive
        loadingOlderEvents={false}
        loading={false}
        selectedEventId={null}
        timelinePreset="all_activity"
        timelineFilter="all"
        timelineStatusFilter="all"
        timelineCapabilityFilter="all"
        timelineCapabilityOptions={["all", "run_variant"]}
        timelineTimeWindow="24h"
        onLoadOlderEvents={noop}
        onApplyTimelinePreset={noop}
        onTimelineFilterChange={noop}
        onTimelineStatusFilterChange={noop}
        onTimelineCapabilityFilterChange={noop}
        onTimelineTimeWindowChange={noop}
        onSelectEvent={noop}
        onFocusAction={noop}
        canOpenExperiment={() => false}
        onOpenExperiment={noop}
        canOpenValidation={() => false}
        onOpenValidation={noop}
        onCopyEventLink={noop}
      />,
    );

    expect(screen.getByRole("button", { name: /All activity/i })).toBeInTheDocument();
    expect(screen.getByText(/More timeline filters/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Timeline action filter/i)).toBeInTheDocument();
    expect(screen.getByText(/All actions/i)).toBeInTheDocument();
    expect(screen.getByText(/Technical event detail/i)).toBeInTheDocument();
    expect(screen.getByText(/run variant/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/Timeline capability filter/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/All capabilities/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/^experiment\.run_variant$/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/^optimize-product-representation$/i)).not.toBeInTheDocument();
  });
});
