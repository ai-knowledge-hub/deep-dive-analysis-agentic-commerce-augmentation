import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { describe, expect, it, vi } from "vitest";

import {
  CanonicalIntentSpecDrawer,
  type CanonicalIntentSpecForm,
} from "./CanonicalIntentSpecDrawer";

const ontology = {
  running_shoes: {
    label: "Running shoes",
    subCategories: ["daily_trainer"],
    useCases: ["daily_training", "speed_work"],
    archetypes: ["beginner_runner"],
    featureConcepts: ["cushioning"],
    constraints: ["budget_sensitive"],
    exclusions: ["elite_racer_only"],
  },
};

const form: CanonicalIntentSpecForm = {
  category: "running_shoes",
  subCategory: "",
  useCases: "daily_training",
  archetypes: "",
  featureConcepts: "",
  constraints: "",
  exclusions: "",
  objectiveKeywords: "",
  bannedKeywords: "",
};

function renderDrawer(overrides: Partial<React.ComponentProps<typeof CanonicalIntentSpecDrawer>> = {}) {
  return render(
    <CanonicalIntentSpecDrawer
      isOpen
      canAutofill
      canSave
      form={form}
      currentClientName="Acme"
      currentBrandName="Acme Sports"
      currentProductName="Runner Pro"
      canonicalOntology={ontology}
      selectedOntology={ontology.running_shoes}
      useCases={ontology.running_shoes.useCases}
      archetypes={ontology.running_shoes.archetypes}
      featureConcepts={ontology.running_shoes.featureConcepts}
      constraints={ontology.running_shoes.constraints}
      exclusions={ontology.running_shoes.exclusions}
      onClose={vi.fn()}
      onFormChange={vi.fn()}
      onAutofill={vi.fn()}
      onSave={vi.fn()}
      {...overrides}
    />,
  );
}

describe("CanonicalIntentSpecDrawer", () => {
  it("routes autofill and save actions to parent handlers", async () => {
    const onAutofill = vi.fn();
    const onSave = vi.fn();
    renderDrawer({ onAutofill, onSave });

    await userEvent.click(screen.getByRole("button", { name: "Preview UCP/ACP autofill" }));
    await userEvent.click(screen.getByRole("button", { name: "Apply autofill" }));
    await userEvent.click(screen.getByRole("button", { name: "Save intent spec" }));

    expect(onAutofill).toHaveBeenNthCalledWith(1, "preview");
    expect(onAutofill).toHaveBeenNthCalledWith(2, "apply");
    expect(onSave).toHaveBeenCalledTimes(1);
  });

  it("emits ontology field patches", async () => {
    const onFormChange = vi.fn();
    renderDrawer({ onFormChange });

    const subCategorySelect = screen.getAllByRole("combobox")[1];
    const useCasesSelect = screen.getAllByRole("listbox")[0];

    await userEvent.selectOptions(subCategorySelect, "daily_trainer");
    await userEvent.selectOptions(useCasesSelect, "speed_work");

    expect(onFormChange).toHaveBeenCalledWith({ subCategory: "daily_trainer" });
    expect(onFormChange).toHaveBeenCalledWith({ useCases: "daily_training, speed_work" });
  });
});
