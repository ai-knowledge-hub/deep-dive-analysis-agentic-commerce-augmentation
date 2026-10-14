"use client";
import React, { useEffect, useState } from "react";
import { Sidebar } from "../components/layout/Sidebar";
import { OperatorWorkspace } from "../components/workspace/OperatorWorkspace";
import { useOperatorWorkspace } from "../components/workspace/useOperatorWorkspace";
import { useTenant } from "../components/tenant/TenantProvider";
import { useAppUser } from "../lib/auth";
import { listAgentRuns } from "../lib/api";
import type { AgentRun } from "../lib/types";

export default function HomePage() {
  const { clientId } = useTenant();
  const { user } = useAppUser();
  const workspace = useOperatorWorkspace(clientId, user?.id ?? null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [runs, setRuns] = useState<AgentRun[]>([]);
  useEffect(() => {
    let active = true; setRuns([]);
    void listAgentRuns({ limit: 100 }).then((result) => { if (active) setRuns(result.runs); }).catch(() => { if (active) setRuns([]); });
    return () => { active = false; };
  }, [clientId, user?.id]);
  return <div className="app">
    <Sidebar mobileOpen={mobileOpen} onMobileClose={() => setMobileOpen(false)} onNewConversation={workspace.reset}
      sessions={workspace.conversations.conversations.map((conversation) => ({ id: conversation.session_id, preview: conversation.run_id ? "Run conversation" : "Objective conversation" }))}
      activeSessionId={workspace.history?.session_id} onSelectSession={(id) => void workspace.select(id)}
      onDeleteSession={() => undefined} onOpenHistory={() => undefined} showHistoryButton={false} />
    <div className="main main--detail"><OperatorWorkspace onMenu={() => setMobileOpen(true)} key={`${workspace.generation}:${workspace.history?.session_id ?? "new"}`} workspace={workspace} runs={runs} userId={user?.id ?? null} /></div>
  </div>;
}
