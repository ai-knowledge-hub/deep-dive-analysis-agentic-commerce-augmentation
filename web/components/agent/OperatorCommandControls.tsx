import React from "react";
import type {
  AgentAction,
  AgentRun,
  AgentRunCommandType,
  AgentRuntimeRecoveryTemplate,
  AgentRuntimeSkillSpec,
} from "../../lib/types";
import { formatOperatorActionName } from "../../lib/operatorDisplayLanguage";

type Props = {
  run: AgentRun | null;
  selectedAction: AgentAction | null;
  recoveryCapabilities: string[];
  activeRecoveryCapability: string;
  recoverySkillOptions: AgentRuntimeSkillSpec[];
  activeRecoverySkill: string;
  activeRecoveryTemplate: AgentRuntimeRecoveryTemplate | null;
  recoverySkillMetadata: Record<string, unknown>;
  onRecoveryCapabilityChange: (capabilityName: string) => void;
  onRecoverySkillChange: (skillId: string) => void;
  onIssueCommand: (
    commandType: AgentRunCommandType,
    message: string,
    actionId?: string | null,
    metadata?: Record<string, unknown>,
  ) => void | Promise<void>;
};

function recoveryCapabilityLabel(capabilityName: string): string {
  return formatOperatorActionName(capabilityName);
}

export function OperatorCommandControls({
  run,
  selectedAction,
  recoveryCapabilities,
  activeRecoveryCapability,
  recoverySkillOptions,
  activeRecoverySkill,
  activeRecoveryTemplate,
  recoverySkillMetadata,
  onRecoveryCapabilityChange,
  onRecoverySkillChange,
  onIssueCommand,
}: Props) {
  const selectedActionLabel = formatOperatorActionName(selectedAction?.capability_name);

  return (
    <div className="panel__actions">
      <button
        type="button"
        className="button button--primary button--sm"
        onClick={() =>
          void onIssueCommand(
            "approve",
            `Approve ${selectedActionLabel}`,
            selectedAction?.id,
          )
        }
        disabled={!run || !selectedAction || selectedAction.status !== "proposed"}
      >
        Approve selected
      </button>
      <button
        type="button"
        className="button button--ghost button--sm"
        onClick={() =>
          void onIssueCommand(
            "reject",
            `Reject ${selectedActionLabel}`,
            selectedAction?.id,
          )
        }
        disabled={!run || !selectedAction || selectedAction.status !== "proposed"}
      >
        Reject selected
      </button>
      <button
        type="button"
        className="button button--ghost button--sm"
        onClick={() =>
          void onIssueCommand(
            "retry",
            `Retry ${selectedActionLabel}`,
            selectedAction?.id,
            { retry_strategy: "same_action" },
          )
        }
        disabled={!run || !selectedAction || selectedAction.status !== "failed"}
      >
        Retry selected
      </button>
      <button
        type="button"
        className="button button--ghost button--sm"
        onClick={() =>
          void onIssueCommand(
            "retry",
            `Retry ${selectedActionLabel} from checkpoint`,
            selectedAction?.id,
            { retry_strategy: "last_safe_checkpoint" },
          )
        }
        disabled={!run || !selectedAction || selectedAction.status !== "failed"}
      >
        Retry checkpoint
      </button>
      <button
        type="button"
        className="button button--ghost button--sm"
        onClick={() =>
          void onIssueCommand(
            "retry",
            `Create recovery action for ${selectedActionLabel}`,
            selectedAction?.id,
            {
              retry_strategy: "create_recovery_action",
              capability_name: activeRecoveryCapability || undefined,
              ...recoverySkillMetadata,
            },
          )
        }
        disabled={
          !run ||
          !selectedAction ||
          selectedAction.status !== "failed" ||
          recoveryCapabilities.length === 0
        }
      >
        Recovery action
      </button>
      <button
        type="button"
        className="button button--ghost button--sm"
        onClick={() =>
          void onIssueCommand(
            "change_plan",
            "Create a recovery plan proposal",
            selectedAction?.id,
            {
              recovery_strategy: "propose_next_action",
              capability_name: activeRecoveryCapability || undefined,
              ...recoverySkillMetadata,
              inputs: run?.experiment_id ? { experiment_id: run.experiment_id } : {},
            },
          )
        }
        disabled={!run || recoveryCapabilities.length === 0}
      >
        Change plan
      </button>
      <label className="field">
        <span className="field__label">Recovery target</span>
        <select
          aria-label="Recovery target capability"
          className="field__input"
          value={activeRecoveryCapability}
          onChange={(event) => onRecoveryCapabilityChange(event.target.value)}
          disabled={!run || recoveryCapabilities.length === 0}
        >
          {recoveryCapabilities.length === 0 ? (
            <option value="">No allowed capabilities</option>
          ) : (
            recoveryCapabilities.map((capability) => (
              <option key={capability} value={capability}>
                {recoveryCapabilityLabel(capability)}
              </option>
            ))
          )}
        </select>
      </label>
      <label className="field">
        <span className="field__label">Preferred skill</span>
        <select
          aria-label="Preferred recovery skill"
          className="field__input"
          value={activeRecoverySkill}
          onChange={(event) => onRecoverySkillChange(event.target.value)}
          disabled={!run || recoverySkillOptions.length === 0}
        >
          {recoverySkillOptions.length === 0 ? (
            <option value="">Default skill</option>
          ) : (
            recoverySkillOptions.map((skill) => (
              <option key={skill.id} value={skill.id}>
                {skill.name}
              </option>
            ))
          )}
        </select>
      </label>
      {activeRecoveryTemplate ? (
        <div className="panel__notice panel__notice--info">
          <strong>Recovery template: {activeRecoveryTemplate.id}</strong>
          <p>{activeRecoveryTemplate.summary}</p>
          {Object.keys(activeRecoveryTemplate.default_inputs ?? {}).length > 0 ? (
            <p className="panel__muted">
              Defaults: {JSON.stringify(activeRecoveryTemplate.default_inputs)}
            </p>
          ) : null}
          {activeRecoveryTemplate.operator_notes?.length ? (
            <ul className="panel__list panel__list--compact">
              {activeRecoveryTemplate.operator_notes.slice(0, 2).map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
      <button
        type="button"
        className="button button--ghost button--sm"
        onClick={() => void onIssueCommand("pause", "Pause this run")}
        disabled={!run}
      >
        Pause run
      </button>
      <button
        type="button"
        className="button button--ghost button--sm"
        onClick={() => void onIssueCommand("start", "Start or resume this run")}
        disabled={!run}
      >
        Start run
      </button>
      <button
        type="button"
        className="button button--ghost button--sm"
        onClick={() => void onIssueCommand("step", "Step this run")}
        disabled={!run}
      >
        Step run
      </button>
      <button
        type="button"
        className="button button--ghost button--sm"
        onClick={() => void onIssueCommand("cancel", "Cancel this run")}
        disabled={!run}
      >
        Cancel run
      </button>
    </div>
  );
}
