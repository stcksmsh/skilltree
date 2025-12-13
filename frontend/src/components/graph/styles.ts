import React from "react";

/* ---------- layout ---------- */

export const layoutStyles = {
  page: {
    display: "grid",
    gridTemplateColumns: "1fr 340px",
    height: "100vh",
  } as React.CSSProperties,

  graphPane: {
    minWidth: 0,
    position: "relative",
  } as React.CSSProperties,

  sidebar: {
    borderLeft: "1px solid #333",
    padding: 16,
    fontFamily: "sans-serif",
  } as React.CSSProperties,
};

/* ---------- toolbar ---------- */

export const toolbarStyles = {
  container: {
    position: "absolute",
    top: 12,
    left: 12,
    zIndex: 10,
    display: "flex",
    gap: 8,
    padding: 8,
    border: "1px solid #333",
    borderRadius: 8,
    background: "rgba(0,0,0,0.6)",
    backdropFilter: "blur(6px)",
    fontFamily: "sans-serif",
    fontSize: 12,
  } as React.CSSProperties,
};

/* ---------- panels ---------- */

export const panelStyles = {
  section: {
    marginTop: 12,
  } as React.CSSProperties,

  sectionTitle: {
    fontSize: 12,
    opacity: 0.8,
    marginBottom: 8,
  } as React.CSSProperties,

  labelRow: {
    display: "flex",
    gap: 8,
    alignItems: "center",
    fontSize: 12,
  } as React.CSSProperties,

  subtleText: {
    fontSize: 11,
    opacity: 0.7,
  } as React.CSSProperties,
};

/* ---------- legend ---------- */

export const legendStyles = {
  container: {
    marginTop: 12,
    fontSize: 12,
    opacity: 0.85,
    lineHeight: 1.5,
  } as React.CSSProperties,
};

/* ---------- selection ---------- */

export const selectionStyles = {
  empty: {
    opacity: 0.8,
  } as React.CSSProperties,

  slug: {
    opacity: 0.7,
    fontSize: 12,
    marginBottom: 10,
  } as React.CSSProperties,
};

/* ---------- misc ---------- */

export const dividerStyle = {
  margin: "16px 0",
  opacity: 0.2,
} as React.CSSProperties;

export const errorStyle = {
  whiteSpace: "pre-wrap",
  marginTop: 12,
  color: "tomato",
} as React.CSSProperties;
