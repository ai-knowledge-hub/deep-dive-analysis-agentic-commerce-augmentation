export const scenes = [
  "start",
  "clarification",
  "plan",
  "approval",
  "running",
  "blocked",
  "paused",
  "failed",
  "partial",
  "outcome",
  "cancelled",
] as const;
export type Scene = (typeof scenes)[number];
export type Inspector = "plan" | "evidence" | "assistant" | "setup" | null;
export type Decision =
  "approve" | "reject" | "pause" | "resume" | "cancel" | null;
export type Conversation = {
  id: string;
  title: string;
  scene: Scene;
  completed: number;
  activeStep: boolean;
  draft: string;
  goal: string;
  questions: string[];
  decision: Decision;
};
export const steps = [
  {
    label: "Freeze comparison inputs",
    detail:
      "Save the query set so the control and candidate are evaluated on the same inputs.",
  },
  {
    label: "Evaluate the control",
    detail: "Run the existing control against the fixed comparison inputs.",
  },
  {
    label: "Identify improvement ideas",
    detail:
      "Use the baseline evidence to create hypotheses for this experiment.",
  },
  {
    label: "Prepare one candidate",
    detail:
      "Create one candidate description inside this experiment. The live product page stays unchanged.",
  },
  {
    label: "Evaluate the candidate",
    detail:
      "Compare the candidate with the control. The limit is one candidate evaluation.",
  },
  {
    label: "Request synthetic validation",
    detail:
      "Send this experiment’s comparison data to the configured validation provider. This may use part of the run’s recorded-cost budget.",
  },
  {
    label: "Review validation readiness",
    detail:
      "Check which validation requirements are met and which evidence is still missing.",
  },
  {
    label: "Update the experiment assessment",
    detail:
      "Record the updated assessment from the available experiment evidence.",
  },
  {
    label: "Recommend the next action",
    detail:
      "Record a recommendation. Nothing is published to the live product page.",
  },
];
export function isScene(value: unknown): value is Scene {
  return typeof value === "string" && scenes.some((scene) => scene === value);
}
export function sampleConversation(
  id: string,
  scene: Scene,
  title = "Trail shoe comparison",
): Conversation {
  const completed =
    scene === "outcome"
      ? 9
      : scene === "partial"
        ? 7
        : ["start", "clarification", "plan", "blocked"].includes(scene)
          ? 0
          : 5;
  return {
    id,
    title,
    scene,
    completed,
    activeStep: scene === "running",
    draft: "",
    questions: [],
    decision: null,
    goal:
      scene === "start"
        ? ""
        : "Compare a clearer product description with the control in the autumn experiment.",
  };
}
export function commitSampleDecision(conversation: Conversation): Conversation {
  const updated = { ...conversation, decision: null };
  switch (conversation.decision) {
    case "approve":
      return conversation.scene === "approval" &&
        conversation.completed < steps.length
        ? { ...updated, scene: "running", activeStep: true }
        : updated;
    case "reject":
      return conversation.scene === "approval"
        ? { ...updated, scene: "partial" }
        : updated;
    case "pause":
      return ["approval", "running"].includes(conversation.scene)
        ? { ...updated, scene: "paused" }
        : updated;
    case "resume":
      return conversation.scene === "paused"
        ? {
            ...updated,
            scene: conversation.activeStep
              ? "running"
              : conversation.completed === steps.length
                ? "outcome"
                : "approval",
          }
        : updated;
    case "cancel":
      return conversation.activeStep ||
        !["approval", "paused"].includes(conversation.scene)
        ? updated
        : { ...updated, scene: "cancelled" };
    default:
      return updated;
  }
}
export function advanceSampleStep(conversation: Conversation): Conversation {
  if (
    !conversation.activeStep ||
    !["running", "paused"].includes(conversation.scene)
  )
    return conversation;
  const completed = Math.min(conversation.completed + 1, steps.length);
  const scene =
    conversation.scene === "paused"
      ? "paused"
      : completed === steps.length
        ? "outcome"
        : "approval";
  return { ...conversation, completed, activeStep: false, scene };
}
export function attention(conversation: Conversation): string {
  switch (conversation.scene) {
    case "start":
      return "New conversation";
    case "clarification":
      return "Choose an experiment";
    case "plan":
      return "Plan ready to review";
    case "approval":
      return "Needs your review";
    case "running":
      return "Working on the comparison";
    case "blocked":
      return "Setup needed";
    case "paused":
      return "Further work is paused";
    case "failed":
      return "Validation outcome unknown";
    case "partial":
      return "Some work remains unresolved";
    case "outcome":
      return "Comparison finished";
    case "cancelled":
      return "Run cancelled";
  }
}
