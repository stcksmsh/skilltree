"use client";

import React, { useMemo } from "react";
import type { GraphOut } from "@/components/graphView/types";

type Props = {
  graph: GraphOut;
  onJump: (groupId: string) => void;
};

const panelStyle: React.CSSProperties = {
  position: "absolute",
  left: 14,
  top: 58, // below toolbar
  zIndex: 20,
  width: 260,
  maxHeight: "70vh",
  overflow: "auto",
  borderRadius: 14,
  padding: 12,
  background: "rgba(18, 18, 18, 0.85)",
  border: "1px solid rgba(255,255,255,0.08)",
  boxShadow: "0 10px 30px rgba(0,0,0,0.35)",
  backdropFilter: "blur(10px)",
};

const titleRowStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "baseline",
  justifyContent: "space-between",
  marginBottom: 10,
};

const titleStyle: React.CSSProperties = {
  margin: 0,
  fontSize: 13,
  fontWeight: 600,
  opacity: 0.95,
};

const subtitleStyle: React.CSSProperties = {
  margin: 0,
  fontSize: 11,
  opacity: 0.6,
};

const sectionStyle: React.CSSProperties = {
  marginTop: 10,
};

const sectionHeaderStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  marginBottom: 6,
};

const sectionTitleStyle: React.CSSProperties = {
  fontSize: 11,
  letterSpacing: 0.4,
  textTransform: "uppercase",
  opacity: 0.7,
  margin: 0,
};

const dividerStyle: React.CSSProperties = {
  marginTop: 12,
  marginBottom: 8,
  border: "none",
  borderTop: "1px solid rgba(255,255,255,0.08)",
};

const blockTitleStyle: React.CSSProperties = {
  margin: 0,
  marginTop: 2,
  fontSize: 12,
  fontWeight: 700,
  opacity: 0.92,
};

const blockSubtitleStyle: React.CSSProperties = {
  margin: 0,
  marginTop: 2,
  fontSize: 11,
  opacity: 0.55,
};

const badgeStyle = (kind: "requires" | "recommended"): React.CSSProperties => ({
  fontSize: 10,
  padding: "2px 8px",
  borderRadius: 999,
  border: "1px solid rgba(255,255,255,0.12)",
  opacity: 0.85,
  ...(kind === "requires"
    ? { background: "rgba(255, 90, 90, 0.10)" }
    : { background: "rgba(90, 160, 255, 0.10)" }),
});

const itemStyle = (kind: "requires" | "recommended"): React.CSSProperties => ({
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: 10,
  width: "100%",
  borderRadius: 12,
  padding: "8px 10px",
  marginBottom: 6,
  cursor: "pointer",
  userSelect: "none",
  background: "rgba(255,255,255,0.04)",
  border: "1px solid rgba(255,255,255,0.06)",
  transition: "transform 120ms ease, background 120ms ease, border 120ms ease",
  ...(kind === "requires"
    ? { borderLeft: "3px solid rgba(255, 90, 90, 0.55)" }
    : { borderLeft: "3px solid rgba(90, 160, 255, 0.55)" }),
});

const itemLeftStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 2,
  minWidth: 0,
};

const itemTitleStyle: React.CSSProperties = {
  fontSize: 13,
  fontWeight: 600,
  margin: 0,
  lineHeight: 1.1,
  whiteSpace: "nowrap",
  overflow: "hidden",
  textOverflow: "ellipsis",
};

const itemMetaStyle: React.CSSProperties = {
  fontSize: 11,
  margin: 0,
  opacity: 0.65,
  whiteSpace: "nowrap",
  overflow: "hidden",
  textOverflow: "ellipsis",
};

const countStyle: React.CSSProperties = {
  fontSize: 12,
  opacity: 0.8,
  fontVariantNumeric: "tabular-nums",
  padding: "2px 8px",
  borderRadius: 999,
  background: "rgba(255,255,255,0.06)",
  border: "1px solid rgba(255,255,255,0.08)",
};

type Hint = NonNullable<GraphOut["boundary_hints"]>[number];

function groupByType(items: Hint[]) {
  const req = items.filter((h) => h.type === "requires").sort((a, b) => b.count - a.count);
  const rec = items.filter((h) => h.type === "recommended").sort((a, b) => b.count - a.count);
  return { req, rec };
}

export function BoundaryPanel({ graph, onJump }: Props) {
  const hints = graph.boundary_hints ?? [];
  if (!hints.length) return null;

  const grouped = useMemo(() => {
    const dependsOn = hints.filter((h) => h.direction === "depends_on");
    const usedBy = hints.filter((h) => h.direction === "used_by");
    return {
      dependsOn: groupByType(dependsOn),
      usedBy: groupByType(usedBy),
      totalDependsOn: dependsOn.length,
      totalUsedBy: usedBy.length,
    };
  }, [hints]);

  const renderSection = (
    label: string,
    kind: "requires" | "recommended",
    items: Hint[]
  ) => {
    if (!items.length) return null;

    return (
      <div style={sectionStyle}>
        <div style={sectionHeaderStyle}>
          <p style={sectionTitleStyle}>{label}</p>
          <span style={badgeStyle(kind)}>{items.length}</span>
        </div>

        {items.map((h) => (
          <div
            key={`${h.group_id}-${h.type}-${h.direction}`}
            style={itemStyle(kind)}
            onClick={() => onJump(h.group_id)}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLDivElement).style.background = "rgba(255,255,255,0.07)";
              (e.currentTarget as HTMLDivElement).style.border = "1px solid rgba(255,255,255,0.12)";
              (e.currentTarget as HTMLDivElement).style.transform = "translateY(-1px)";
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLDivElement).style.background = "rgba(255,255,255,0.04)";
              (e.currentTarget as HTMLDivElement).style.border = "1px solid rgba(255,255,255,0.06)";
              (e.currentTarget as HTMLDivElement).style.transform = "translateY(0px)";
            }}
            title={`Jump to ${h.title}`}
          >
            <div style={itemLeftStyle}>
              <p style={itemTitleStyle}>{h.short_title}</p>
              <p style={itemMetaStyle}>{h.title}</p>
            </div>
            <div style={countStyle}>{h.count}</div>
          </div>
        ))}
      </div>
    );
  };

  const renderBlock = (
    title: string,
    subtitle: string,
    block: { req: Hint[]; rec: Hint[] },
    totalCount: number
  ) => {
    if (totalCount === 0) return null;

    return (
      <div>
        <p style={blockTitleStyle}>{title}</p>
        <p style={blockSubtitleStyle}>{subtitle}</p>
        {renderSection("Requires", "requires", block.req)}
        {renderSection("Recommended", "recommended", block.rec)}
      </div>
    );
  };

  return (
    <div style={panelStyle}>
      <div style={titleRowStyle}>
        <p style={titleStyle}>Boundary</p>
        <p style={subtitleStyle}>outside current focus</p>
      </div>

      {renderBlock(
        "Depends on",
        "external prerequisites for this focus",
        grouped.dependsOn,
        grouped.totalDependsOn
      )}

      {(grouped.totalDependsOn > 0 && grouped.totalUsedBy > 0) && <hr style={dividerStyle} />}

      {renderBlock(
        "Used by",
        "external areas that depend on this focus",
        grouped.usedBy,
        grouped.totalUsedBy
      )}
    </div>
  );
}
