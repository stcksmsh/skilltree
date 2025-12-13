"use client";

import React from "react";
import { API_BASE } from "@/lib/api";
import type { NodeOut } from "@/components/graphView/GraphView";

import { Legend } from "./Legend";
import { EdgesPanel } from "./EdgesPanel";
import { NewNodePanel } from "./NewNodePanel";
import { SelectionPanel } from "./SelectionPanel";
import { SelectedNodeDetails } from "./SelectedNodeDetails";

import {
  layoutStyles,
  dividerStyle,
  errorStyle,
} from "./styles";

export function Sidebar({
  error,
  onReseed,

  showRequires,
  showRecommended,
  showRelated,
  onChangeRequires,
  onChangeRecommended,
  onChangeRelated,

  creating,
  newTitle,
  newSlug,
  newSummary,
  onToggleNew,
  onChangeNewTitle,
  onChangeNewSlug,
  onChangeNewSummary,
  onCreateNode,

  highlightPrereqs,
  onToggleHighlightPrereqs,
  onClearSelection,

  selected,
}: {
  error: string | null;
  onReseed: () => Promise<void>;

  showRequires: boolean;
  showRecommended: boolean;
  showRelated: boolean;
  onChangeRequires: (v: boolean) => void;
  onChangeRecommended: (v: boolean) => void;
  onChangeRelated: (v: boolean) => void;

  creating: boolean;
  newTitle: string;
  newSlug: string;
  newSummary: string;
  onToggleNew: () => void;
  onChangeNewTitle: (v: string) => void;
  onChangeNewSlug: (v: string) => void;
  onChangeNewSummary: (v: string) => void;
  onCreateNode: () => void;

  highlightPrereqs: boolean;
  onToggleHighlightPrereqs: (v: boolean) => void;
  onClearSelection: () => void;

  selected: NodeOut | null;
}) {
  return (
    <aside style={layoutStyles.sidebar}>
      <Legend />

      <EdgesPanel
        showRequires={showRequires}
        showRecommended={showRecommended}
        showRelated={showRelated}
        onChangeRequires={onChangeRequires}
        onChangeRecommended={onChangeRecommended}
        onChangeRelated={onChangeRelated}
      />

      <NewNodePanel
        creating={creating}
        newTitle={newTitle}
        newSlug={newSlug}
        newSummary={newSummary}
        onToggle={onToggleNew}
        onChangeTitle={onChangeNewTitle}
        onChangeSlug={onChangeNewSlug}
        onChangeSummary={onChangeNewSummary}
        onCreate={onCreateNode}
      />

      <SelectionPanel
        highlightPrereqs={highlightPrereqs}
        onToggleHighlightPrereqs={onToggleHighlightPrereqs}
        onClearSelection={onClearSelection}
        selected={selected}
      />

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginTop: 12 }}>
        <h2 style={{ margin: 0 }}>Library of Alexandria</h2>
        <button onClick={onReseed}>Reseed</button>
      </div>

      <div style={{ opacity: 0.7, marginTop: 6, fontSize: 12 }}>API: {API_BASE}</div>

      {error && (
        <pre style={errorStyle}>
          {error}
        </pre>
      )}

      <hr style={dividerStyle} />

      <SelectedNodeDetails selected={selected} />
    </aside>
  );
}
