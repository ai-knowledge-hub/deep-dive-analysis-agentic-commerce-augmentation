"use client";

import React, { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  confirmOperatorConversationCommand,
  listOperatorConversationCommands,
  sendOperatorConversationMessageStream,
} from "../../lib/api";
import type {
  OperatorCommandProposal,
  OperatorCommandReceipt,
  OperatorCommandRecord,
} from "../../lib/operatorConversationTypes";
import type { AgentAction, AgentRun, AgentRunEvent } from "../../lib/types";
import { OperatorChatPrompts } from "./OperatorChatPrompts";
import { OperatorChatSummary } from "./OperatorChatSummary";
import { OperatorChatThread } from "./OperatorChatThread";
import type { ChatMessage, PromptId } from "./operatorChatTypes";

type Props = {
  run: AgentRun | null;
  actions: AgentAction[];
  events: AgentRunEvent[];
  userId: string | null;
  selectedAction: AgentAction | null;
  nextRecommendedAction: {
    action: AgentAction | null;
    guardrails: string[];
    hint: string;
  };
  onJumpToNextAction?: () => void;
  onCommandCommitted?: () => void | Promise<void>;
};

const PROMPTS: Record<PromptId, string> = {
  brief: "Give me a verified briefing for this run.",
  explain_run: "Explain this run and its current lifecycle state.",
  summarize_failures: "Summarize the verified failures in this run.",
  blocked_action: "Explain the current blocker or pending approval.",
  recommend_next: "Recommend the next operator action from verified evidence.",
  open_context: "Show me the related evidence and records.",
};

export function OperatorConsoleChat({
  run,
  actions,
  events,
  userId,
  selectedAction,
  nextRecommendedAction,
  onJumpToNextAction,
  onCommandCommitted,
}: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmingProposalId, setConfirmingProposalId] = useState<string | null>(null);
  const [dismissedProposalIds, setDismissedProposalIds] = useState<string[]>([]);
  const [commandReceipt, setCommandReceipt] = useState<OperatorCommandReceipt | null>(null);
  const [commandRecords, setCommandRecords] = useState<OperatorCommandRecord[]>([]);
  const [commandHistoryPage, setCommandHistoryPage] = useState<{
    hasMore: boolean;
    nextCursor: string | null;
    totalCount: number;
  }>({ hasMore: false, nextCursor: null, totalCount: 0 });
  const [loadingOlderCommands, setLoadingOlderCommands] = useState(false);
  const [commandRecordsError, setCommandRecordsError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const requestRef = useRef(0);
  const confirmationRequestRef = useRef(0);
  const commandRecordsRequestRef = useRef(0);

  const counts = useMemo(
    () => ({
      proposed: actions.filter((action) => action.status === "proposed").length,
      approved: actions.filter((action) => action.status === "approved").length,
      failed: actions.filter((action) => action.status === "failed").length,
      policy: events.filter((event) => event.is_policy_event).length,
    }),
    [actions, events],
  );

  const refreshCommandRecords = useCallback(
    async ({
      signal,
      cursor = null,
      append = false,
    }: {
      signal?: AbortSignal;
      cursor?: string | null;
      append?: boolean;
    } = {}) => {
      if (!run) {
        commandRecordsRequestRef.current += 1;
        setCommandRecords([]);
        setCommandHistoryPage({ hasMore: false, nextCursor: null, totalCount: 0 });
        setCommandRecordsError(null);
        return;
      }
      const requestId = commandRecordsRequestRef.current + 1;
      commandRecordsRequestRef.current = requestId;
      try {
        const response = await listOperatorConversationCommands(run.id, {
          cursor,
          signal,
        });
        if (
          commandRecordsRequestRef.current !== requestId ||
          response.run_id !== run.id
        ) {
          return;
        }
        setCommandRecords((current) => {
          if (!append) return response.records;
          const records = new Map(
            current.map((record) => [record.proposal.proposal_id, record]),
          );
          response.records.forEach((record) => {
            records.set(record.proposal.proposal_id, record);
          });
          return [...records.values()];
        });
        setCommandHistoryPage({
          hasMore: response.page.has_more,
          nextCursor: response.page.next_cursor,
          totalCount: response.total_count,
        });
        setCommandRecordsError(null);
      } catch (caught) {
        if (signal?.aborted || commandRecordsRequestRef.current !== requestId) return;
        setCommandRecordsError(
          caught instanceof Error ? caught.message : "Operator command history is unavailable.",
        );
      }
    },
    [run],
  );

  const loadOlderCommands = useCallback(async () => {
    if (!commandHistoryPage.hasMore || !commandHistoryPage.nextCursor) return;
    setLoadingOlderCommands(true);
    try {
      await refreshCommandRecords({
        cursor: commandHistoryPage.nextCursor,
        append: true,
      });
    } finally {
      setLoadingOlderCommands(false);
    }
  }, [commandHistoryPage, refreshCommandRecords]);

  useEffect(() => {
    abortRef.current?.abort();
    requestRef.current += 1;
    confirmationRequestRef.current += 1;
    commandRecordsRequestRef.current += 1;
    setMessages([]);
    setSessionId(null);
    setDraft("");
    setStatus(null);
    setError(null);
    setConfirmingProposalId(null);
    setDismissedProposalIds([]);
    setCommandReceipt(null);
    setCommandRecords([]);
    setCommandHistoryPage({ hasMore: false, nextCursor: null, totalCount: 0 });
    setLoadingOlderCommands(false);
    setCommandRecordsError(null);
  }, [run?.id]);

  useEffect(() => {
    const controller = new AbortController();
    void refreshCommandRecords({ signal: controller.signal });
    return () => controller.abort();
  }, [refreshCommandRecords]);

  async function confirmPause(proposal: OperatorCommandProposal) {
    if (!run || !proposal || confirmingProposalId) return;
    const confirmationRequestId = confirmationRequestRef.current + 1;
    confirmationRequestRef.current = confirmationRequestId;
    setConfirmingProposalId(proposal.proposal_id);
    setError(null);
    try {
      const response = await confirmOperatorConversationCommand(
        run.id,
        proposal.proposal_id,
        proposal.proposal_digest,
      );
      if (confirmationRequestRef.current !== confirmationRequestId) return;
      setCommandReceipt(response.receipt);
      await refreshCommandRecords();
      await onCommandCommitted?.();
    } catch (caught) {
      if (confirmationRequestRef.current !== confirmationRequestId) return;
      setError(caught instanceof Error ? caught.message : "Pause confirmation failed.");
    } finally {
      if (confirmationRequestRef.current === confirmationRequestId) {
        setConfirmingProposalId(null);
      }
    }
  }

  async function sendQuestion(question: string) {
    const normalized = question.trim();
    if (!normalized || !run || !userId) return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const requestId = requestRef.current + 1;
    requestRef.current = requestId;
    const assistantId = `assistant-${requestId}`;
    setError(null);
    setDraft("");
    setMessages((current) => [
      ...current,
      { id: `user-${requestId}`, role: "user", content: normalized },
      { id: assistantId, role: "assistant", content: "" },
    ]);
    try {
      const response = await sendOperatorConversationMessageStream(
        run.id,
        normalized,
        sessionId,
        {
          onStatus: (phase) => {
            if (requestRef.current === requestId) setStatus(phase);
          },
          onDelta: (delta) => {
            if (requestRef.current !== requestId) return;
            setMessages((current) =>
              current.map((message) =>
                message.id === assistantId
                  ? { ...message, content: `${message.content}${delta}` }
                  : message,
              ),
            );
          },
        },
        controller.signal,
      );
      if (requestRef.current !== requestId) return;
      setSessionId(response.session_id);
      setStatus(null);
      setMessages((current) =>
        current.map((message) =>
          message.id === assistantId
            ? { ...message, content: response.answer, response }
            : message,
        ),
      );
      await refreshCommandRecords();
    } catch (caught) {
      if (controller.signal.aborted || requestRef.current !== requestId) return;
      setStatus(null);
      setError(caught instanceof Error ? caught.message : "The grounded answer failed.");
      setMessages((current) => current.filter((message) => message.id !== assistantId));
    }
  }

  function sendPrompt(promptId: PromptId) {
    const selection =
      promptId === "blocked_action" && selectedAction
        ? ` Focus on action ${selectedAction.id}.`
        : "";
    void sendQuestion(`${PROMPTS[promptId]}${selection}`);
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void sendQuestion(draft);
  }

  const latestResponse = [...messages]
    .reverse()
    .find((message) => message.response)?.response;
  const durablePendingProposal = commandRecords.find(
    (record) =>
      !record.receipt &&
      new Date(record.proposal.expires_at).getTime() > Date.now() &&
      !dismissedProposalIds.includes(record.proposal.proposal_id),
  )?.proposal;
  const pendingProposal = durablePendingProposal ?? latestResponse?.command_proposal ?? null;
  const durableReceipt =
    commandReceipt ?? commandRecords.find((record) => Boolean(record.receipt))?.receipt ?? null;

  return (
    <section className="panel__card panel__card--secondary">
      <OperatorChatSummary
        run={run}
        briefing={
          run
            ? "Ask about verified execution, evidence, blockers, or next steps. Pause requests become reviewable proposals and require a separate confirmation."
            : "Select a run to start a grounded operator conversation."
        }
        proposedCount={counts.proposed}
        approvedCount={counts.approved}
        failedCount={counts.failed}
        policyCount={counts.policy}
        selectedAction={selectedAction}
      />
      <OperatorChatPrompts
        selectedAction={selectedAction}
        hasNextAction={Boolean(nextRecommendedAction.action)}
        onPrompt={sendPrompt}
        onJumpToNextAction={onJumpToNextAction}
      />
      <OperatorChatThread messages={messages} />

      <form className="operator-chat__composer" onSubmit={submit}>
        <label className="panel__label" htmlFor="operator-chat-question">
          Ask about the selected run
        </label>
        <textarea
          id="operator-chat-question"
          className="panel__textarea"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="What evidence supports this result?"
          rows={3}
          maxLength={2000}
          disabled={!run || !userId || Boolean(status)}
        />
        <div className="panel__actions">
          <button
            type="submit"
            className="button button--primary button--sm"
            disabled={!run || !userId || !draft.trim() || Boolean(status)}
          >
            Ask
          </button>
          {status ? <span className="panel__muted">{status.replaceAll("_", " ")}</span> : null}
        </div>
      </form>

      {error ? <div className="panel__notice panel__notice--error">{error}</div> : null}
      {latestResponse ? (
        <div className="operator-chat__artifacts" aria-label="Verified answer details">
          <div className="panel__notice panel__notice--info">
            Evidence view {latestResponse.snapshot.digest.slice(0, 12)} · {latestResponse.freshness.state}
            {" · "}Data {latestResponse.freshness.data_state}
            {" · "}Cursor {latestResponse.freshness.snapshot_cursor?.slice(0, 12) ?? "no events"}
          </div>
          {latestResponse.warnings.map((warning) => (
            <div key={warning.code} className="panel__notice panel__notice--warning">
              {warning.message}
            </div>
          ))}
          {latestResponse.recommendation ? (
            <div className="panel__notice panel__notice--info">
              <strong>Recommendation:</strong> {latestResponse.recommendation.text}
            </div>
          ) : null}
          <details className="panel__details">
            <summary className="panel__details-summary">
              Verified facts ({latestResponse.verified_facts.length})
            </summary>
            <ul className="operator-chat__fact-list">
              {latestResponse.verified_facts.map((fact) => (
                <li key={fact.id}>
                  <span>{fact.text}</span>
                  <small>
                    {fact.category} · {fact.trust ?? "authoritative_projection"} · {fact.provenance.record_type}{" "}
                    <a href={fact.source}>Source</a>
                  </small>
                </li>
              ))}
            </ul>
          </details>
          {latestResponse.evidence.length ? (
            <details className="panel__details">
              <summary className="panel__details-summary">
                Evidence records ({latestResponse.evidence.length})
              </summary>
              <ul className="operator-chat__fact-list">
                {latestResponse.evidence.map((item, index) => {
                  const evidenceId = String(
                    item.record.evidence_id ?? item.record.id ?? `record-${index + 1}`,
                  );
                  const sourceType = String(item.record.source_type ?? item.kind);
                  return (
                    <li key={`${item.kind}-${evidenceId}-${index}`}>
                      <span>{evidenceId}</span>
                      <small>
                        {sourceType} · <a href={item.href}>Open evidence</a>
                      </small>
                    </li>
                  );
                })}
              </ul>
            </details>
          ) : null}
          <div className="panel__actions">
            {latestResponse.navigation.map((link) => (
              <a key={link.href} className="button button--ghost button--sm" href={link.href}>
                {link.label}
              </a>
            ))}
          </div>
        </div>
      ) : null}
      {run ? (
        <section className="operator-chat__artifacts" aria-label="Durable operator commands">
          <div className="control-section__header">
            <strong>Operator commands</strong>
            <span className="control-chip">
              {commandRecords.length}
              {commandHistoryPage.totalCount > commandRecords.length
                ? ` of ${commandHistoryPage.totalCount}`
                : ""}
            </span>
          </div>
          {commandRecordsError ? (
            <div className="panel__notice panel__notice--warning">
              Durable operator command history could not be loaded: {commandRecordsError}
            </div>
          ) : null}
          {commandHistoryPage.hasMore ? (
            <div className="panel__notice panel__notice--warning">
              Showing the newest {commandRecords.length} of {commandHistoryPage.totalCount} durable
              commands. Older proposal and receipt evidence is available.
              <div className="panel__actions">
                <button
                  type="button"
                  className="button button--ghost button--sm"
                  disabled={loadingOlderCommands}
                  onClick={() => void loadOlderCommands()}
                >
                  {loadingOlderCommands ? "Loading…" : "Load older commands"}
                </button>
              </div>
            </div>
          ) : null}
          {pendingProposal &&
          !dismissedProposalIds.includes(pendingProposal.proposal_id) &&
          durableReceipt?.proposal_id !== pendingProposal.proposal_id ? (
            <section className="operator-chat__proposal" aria-label="Pause proposal">
              <div>
                <strong>Pause this run?</strong>
                <div className="panel__muted">
                  Revision {pendingProposal.source.active_graph_revision} · status{" "}
                  {pendingProposal.source.run_status} · expires{" "}
                  {new Date(pendingProposal.expires_at).toLocaleTimeString()}
                </div>
              </div>
              <ul className="operator-chat__fact-list">
                {pendingProposal.consequences.map((consequence) => (
                  <li key={consequence}>{consequence}</li>
                ))}
              </ul>
              <div className="panel__muted">
                Proposal {pendingProposal.proposal_id.slice(0, 12)} · digest{" "}
                {pendingProposal.proposal_digest.slice(0, 12)}
              </div>
              <div className="panel__actions">
                <button
                  type="button"
                  className="button button--primary button--sm"
                  disabled={Boolean(confirmingProposalId)}
                  onClick={() => void confirmPause(pendingProposal)}
                >
                  {confirmingProposalId ? "Confirming…" : "Confirm pause"}
                </button>
                <button
                  type="button"
                  className="button button--ghost button--sm"
                  disabled={Boolean(confirmingProposalId)}
                  onClick={() =>
                    setDismissedProposalIds((current) => [
                      ...current,
                      pendingProposal.proposal_id,
                    ])
                  }
                >
                  Dismiss
                </button>
              </div>
            </section>
          ) : null}
          {durableReceipt ? (
            <div className="panel__notice panel__notice--info" aria-label="Pause receipt">
              <strong>Pause acknowledged.</strong> Receipt {durableReceipt.receipt_id} · proposal{" "}
              {durableReceipt.proposal_id} · {durableReceipt.acknowledgement.replaceAll("_", " ")}.
              Runtime propagation is not independently certified.{" "}
              <a href={`/interventions?run_id=${run.id}`}>Open Interventions</a>
            </div>
          ) : null}
          {!pendingProposal && !durableReceipt && !commandRecordsError ? (
            <div className="panel__muted">No conversational operator commands are recorded.</div>
          ) : null}
          {commandRecords.length ? (
            <details className="panel__details">
              <summary className="panel__details-summary">
                Durable command history ({commandRecords.length})
              </summary>
              <ul className="operator-chat__fact-list">
                {commandRecords.map((record) => (
                  <li key={record.proposal.proposal_id}>
                    <span>
                      Pause proposal {record.proposal.proposal_id} ·{" "}
                      {record.receipt ? "completed" : "awaiting confirmation"}
                    </span>
                    <small>
                      Proposal digest {record.proposal.proposal_digest} · receipt{" "}
                      {record.receipt?.receipt_id ?? "not issued"}
                    </small>
                  </li>
                ))}
              </ul>
            </details>
          ) : null}
        </section>
      ) : null}
    </section>
  );
}
