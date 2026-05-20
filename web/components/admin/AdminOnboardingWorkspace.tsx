"use client";

import React, { type ReactNode } from "react";
import type { AdminBrand, AdminClient, AdminProduct } from "../../lib/types";
import {
  OnboardingFlowStatus,
  type OnboardingNextAction,
  type OnboardingStep,
} from "./OnboardingFlowStatus";
import { ScopeSelectors } from "./ScopeSelectors";

type OnboardingCompletion = {
  completed: number;
  total: number;
};

type Props = {
  completion: OnboardingCompletion;
  currentStep: number;
  flowSteps: OnboardingStep[];
  nextAction: OnboardingNextAction;
  activeClientId: string;
  activeBrandId: string;
  activeProductId: string;
  clients: AdminClient[];
  brands: AdminBrand[];
  products: AdminProduct[];
  onRunNextAction: () => void;
  onClientChange: (nextClientId: string) => void;
  onBrandChange: (nextBrandId: string) => void;
  onProductChange: (nextProductId: string) => void;
  onAddClient: () => void;
  children: ReactNode;
};

export function AdminOnboardingWorkspace({
  completion,
  currentStep,
  flowSteps,
  nextAction,
  activeClientId,
  activeBrandId,
  activeProductId,
  clients,
  brands,
  products,
  onRunNextAction,
  onClientChange,
  onBrandChange,
  onProductChange,
  onAddClient,
  children,
}: Props) {
  return (
    <section className="panel__card admin-onboarding">
      <div className="panel__header">
        <h3>Client onboarding workspace</h3>
        <span className="panel__meta">
          {completion.completed}/{completion.total} complete
        </span>
      </div>
      <p className="panel__subheading">Setup flow</p>
      <p className="panel__step-helper">
        Complete onboarding in sequence, then move to operational controls.
      </p>
      <OnboardingFlowStatus
        currentStep={currentStep}
        steps={flowSteps}
        nextAction={nextAction}
        onRunNextAction={onRunNextAction}
      />
      <ScopeSelectors
        activeClientId={activeClientId}
        activeBrandId={activeBrandId}
        activeProductId={activeProductId}
        clients={clients}
        brands={brands}
        products={products}
        onClientChange={onClientChange}
        onBrandChange={onBrandChange}
        onProductChange={onProductChange}
      />
      <p className="panel__meta">All onboarding changes are saved against the selected scope above.</p>
      <div className="panel__actions">
        <button type="button" className="button button--primary-subtle" onClick={onAddClient}>
          Add new client
        </button>
      </div>
      <div className="admin-onboarding__panels">{children}</div>
    </section>
  );
}
