"use client";

import React from "react";
import type { NodeOut } from "@/components/graphView/types";
import { panelStyles } from "./styles";

export function SelectionPanel({
  highlightPrereqs,
  onToggleHighlightPrereqs,
  onClearSelection,
  selected,
}: {
  highlightPrereqs: boolean;
  onToggleHighlightPrereqs: (v: boolean) => void;
  onClearSelection: () => void;
  selected: NodeOut | null;
}) {
  return (
    <div style={panelStyles.section}>
      <div style={panelStyles.sectionTitle}>Selection</div>

      <label style={panelStyles.labelRow}>
        <input
          type="checkbox"
          checked={highlightPrereqs}
          onChange={(e) => onToggleHighlightPrereqs(e.target.checked)}
        />
        highlight prerequisites (requires)
      </label>

      <button
        style={{ marginTop: 8 }}
        onClick={onClearSelection}
        disabled={!selected && !highlightPrereqs}
      >
        Clear selection
      </button>
    </div>
  );
}
