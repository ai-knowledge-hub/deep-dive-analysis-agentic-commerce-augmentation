import React from "react";
export function ScoutMark({ small = false }: { small?: boolean }) {
  return (
    <svg
      className={small ? "scout-mark scout-mark--small" : "scout-mark"}
      viewBox="0 0 48 48"
      role="img"
      aria-label="Scout, commerce assistant"
    >
      <rect x="2" y="2" width="44" height="44" fill="var(--workspace-canvas, var(--preview-canvas))" />
      {[0, 1, 2, 3].map((ring) => (
        <rect
          key={ring}
          x={4 + ring * 5}
          y={4 + ring * 5}
          width={40 - ring * 10}
          height={40 - ring * 10}
          rx={9 - ring * 2}
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          transform={`rotate(${ring * 8} 24 24)`}
        />
      ))}
    </svg>
  );
}
export function WorkspaceIcon({
  name,
}: {
  name:
    | "plus"
    | "arrow"
    | "close"
    | "panel"
    | "menu"
    | "check"
    | "search"
    | "chevron"
    | "sun"
    | "pause";
}) {
  const paths = {
    plus: "M12 5v14M5 12h14",
    arrow: "M12 19V5m-6 6 6-6 6 6",
    close: "m6 6 12 12M6 18 18 6",
    panel: "M15 4v16M4 4h16v16H4z",
    menu: "M4 6h16M4 12h16M4 18h16",
    check: "m5 12 4 4L19 6",
    search: "m16 16 4 4M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0",
    chevron: "m9 6 6 6-6 6",
    sun: "M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1 1m12 12 1 1M5 19l1-1M18 6l1-1M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0",
    pause: "M8 5v14M16 5v14",
  };
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.65"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={paths[name]} />
    </svg>
  );
}
