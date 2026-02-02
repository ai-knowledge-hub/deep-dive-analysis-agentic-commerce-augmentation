"use client";

import type { SessionSummary } from "../../lib/types";

type Props = {
  isOpen: boolean;
  isClosing: boolean;
  sessions: SessionSummary[];
  activeSessionId?: string | null;
  onClose: () => void;
  onSelect: (session: SessionSummary) => void;
  onRequestDelete: (sessionId: string) => void;
};

export function HistoryDrawer({
  isOpen,
  isClosing,
  sessions,
  activeSessionId,
  onClose,
  onSelect,
  onRequestDelete,
}: Props) {
  if (!isOpen) return null;

  return (
    <div
      className={`history-overlay ${isClosing ? "is-closing" : ""}`}
      role="dialog"
      aria-modal="true"
      onClick={onClose}
    >
      <div
        className={`history-panel ${isClosing ? "is-closing" : ""}`}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="history-panel__header">
          <h4>History</h4>
          <button
            type="button"
            className="history-panel__close"
            onClick={onClose}
            aria-label="Close history"
          >
            ×
          </button>
        </div>
        <div className="history-panel__list">
          {sessions.length === 0 ? (
            <p className="panel__empty">No conversations yet.</p>
          ) : (
            sessions.map((session) => (
              <div
                key={session.id}
                role="button"
                tabIndex={0}
                className={`history-panel__item ${
                  session.id === activeSessionId ? "is-active" : ""
                }`}
                onClick={() => onSelect(session)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onSelect(session);
                  }
                }}
              >
                <div className="history-panel__row">
                  <span
                    className="history-panel__title"
                    title={session.preview || "Conversation"}
                  >
                    {session.preview || "Conversation"}
                  </span>
                  <button
                    type="button"
                    className="history-panel__delete"
                    onClick={(event) => {
                      event.stopPropagation();
                      onRequestDelete(session.id);
                    }}
                    aria-label="Delete conversation"
                    title="Delete conversation"
                  >
                    <svg viewBox="0 0 24 24" aria-hidden="true" className="icon">
                      <path
                        d="M9 3h6l1 2h4v2H4V5h4l1-2zm1 6h2v9h-2V9zm4 0h2v9h-2V9zM7 9h2v9H7V9z"
                        fill="currentColor"
                      />
                    </svg>
                  </button>
                </div>
                {session.last_turn_at && (
                  <span className="history-panel__meta">
                    {new Date(session.last_turn_at).toLocaleDateString()}
                  </span>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
