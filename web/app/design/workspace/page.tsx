import React from "react";
import { notFound } from "next/navigation";
import { WorkspacePreview } from "@/components/workspace-preview/WorkspacePreview";
import { isScene } from "@/components/workspace-preview/model";
import { workspacePreviewEnabled } from "@/lib/design-preview";
export const dynamic = "force-dynamic";
export default function WorkspaceDesignPage({
  searchParams,
}: {
  searchParams: { scene?: string };
}) {
  if (
    !workspacePreviewEnabled(
      process.env.NODE_ENV,
      process.env.WORKSPACE_DESIGN_PREVIEW,
    )
  )
    notFound();
  return (
    <WorkspacePreview
      initialScene={isScene(searchParams.scene) ? searchParams.scene : "start"}
    />
  );
}
