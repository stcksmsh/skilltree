import type cytoscape from "cytoscape";
import type { AbstractNodeOut } from "@/components/graphView/types";

export type EnterFocusMeta = {
  fromNodeId?: string;
  fromRenderPos?: { x: number; y: number };
};

export function installGraphEvents(opts: {
  cy: cytoscape.Core;
  onSelect: (n: AbstractNodeOut | null) => void;
  onEnterFocus: (abstractId: string, meta?: EnterFocusMeta) => void;
  restoreAll: () => void;
  highlightSelected: (id: string) => void;
  shouldHighlight: () => boolean;
}) {
  const { cy, onSelect, onEnterFocus, restoreAll, highlightSelected, shouldHighlight } = opts;

  const readNodeOut = (evt: cytoscape.EventObject): AbstractNodeOut => {
    const d = evt.target.data();
    return {
      id: d.id,
      slug: d.slug,
      title: d.title,
      short_title: d.short_title,
      summary: d.summary ?? null,
      body_md: d.body_md ?? null,
      kind: d.kind,
      parent_id: d.parent_id || null,
      has_children: !!d.has_children,
      has_variants: !!d.has_variants,
      default_impl_id: d.default_impl_id || null,
      impls: d.impls ?? [],
    };
  };

  // ---- IMPORTANT: debounce tap so dbltap can cancel it
  let tapTimer: number | null = null;
  const TAP_DELAY_MS = 200;

  const clearTapTimer = () => {
    if (tapTimer != null) {
      window.clearTimeout(tapTimer);
      tapTimer = null;
    }
  };

  cy.on("tap", "node", (evt) => {
    clearTapTimer();

    // schedule "single tap" selection
    tapTimer = window.setTimeout(() => {
      tapTimer = null;

      cy.$("node").unselect();
      evt.target.select();

      const node = readNodeOut(evt);
      onSelect(node);

      if (shouldHighlight()) {
        restoreAll();
        highlightSelected(node.id);
      }
    }, TAP_DELAY_MS);
  });

  cy.on("dbltap", "node", (evt) => {
    clearTapTimer();

    const node = readNodeOut(evt);
    if (node.kind === "group" && node.has_children) {
      // optional: clear selection UI immediately for drill
      cy.$("node").unselect();
      onSelect(null);
      restoreAll();

      evt.target.addClass("exiting-focus");
      onEnterFocus(node.id, {
        fromNodeId: node.id,
        fromRenderPos: evt.target.renderedPosition()
      });
    }
  });

  cy.on("tap", (evt) => {
    if (evt.target !== cy) return;

    clearTapTimer();

    cy.$("node").unselect();
    onSelect(null);
    restoreAll();
  });
}
