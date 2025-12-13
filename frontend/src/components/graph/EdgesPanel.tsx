"use client";

import React from "react";
import { layoutStyles, panelStyles } from "./styles";

export function EdgesPanel({
  showRequires,
  showRecommended,
  showRelated,
  onChangeRequires,
  onChangeRecommended,
  onChangeRelated,
}: {
  showRequires: boolean;
  showRecommended: boolean;
  showRelated: boolean;
  onChangeRequires: (v: boolean) => void;
  onChangeRecommended: (v: boolean) => void;
  onChangeRelated: (v: boolean) => void;
}) {
  return (
    <div style={panelStyles.section}>
      <div style={panelStyles.sectionTitle}>Edges</div>

      <label style={panelStyles.labelRow}>
        <input type="checkbox" checked={showRequires} onChange={(e) => onChangeRequires(e.target.checked)} />
        requires
      </label>

      <label style={panelStyles.labelRow}>
        <input
          type="checkbox"
          checked={showRecommended}
          onChange={(e) => onChangeRecommended(e.target.checked)}
        />
        recommended
      </label>

      <label style={panelStyles.labelRow}>
        <input type="checkbox" checked={showRelated} onChange={(e) => onChangeRelated(e.target.checked)} />
        related
      </label>
    </div>
  );
}
