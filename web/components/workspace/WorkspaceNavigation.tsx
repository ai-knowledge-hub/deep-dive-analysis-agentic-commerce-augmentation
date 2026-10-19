"use client";
import React, { useState } from "react";
import { ScoutMark, WorkspaceIcon } from "../workspace-ui/WorkspaceIcons";
import type { WorkspaceList } from "../../lib/workspace";
import { WorkspaceAccount } from "./WorkspaceAccount";

type Props = {
  conversations: WorkspaceList; activeId?: string; onNew: () => void; onSelect: (id: string) => void;
  onClose: () => void; onAssistant: () => void; dark: boolean; onTheme: () => void;
};
export function WorkspaceNavigation({ conversations, activeId, onNew, onSelect, onClose, onAssistant, dark, onTheme }: Props) {
  const [search, setSearch] = useState("");
  const matching = conversations.conversations.filter((item) => (item.preview || "Conversation").toLowerCase().includes(search.toLowerCase()));
  return <>
    <div className="workspace-brand"><span className="workspace-brand-symbol">i</span><strong>Intentionality</strong>
      <button className="workspace-mobile-close workspace-icon-button" onClick={onClose} aria-label="Close navigation"><WorkspaceIcon name="close" /></button>
    </div>
    <button className="workspace-new" onClick={onNew}><WorkspaceIcon name="plus" />New conversation</button>
    <label className="workspace-search"><WorkspaceIcon name="search" /><input aria-label="Find a conversation" placeholder="Find a conversation" value={search} onChange={(e) => setSearch(e.target.value)} /></label>
    <button className="workspace-assistant-profile" onClick={onAssistant}><ScoutMark small /><span><strong>Scout</strong><small>Commerce assistant</small></span><WorkspaceIcon name="chevron" /></button>
    <nav className="workspace-conversations" aria-label="Your conversations"><p className="workspace-nav-label">Your work</p>
      {matching.map((item) => <button className={`workspace-conversation ${activeId === item.session_id ? "is-selected" : ""}`} aria-current={activeId === item.session_id ? "page" : undefined} key={item.session_id} onClick={() => onSelect(item.session_id)}>
        <span className="workspace-conversation-dot" /><span><strong>{item.preview || "Conversation"}</strong><small>{item.run_id ? "Supervised run" : "Objective review"}</small></span>
      </button>)}
      {!matching.length && <p className="workspace-search-empty">{search ? "No matching conversations." : "Your conversations will appear here."}</p>}
      {conversations.has_more && <p className="workspace-note">Showing recent conversations. Open an older conversation with its saved link.</p>}
    </nav>
    <div className="workspace-sidebar-footer">
      <details className="workspace-advanced"><summary>Advanced workspace</summary><nav aria-label="Control plane">
        <a href="/inbox">Inbox</a><a href="/runs">Runs</a><a href="/interventions">Interventions</a><a href="/learnings">Insights</a><a href="/lab">Lab</a>
        <a href="/alignment">Alignment</a><a href="/evidence">Evidence</a><a href="/simulation">Simulation</a><a href="/experiments">Experiments</a><a href="/validation">Validation</a><a href="/overview">Overview</a>
      </nav></details>
      <button onClick={onTheme}><WorkspaceIcon name="sun" />{dark ? "Light appearance" : "Dark appearance"}</button>
      <WorkspaceAccount />
    </div>
  </>;
}
