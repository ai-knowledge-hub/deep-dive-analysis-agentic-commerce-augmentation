"use client";
import React, { useEffect, useState } from "react";
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
  const scope = JSON.stringify([clientId, user?.id]);
  const [runList, setRunList] = useState<{ scope: string; runs: AgentRun[] }>({ scope: "", runs: [] });
  useEffect(() => {
    let active = true; setRunList({ scope, runs: [] });
    void listAgentRuns({ limit: 100 }).then((result) => { if (active) setRunList({ scope, runs: result.runs }); }).catch(() => { if (active) setRunList({ scope, runs: [] }); });
    return () => { active = false; };
  }, [clientId, user?.id, scope]);
  return <OperatorWorkspace workspace={workspace} runs={runList.scope === scope ? runList.runs : []} userId={user?.id ?? null} />;
}
