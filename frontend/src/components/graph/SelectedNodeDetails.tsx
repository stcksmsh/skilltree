"use client";

import React from "react";
import type { NodeOut } from "@/components/graphView/GraphView";
import { selectionStyles } from "./styles";

export function SelectedNodeDetails({ selected }: { selected: NodeOut | null }) {
  if (!selected) return <div style={selectionStyles.empty}>Click a node.</div>;

  return (
    <>
      <h3>{selected.title}</h3>
      <div style={selectionStyles.slug}>{selected.slug}</div>
      <div>{selected.summary || "—"}</div>
    </>
  );
}
