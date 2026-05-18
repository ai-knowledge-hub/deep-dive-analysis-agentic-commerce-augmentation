"use client";

import React from "react";
import type { QueryBattery } from "../../lib/types";

type Props = {
  batteries: QueryBattery[];
  selectedBatteryId: string;
  isGenerating: boolean;
  disabledReason: string | null;
  onBatteryIdChange: (batteryId: string) => void;
  onGenerateQueries: (batteryId: string) => void;
};

export function QueryGenerationPanel({
  batteries,
  selectedBatteryId,
  isGenerating,
  disabledReason,
  onBatteryIdChange,
  onGenerateQueries,
}: Props) {
  return (
    <>
      <label className="panel__label">
        Generate for battery
        <select
          className="panel__input"
          value={selectedBatteryId}
          onChange={(event) => onBatteryIdChange(event.target.value)}
        >
          <option value="">Select battery</option>
          {batteries.map((battery) => (
            <option key={battery.id} value={battery.id}>
              {battery.name}
            </option>
          ))}
        </select>
      </label>
      <p className="panel__subheading">Step 2 · Generate queries</p>
      <button
        type="button"
        className="panel__action panel__action--prominent"
        onClick={() => onGenerateQueries(selectedBatteryId)}
        disabled={Boolean(disabledReason)}
      >
        {isGenerating ? (
          <>
            Generating queries<span className="button__dots" />
          </>
        ) : (
          "Generate queries"
        )}
      </button>
      {disabledReason ? <p className="panel__muted">{disabledReason}</p> : null}
    </>
  );
}
