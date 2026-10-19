"use client";
import React, { useCallback, useEffect, useState } from "react";
import { PreviewArtifacts } from "./PreviewArtifacts";
import { PreviewInspector, PreviewDecision } from "./PreviewInspector";
import { PreviewIcon, ScoutMark } from "./PreviewIcons";
import {
  advanceSampleStep,
  attention,
  commitSampleDecision,
  sampleConversation,
  scenes,
  type Conversation,
  type Inspector,
  type Scene,
} from "./model";
import { usePreviewFocus } from "./usePreviewFocus";
import "./workspace-preview.css";

export function WorkspacePreview({
  initialScene = "start",
}: {
  initialScene?: Scene;
}) {
  const [conversations, setConversations] = useState<Conversation[]>([
    sampleConversation(
      "current",
      initialScene,
      initialScene === "start" ? "New conversation" : "Trail shoe comparison",
    ),
    sampleConversation("earlier", "outcome", "Earlier trail shoe comparison"),
  ]);
  const [selected, setSelected] = useState("current");
  const [inspector, setInspector] = useState<Inspector>(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [mobile, setMobile] = useState(false);
  useEffect(() => {
    const query = window.matchMedia("(max-width: 860px)");
    const sync = () => {
      setMobile(query.matches);
      if (!query.matches) setMobileOpen(false);
    };
    sync();
    query.addEventListener("change", sync);
    return () => query.removeEventListener("change", sync);
  }, []);
  const [dark, setDark] = useState(false);
  const [search, setSearch] = useState("");
  const work =
    conversations.find((conversation) => conversation.id === selected) ??
    conversations[0];
  const update = useCallback(
    (transform: (current: Conversation) => Conversation) =>
      setConversations((current) =>
        current.map((conversation) =>
          conversation.id === selected ? transform(conversation) : conversation,
        ),
      ),
    [selected],
  );
  const closeInspector = useCallback(() => setInspector(null), []);
  const closeMobile = useCallback(() => setMobileOpen(false), []);
  const closeDecision = useCallback(
    () => update((current) => ({ ...current, decision: null })),
    [update],
  );
  usePreviewFocus(mobileOpen, ".preview-sidebar", closeMobile);
  usePreviewFocus(
    Boolean(inspector),
    ".preview-inspector",
    closeInspector,
    mobile,
  );
  usePreviewFocus(
    Boolean(work.decision),
    ".preview-decision-dialog",
    closeDecision,
  );
  function newConversation() {
    const id = `sample-${conversations.length}`;
    setConversations((current) => [
      sampleConversation(id, "start", "New conversation"),
      ...current,
    ]);
    setSelected(id);
    setInspector(null);
    setMobileOpen(false);
  }
  function selectConversation(id: string) {
    setSelected(id);
    setInspector(null);
    setMobileOpen(false);
  }
  function setScene(scene: Scene) {
    update((current) => ({
      ...sampleConversation(current.id, scene, current.title),
      draft: current.draft,
    }));
    setInspector(null);
  }
  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!work.draft.trim()) return;
    if (work.scene === "start")
      update((current) => ({
        ...current,
        scene: "plan",
        title: "Trail shoe comparison",
        goal: current.draft.trim(),
        draft: "",
      }));
    else
      update((current) => ({
        ...current,
        questions: [...current.questions, current.draft.trim()],
        draft: "",
      }));
  }
  return (
    <div
      className="workspace-preview"
      data-theme={dark ? "dark" : "light"}
      data-inspector={Boolean(inspector)}
    >
      {mobileOpen && (
        <button
          className="preview-mobile-backdrop"
          aria-label="Close navigation overlay"
          onClick={closeMobile}
        />
      )}
      <aside
        className={`preview-sidebar ${mobileOpen ? "is-open" : ""}`}
        aria-label="Work conversations"
        aria-hidden={mobile && !mobileOpen ? true : undefined}
        role={mobileOpen ? "dialog" : undefined}
        aria-modal={mobileOpen ? true : undefined}
        {...((mobile && !mobileOpen) || work.decision || (mobile && inspector)
          ? { inert: "" }
          : {})}
        tabIndex={-1}
      >
        <div className="preview-brand">
          <span className="preview-brand-symbol">i</span>
          <strong>Intentionality</strong>
          <button
            className="preview-mobile-close preview-icon-button"
            onClick={closeMobile}
            aria-label="Close navigation"
          >
            <PreviewIcon name="close" />
          </button>
        </div>
        <button className="preview-new" onClick={newConversation}>
          <PreviewIcon name="plus" />
          New conversation
        </button>
        <label className="preview-search">
          <PreviewIcon name="search" />
          <input
            aria-label="Find a conversation"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Find a conversation"
          />
        </label>
        <button
          className="preview-assistant-profile"
          onClick={() => {
            setMobileOpen(false);
            setInspector("assistant");
          }}
        >
          <ScoutMark small />
          <span>
            <strong>Scout</strong>
            <small>Commerce assistant</small>
          </span>
          <PreviewIcon name="chevron" />
        </button>
        <div className="preview-conversations">
          <p className="preview-nav-label">Your work</p>
          {conversations
            .filter((conversation) =>
              conversation.title.toLowerCase().includes(search.toLowerCase()),
            )
            .map((conversation) => (
              <button
                key={conversation.id}
                aria-current={conversation.id === selected ? "page" : undefined}
                className={`preview-conversation ${conversation.id === selected ? "is-selected" : ""}`}
                onClick={() => selectConversation(conversation.id)}
              >
                <span
                  className={`preview-conversation-dot ${["approval", "blocked", "failed"].includes(conversation.scene) ? "needs-you" : ""}`}
                />
                <span>
                  <strong>{conversation.title}</strong>
                  <small>{attention(conversation)}</small>
                </span>
              </button>
            ))}
          {search &&
            !conversations.some((conversation) =>
              conversation.title.toLowerCase().includes(search.toLowerCase()),
            ) && (
              <p className="preview-search-empty">No matching conversations.</p>
            )}
        </div>
        <div className="preview-sidebar-footer">
          <a href="/lab">
            <PreviewIcon name="panel" />
            Advanced workspace
          </a>
          <button onClick={() => setDark((current) => !current)}>
            <PreviewIcon name="sun" />
            {dark ? "Light appearance" : "Dark appearance"}
          </button>
          <details className="preview-scene-picker">
            <summary>Preview states</summary>
            <label>
              Sample screen
              <select
                aria-label="Preview screen"
                value={work.scene}
                onChange={(event) => setScene(event.target.value as Scene)}
              >
                {scenes.map((scene) => (
                  <option value={scene} key={scene}>
                    {scene}
                  </option>
                ))}
              </select>
            </label>
            {work.activeStep && (
              <button
                className="preview-secondary"
                onClick={() => update(advanceSampleStep)}
              >
                Advance sample step
              </button>
            )}
          </details>
          <div className="preview-sample-label">
            <span>Design preview</span>
            <small>
              Sample data. No connected tools.
              <br />
              Chats reset when this page reloads.
            </small>
          </div>
          <div className="preview-user">
            <span>DG</span>
            <div>
              <strong>Your workspace</strong>
              <small>Example organisation</small>
            </div>
          </div>
        </div>
      </aside>
      <main
        className="preview-main"
        aria-label="Conversation workspace"
        {...(mobileOpen || work.decision || (mobile && inspector)
          ? { inert: "" }
          : {})}
      >
        <header className="preview-topbar">
          <button
            data-workspace-menu className="preview-menu preview-icon-button"
            onClick={() => setMobileOpen(true)}
            aria-label="Open navigation"
          >
            <PreviewIcon name="menu" />
          </button>
          <div>
            <strong>
              {work.scene === "start" ? "New conversation" : work.title}
            </strong>
            <span>Design preview · sample data</span>
          </div>
          <button
            className="preview-icon-button"
            aria-label="Open work details"
            aria-expanded={Boolean(inspector)}
            onClick={() => setInspector((current) => (current ? null : "plan"))}
          >
            <PreviewIcon name="panel" />
          </button>
        </header>
        <div
          className={`preview-conversation-body ${work.scene === "start" ? "is-empty" : ""}`}
        >
          {work.scene === "start" ? (
            <div className="preview-welcome">
              <p className="preview-eyebrow">Scout · your commerce assistant</p>
              <h1>
                What would you
                <br />
                like to improve?
              </h1>
              <p>
                Start with an existing product experiment.
                <br />
                We’ll take it one clear decision at a time.
              </p>
            </div>
          ) : (
            <div className="preview-thread" key={work.id}>
              <div className="preview-user-message">
                <span>You</span>
                <p>{work.goal}</p>
              </div>
              <div className="preview-assistant-message">
                <ScoutMark small />
                <div>
                  <strong>
                    Scout <span>Commerce assistant</span>
                  </strong>
                  <p>
                    {work.scene === "plan"
                      ? "Here’s a bounded plan for the sample autumn experiment. Take a look before creating work."
                      : work.scene === "outcome"
                        ? "The comparison is ready. Here’s what the evidence supports—and what remains unmeasured."
                        : "We’ll keep the comparison, your decisions and its evidence together here."}
                  </p>
                </div>
              </div>
              <PreviewArtifacts
                work={work}
                inspect={setInspector}
                decide={(decision) =>
                  update((current) => ({ ...current, decision }))
                }
                choose={() => setScene("plan")}
                create={() =>
                  update((current) => ({
                    ...current,
                    scene: "approval",
                    completed: 0,
                  }))
                }
              />
              {work.questions.map((question, index) => (
                <React.Fragment key={`${index}-${question}`}>
                  <div className="preview-user-message">
                    <span>You</span>
                    <p>{question}</p>
                  </div>
                  <div className="preview-preview-reply">
                    <strong>Preview reply</strong>
                    <p>
                      Your question is retained in this sample conversation. Use
                      the work details to inspect the fixed example; no model
                      was called.
                    </p>
                  </div>
                </React.Fragment>
              ))}
            </div>
          )}
          <form className="preview-composer" onSubmit={submit}>
            <label className="preview-sr-only" htmlFor="preview-message">
              Message Scout
            </label>
            <textarea
              id="preview-message"
              value={work.draft}
              onChange={(event) =>
                update((current) => ({ ...current, draft: event.target.value }))
              }
              placeholder={
                work.scene === "start"
                  ? "Compare a candidate with the control…"
                  : "Ask about the comparison…"
              }
              rows={work.scene === "start" ? 3 : 2}
              maxLength={2000}
            />
            <div>
              <span>One existing experiment</span>
              <button
                className="preview-send"
                type="submit"
                disabled={!work.draft.trim()}
                aria-label={
                  work.scene === "start" ? "Review objective" : "Send question"
                }
              >
                <PreviewIcon name="arrow" />
              </button>
            </div>
          </form>
          {work.scene === "start" && (
            <div className="preview-starters">
              <button
                onClick={() =>
                  update((current) => ({
                    ...current,
                    draft:
                      "Compare a clearer description with the control in the autumn experiment.",
                  }))
                }
              >
                Compare a candidate
                <PreviewIcon name="chevron" />
              </button>
              <button onClick={() => selectConversation("earlier")}>
                Review an earlier comparison
                <PreviewIcon name="chevron" />
              </button>
            </div>
          )}
          <p className="preview-composer-note">
            All decisions and results on this page are illustrative. No live
            work is created.
          </p>
        </div>
      </main>
      {inspector && (
        <>
          <button
            className="preview-inspector-backdrop"
            onClick={closeInspector}
            aria-label="Close details overlay"
          />
          <PreviewInspector
            panel={inspector}
            work={work}
            close={closeInspector}
            mobile={mobile}
            inert={Boolean(work.decision)}
          />
        </>
      )}
      <PreviewDecision
        decision={work.decision}
        work={work}
        close={closeDecision}
        confirm={() => update(commitSampleDecision)}
      />
    </div>
  );
}
