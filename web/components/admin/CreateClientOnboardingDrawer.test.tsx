import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { describe, expect, it, vi } from "vitest";

import {
  CreateClientOnboardingDrawer,
  type CreateClientOnboardingForm,
} from "./CreateClientOnboardingDrawer";

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

const form: CreateClientOnboardingForm = {
  clientId: "",
  clientName: "",
  brandId: "",
  brandName: "",
  productsText: "",
  category: "running_shoes",
  subCategory: "",
  useCases: "daily_training",
  archetypes: "",
  featureConcepts: "",
  constraints: "",
  exclusions: "",
  objectiveKeywords: "",
  bannedKeywords: "",
  ucpOfferUrl: "",
  ucpMerchantName: "",
  ucpCurrency: "GBP",
  acpEnableSearch: true,
  acpEnableCheckout: true,
};

function renderDrawer(overrides: Partial<React.ComponentProps<typeof CreateClientOnboardingDrawer>> = {}) {
  return render(
    <CreateClientOnboardingDrawer
      isOpen
      isBusy={false}
      canSubmit={false}
      error={null}
      success={null}
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
      onSubmit={vi.fn()}
      {...overrides}
    />,
  );
}

describe("CreateClientOnboardingDrawer", () => {
  it("keeps submit disabled until the parent marks the form submittable", async () => {
    const onSubmit = vi.fn();
    renderDrawer({ canSubmit: false, onSubmit });

    const submit = screen.getByRole("button", { name: "Create client onboarding" });
    expect(submit).toBeDisabled();

    await userEvent.click(submit);
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("emits form patches and submit callbacks", async () => {
    const onFormChange = vi.fn();
    const onSubmit = vi.fn();
    renderDrawer({ canSubmit: true, onFormChange, onSubmit });

    await userEvent.type(screen.getByPlaceholderText("client-id"), "client-a");
    expect(onFormChange).toHaveBeenCalledWith({ clientId: "c" });

    const categorySelect = screen.getAllByRole("combobox")[0];
    await userEvent.selectOptions(categorySelect, "running_shoes");
    expect(onFormChange).toHaveBeenCalledWith({ category: "running_shoes", subCategory: "" });

    await userEvent.click(screen.getByRole("button", { name: "Create client onboarding" }));
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });
});
