"use client";

import React from "react";
import type { AdminClientUser } from "../../lib/types";

export type ClientUserForm = {
  memberUserId: string;
  role: string;
};

type Props = {
  activeClientId: string;
  selectedClientName?: string | null;
  clientUsers: AdminClientUser[];
  userForm: ClientUserForm;
  onUserFormChange: (patch: Partial<ClientUserForm>) => void;
  onAddClientUser: () => void;
};

export function ClientAccessPanel({
  activeClientId,
  selectedClientName,
  clientUsers,
  userForm,
  onUserFormChange,
  onAddClientUser,
}: Props) {
  return (
    <details>
      <summary>Client access</summary>
      {activeClientId ? (
        <div className="admin__form">
          <p className="panel__meta">
            Users added here get access to: <strong>{selectedClientName ?? activeClientId}</strong>
          </p>
          <span className="panel__label">Client users</span>
          {clientUsers.length === 0 ? (
            <p className="panel__empty">No users yet.</p>
          ) : (
            <ul className="admin__list">
              {clientUsers.map((member) => (
                <li key={member.id}>
                  <span>{member.user_id}</span>
                  <span className="admin__meta">{member.role ?? "analyst"}</span>
                </li>
              ))}
            </ul>
          )}
          <input
            type="text"
            placeholder="Clerk user id"
            value={userForm.memberUserId}
            onChange={(event) => onUserFormChange({ memberUserId: event.target.value })}
          />
          <input
            type="text"
            placeholder="Role (analyst, admin)"
            value={userForm.role}
            onChange={(event) => onUserFormChange({ role: event.target.value })}
          />
          <button
            type="button"
            className="button button--primary-subtle"
            onClick={onAddClientUser}
            disabled={!userForm.memberUserId.trim()}
          >
            Add user to selected client
          </button>
        </div>
      ) : (
        <p className="panel__empty">Select a client first.</p>
      )}
    </details>
  );
}
