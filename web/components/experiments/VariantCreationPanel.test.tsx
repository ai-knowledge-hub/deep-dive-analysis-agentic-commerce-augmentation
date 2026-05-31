import { fireEvent, render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";

import { VariantCreationPanel } from "./VariantCreationPanel";

const baseProps = {
  setVariantSourceMode: vi.fn(),
  setVariantSourceManualOverride: vi.fn(),
  recommendedVariantSourceReason: "Simulation revision is available.",
  variantSourceManualOverride: false,
  variantForm: {
    label: "Variant A",
    role: "candidate",
    description: "Candidate copy",
    type: "copy",
    payload: "{}",
  },
  setVariantForm: vi.fn(),
  selectedSimulationRevisionId: "revision-1",
  setSelectedSimulationRevisionId: vi.fn(),
  handleUseSimulationRevision: vi.fn(),
  simulationRevisionStatus: null,
  loopGeneratedVariants: [],
  selectedLoopCandidateIndex: 0,
  setSelectedLoopCandidateIndex: vi.fn(),
  handleGenerateLoopVariants: vi.fn(),
  handleUseGeneratedLoopVariant: vi.fn(),
  handleCreateVariantFromLoopCandidate: vi.fn(),
  loopGenerationStatus: null,
  loopEvidenceAdvisory: null,
  coldStartGenerationStrategy: "both" as const,
  setColdStartGenerationStrategy: vi.fn(),
  handleGenerateColdStartVariants: vi.fn(),
  variantSecondaryActionsOpen: false,
  setVariantSecondaryActionsOpen: vi.fn(),
  variantAdvancedOpen: false,
  setVariantAdvancedOpen: vi.fn(),
  jsonErrorVariantPayload: null,
  addVariantDisabledReason: null,
  handleCreateVariant: vi.fn(),
  labMode: "manual" as const,
  setLabShowManualControls: vi.fn(),
  isSubmitting: false,
  isGeneratingLoopVariant: false,
  variantGenerationRequestType: null,
  isCreatingVariant: false,
  isCreatingLoopCandidateVariant: false,
  canGenerateCandidates: true,
};

describe("VariantCreationPanel", () => {
  it("uses readable source and simulation revision labels", () => {
    render(
      <VariantCreationPanel
        {...baseProps}
        variantSourceMode="simulation"
        recommendedVariantSource="loop_evidence"
        simulationRevisions={[
          {
            id: "revision-1",
            updated_at: "2026-05-31T10:00:00Z",
            status: "ready_for_review",
          },
        ]}
      />,
    );

    expect(screen.getByText(/Recommended now:/i).textContent).toContain("Loop evidence");
    expect(
      screen.getByRole("option", { name: /Ready for review/i }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/loop_evidence/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/ready_for_review/i)).not.toBeInTheDocument();
  });

  it("uses test idea as the default candidate label after switching from control", () => {
    const setVariantForm = vi.fn((updater) =>
      updater({
        label: "Control (current copy)",
        role: "control",
        description: "",
        type: "copy",
        payload: "{}",
      }),
    );

    render(
      <VariantCreationPanel
        {...baseProps}
        variantSourceMode="manual"
        recommendedVariantSource="manual"
        simulationRevisions={[]}
        variantForm={{
          ...baseProps.variantForm,
          role: "control",
          label: "Control (current copy)",
        }}
        setVariantForm={setVariantForm}
      />,
    );

    fireEvent.change(screen.getByRole("combobox", { name: /Role/i }), {
      target: { value: "candidate" },
    });

    expect(setVariantForm.mock.results[0]?.value).toEqual(
      expect.objectContaining({ label: "Test idea variant" }),
    );
  });
});
