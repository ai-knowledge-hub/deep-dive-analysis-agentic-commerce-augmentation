"use client";

import React from "react";
import type { AdminSkill } from "../../lib/types";

type SkillHistoryItem = {
  id: number;
  version?: string;
  changed_at?: string;
};

type Props = {
  userId?: string | null;
  skillNames: string[];
  activeSkillName: string;
  activeSkill: AdminSkill | null;
  skillDescription: string;
  skillVersion: string;
  skillContent: string;
  skillEnabled: boolean;
  skillHistory: SkillHistoryItem[];
  skillError: string | null;
  skillSaved: boolean;
  onActiveSkillNameChange: (value: string) => void;
  onSkillDescriptionChange: (value: string) => void;
  onSkillVersionChange: (value: string) => void;
  onSkillContentChange: (value: string) => void;
  onSkillEnabledChange: (value: boolean) => void;
  onSaveSkill: () => void;
};

export function AgentSkillsPanel({
  userId,
  skillNames,
  activeSkillName,
  activeSkill,
  skillDescription,
  skillVersion,
  skillContent,
  skillEnabled,
  skillHistory,
  skillError,
  skillSaved,
  onActiveSkillNameChange,
  onSkillDescriptionChange,
  onSkillVersionChange,
  onSkillContentChange,
  onSkillEnabledChange,
  onSaveSkill,
}: Props) {
  return (
    <details className="admin-ops__details">
      <summary>Agent skills</summary>
      {!userId ? (
        <p className="panel__empty">Sign in to edit skills.</p>
      ) : (
        <div className="admin__form">
          <span className="panel__label">Skill</span>
          <select
            value={activeSkillName}
            onChange={(event) => onActiveSkillNameChange(event.target.value)}
          >
            {skillNames.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
          {activeSkill?.updated_at ? (
            <p className="panel__meta">Updated: {activeSkill.updated_at}</p>
          ) : null}
          <input
            type="text"
            placeholder="Description"
            value={skillDescription}
            onChange={(event) => onSkillDescriptionChange(event.target.value)}
          />
          <input
            type="text"
            placeholder="Version"
            value={skillVersion}
            onChange={(event) => onSkillVersionChange(event.target.value)}
          />
          <label className="panel__label panel__label--inline">
            <input
              type="checkbox"
              checked={skillEnabled}
              onChange={(event) => onSkillEnabledChange(event.target.checked)}
            />
            Enabled
          </label>
          <textarea
            rows={10}
            value={skillContent}
            onChange={(event) => onSkillContentChange(event.target.value)}
          />
          {skillHistory.length > 0 ? (
            <div className="admin__history">
              <span className="panel__label">Recent versions</span>
              <ul className="admin__list">
                {skillHistory.map((item) => (
                  <li key={item.id}>
                    <span>{item.version ?? "n/a"}</span>
                    <span className="admin__meta">{item.changed_at ?? ""}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {skillError ? <p className="panel__error">{skillError}</p> : null}
          {skillSaved ? <p className="panel__success">Saved skill.</p> : null}
          <button type="button" className="button button--primary-subtle" onClick={onSaveSkill}>
            Save skill
          </button>
        </div>
      )}
    </details>
  );
}
