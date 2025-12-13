"use client";

import React from "react";
import { panelStyles } from "./styles";

export function NewNodePanel({
  creating,
  newTitle,
  newSlug,
  newSummary,
  onToggle,
  onChangeTitle,
  onChangeSlug,
  onChangeSummary,
  onCreate,
}: {
  creating: boolean;
  newTitle: string;
  newSlug: string;
  newSummary: string;
  onToggle: () => void;
  onChangeTitle: (v: string) => void;
  onChangeSlug: (v: string) => void;
  onChangeSummary: (v: string) => void;
  onCreate: () => void;
}) {
  return (
    <div style={panelStyles.section}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <div style={panelStyles.sectionTitle}>Nodes</div>
        <button onClick={onToggle}>{creating ? "Cancel" : "New"}</button>
      </div>

      {creating && (
        <div style={panelStyles.labelRow}>
          <input
            placeholder="title"
            value={newTitle}
            onChange={(e) => onChangeTitle(e.target.value)}
            style={{ width: "100%" }}
          />
          <input
            placeholder="slug (unique)"
            value={newSlug}
            onChange={(e) => onChangeSlug(e.target.value)}
            style={{ width: "100%" }}
          />
          <textarea
            placeholder="summary (optional)"
            value={newSummary}
            onChange={(e) => onChangeSummary(e.target.value)}
            rows={3}
            style={{ width: "100%", resize: "vertical" }}
          />
          <button onClick={onCreate} disabled={!newTitle.trim() || !newSlug.trim()}>
            Create
          </button>

          <div style={panelStyles.subtleText}>
            Tip: keep slug lowercase with dashes (e.g. linear-algebra-basics)
          </div>
        </div>
      )}
    </div>
  );
}
