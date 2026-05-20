"use client";

import React from "react";
import type { AdminPlatformProfile } from "../../lib/types";

type Props = {
  platformProfile: AdminPlatformProfile | null;
  profileName: string;
  profileVersion: string;
  profileText: string;
  profileError: string | null;
  profileSaved: boolean;
  onProfileNameChange: (value: string) => void;
  onProfileVersionChange: (value: string) => void;
  onProfileTextChange: (value: string) => void;
  onSaveProfile: () => void;
};

export function PlatformProfilePanel({
  platformProfile,
  profileName,
  profileVersion,
  profileText,
  profileError,
  profileSaved,
  onProfileNameChange,
  onProfileVersionChange,
  onProfileTextChange,
  onSaveProfile,
}: Props) {
  return (
    <details>
      <summary>Platform profile (UCP)</summary>
      {!platformProfile ? (
        <p className="panel__empty">Platform profile not loaded yet.</p>
      ) : (
        <div className="admin__form">
          <span className="panel__label">Profile JSON</span>
          <input
            type="text"
            placeholder="Profile name"
            value={profileName}
            onChange={(event) => onProfileNameChange(event.target.value)}
          />
          <input
            type="text"
            placeholder="Version"
            value={profileVersion}
            onChange={(event) => onProfileVersionChange(event.target.value)}
          />
          <textarea
            rows={8}
            value={profileText}
            onChange={(event) => onProfileTextChange(event.target.value)}
          />
          {profileError ? <p className="panel__error">{profileError}</p> : null}
          {profileSaved ? <p className="panel__success">Saved platform profile.</p> : null}
          <button type="button" className="button button--primary-subtle" onClick={onSaveProfile}>
            Save profile
          </button>
        </div>
      )}
    </details>
  );
}
