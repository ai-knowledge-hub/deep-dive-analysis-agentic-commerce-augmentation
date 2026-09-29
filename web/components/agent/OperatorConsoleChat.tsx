"use client";

import React, { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { sendOperatorConversationMessageStream } from "../../lib/api";
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
}: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const requestRef = useRef(0);

  const counts = useMemo(
    () => ({
      proposed: actions.filter((action) => action.status === "proposed").length,
      approved: actions.filter((action) => action.status === "approved").length,
      failed: actions.filter((action) => action.status === "failed").length,
      policy: events.filter((event) => event.is_policy_event).length,
    }),
    [actions, events],
  );

  useEffect(() => {
    abortRef.current?.abort();
    requestRef.current += 1;
    setMessages([]);
    setSessionId(null);
    setDraft("");
    setStatus(null);
    setError(null);
  }, [run?.id]);

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

  return (
    <section className="panel__card panel__card--secondary">
      <OperatorChatSummary
        run={run}
        briefing={
          run
            ? "Ask about this run’s verified execution, evidence, blockers, or recommended next step. Conversation cannot change execution state."
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
    </section>
  );
}
