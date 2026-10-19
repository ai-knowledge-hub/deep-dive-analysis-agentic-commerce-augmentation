"use client";
import React, { useCallback, useEffect, useState } from "react";
import type { WorkspaceList } from "../../lib/workspace";
import { WorkspaceIcon } from "../workspace-ui/WorkspaceIcons";
import { useWorkspaceFocus } from "../workspace-ui/useWorkspaceFocus";
import { WorkspaceNavigation } from "./WorkspaceNavigation";
import "../workspace-ui/workspace-shell.css";
import "./workspace.css";

type Props = {
  conversations: WorkspaceList; activeId?: string; title: string; subtitle: string;
  onNew: () => void; onSelect: (id: string) => void; details: React.ReactNode;
  children: (evidenceTarget: HTMLElement | null) => React.ReactNode;
};
export function WorkspaceShell({ conversations, activeId, title, subtitle, onNew, onSelect, details, children }: Props) {
  const [mobile, setMobile] = useState(false);
  const [navigation, setNavigation] = useState(false);
  const [inspector, setInspector] = useState(false);
  const [assistant, setAssistant] = useState(false);
  const [dark, setDark] = useState(false);
  const [evidenceTarget, setEvidenceTarget] = useState<HTMLDivElement | null>(null);
  const closeNavigation = useCallback(() => setNavigation(false), []);
  const closeInspector = useCallback(() => setInspector(false), []);
  useEffect(() => {
    const query = window.matchMedia("(max-width: 860px)");
    const sync = () => { setMobile(query.matches); if (!query.matches) setNavigation(false); };
    sync(); query.addEventListener("change", sync);
    return () => query.removeEventListener("change", sync);
  }, []);
  useEffect(() => { setInspector(false); setNavigation(false); }, [activeId]);
  useWorkspaceFocus(navigation, ".commerce-workspace .workspace-sidebar", closeNavigation);
  useWorkspaceFocus(inspector, ".commerce-workspace .workspace-inspector", closeInspector, mobile);
  function select(id: string) { closeNavigation(); closeInspector(); onSelect(id); }
  return <div className="commerce-workspace" data-theme={dark ? "dark" : "light"} data-inspector={inspector}>
    {navigation && <button className="workspace-mobile-backdrop" aria-label="Close navigation overlay" onClick={closeNavigation} />}
    <aside className={`workspace-sidebar ${navigation ? "is-open" : ""}`} aria-label="Work conversations" aria-hidden={mobile && !navigation ? true : undefined}
      role={navigation ? "dialog" : undefined} aria-modal={navigation ? true : undefined} tabIndex={-1}
      {...((mobile && !navigation) || (mobile && inspector) ? { inert: "" } : {})}>
      <WorkspaceNavigation conversations={conversations} activeId={activeId} onNew={() => { closeNavigation(); closeInspector(); onNew(); }} onSelect={select} onClose={closeNavigation}
        onAssistant={() => { closeNavigation(); setAssistant(true); setInspector(true); }} dark={dark} onTheme={() => setDark((value) => !value)} />
    </aside>
    <main className="workspace-dialogue" aria-label="Conversation workspace" {...(navigation || (mobile && inspector) ? { inert: "" } : {})}>
      <header className="workspace-topbar"><button data-workspace-menu className="workspace-menu workspace-icon-button" aria-label="Open navigation" onClick={() => setNavigation(true)}><WorkspaceIcon name="menu" /></button>
        <div><strong>{title}</strong><span>{subtitle}</span></div>
        <button className="workspace-icon-button" aria-label="Open work details" aria-expanded={inspector} onClick={() => { setAssistant(false); setInspector((value) => !value); }}><WorkspaceIcon name="panel" /></button>
      </header>
      {children(evidenceTarget)}
    </main>
    {inspector && <button className="workspace-inspector-backdrop" aria-label="Close details overlay" onClick={closeInspector} />}
    <aside className="workspace-inspector" aria-label="Work details" hidden={!inspector} role={mobile && inspector ? "dialog" : undefined} aria-modal={mobile && inspector ? true : undefined} tabIndex={-1}>
      <header><span>Work details</span><button className="workspace-icon-button" aria-label="Close work details" onClick={closeInspector}><WorkspaceIcon name="close" /></button></header>
      <div className="workspace-inspector-content">
        {assistant && <section><h2>Scout</h2><p>A commerce assistant for one existing product experiment. Every action needs your separate approval.</p><p>Pausing stops further scheduling; started work can finish. Cancellation reverses no completed effect. Synthetic results do not measure customer conversion.</p></section>}
        {details}
        <div ref={setEvidenceTarget} />
      </div>
    </aside>
  </div>;
}
