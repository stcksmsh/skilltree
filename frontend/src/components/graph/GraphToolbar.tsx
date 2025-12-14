"use client";

import React from "react";
import type { Core } from "cytoscape";
import { VIEW_ANIM } from "./constants";
import { toolbarStyles } from "./styles";

export function GraphToolbar({
  cyRef,
  selectedId,
}: {
  cyRef: React.RefObject<Core | null>;
  selectedId: string | null;
}) {
  return (
    <div
      style={toolbarStyles.container}
    >
      <button
        onClick={() => {
          const cy = cyRef.current;
          if (!cy) return;

          const visible = cy.elements(":visible");
          cy.animate(
            { fit: { eles: visible, padding: VIEW_ANIM.fit.padding } },
            { duration: VIEW_ANIM.fit.duration, easing: VIEW_ANIM.easing }
          );
        }}
      >
        Fit
      </button>

      <button
        onClick={() => {
          const cy = cyRef.current;
          if (!cy) return;

          const next = cy.zoom() * VIEW_ANIM.zoom.factor;
          cy.animate(
            { zoom: next, pan: { x: cy.width() / 2, y: cy.height() / 2 } },
            { duration: VIEW_ANIM.zoom.duration, easing: VIEW_ANIM.easing }
          );
        }}
      >
        +
      </button>

      <button
        onClick={() => {
          const cy = cyRef.current;
          if (!cy) return;

          const next = cy.zoom() / VIEW_ANIM.zoom.factor;
          cy.animate(
            { zoom: next, pan: { x: cy.width() / 2, y: cy.height() / 2 } },
            { duration: VIEW_ANIM.zoom.duration, easing: VIEW_ANIM.easing }
          );
        }}
      >
        -
      </button>

      <button
        onClick={() => {
          const cy = cyRef.current;
          if (!cy) return;

          const layout = cy.layout({
            name: "breadthfirst",
            directed: true,
            padding: VIEW_ANIM.layout.padding,
            animate: true,
            animationDuration: VIEW_ANIM.layout.duration,
            animationEasing: VIEW_ANIM.easing,
            spacingFactor: 1.5,
            nodeDimensionsIncludeLabels: true,
            grid: true,
          });

          layout.run();

          layout.one("layoutstop", () => {
            const visible = cy.elements(":visible");
            cy.animate(
              { fit: { eles: visible, padding: VIEW_ANIM.fit.padding } },
              { duration: VIEW_ANIM.layout.fitDuration, easing: VIEW_ANIM.easing }
            );
          });
        }}
      >
        Re-layout
      </button>

      <button
        onClick={() => {
          const cy = cyRef.current;
          if (!cy) return;

          const ANIM = { duration: VIEW_ANIM.center.duration, easing: VIEW_ANIM.easing };

          if (selectedId) {
            const el = cy.getElementById(selectedId);
            if (!el.empty()) {
              cy.animate({ center: { eles: el } }, ANIM);
            }
            return;
          }

          const visible = cy.elements(":visible");
          if (visible.nonempty()) {
            cy.animate(
              { fit: { eles: visible, padding: VIEW_ANIM.center.paddingIfNoSelection } },
              ANIM
            );
          }
        }}
      >
        Center
      </button>
    </div>
  );
}
