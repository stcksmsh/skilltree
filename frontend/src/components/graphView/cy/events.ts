import type cytoscape from "cytoscape";
import type { AbstractNodeOut } from "@/components/graphView/types";

export function installGraphEvents(opts: {
  cy: cytoscape.Core;
  onSelect: (n: AbstractNodeOut | null) => void;
  onEnterFocus: (abstractId: string) => void;
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

  // single click selects (no focus change)
  cy.on("tap", "node", (evt) => {
    cy.$("node").unselect();
    evt.target.select();

    const node = readNodeOut(evt);
    onSelect(node);

    if (shouldHighlight()) {
      restoreAll();
      highlightSelected(node.id);
    }
  });

  // double click enters focus (only if expandable)
  cy.on("dbltap", "node", (evt) => {
    const node = readNodeOut(evt);

    // only enter on groups (or anything you consider expandable)
    if (node.kind === "group" && node.has_children) {
      onEnterFocus(node.id);
    }
  });

  // background click clears selection
  cy.on("tap", (evt) => {
    if (evt.target !== cy) return;

    cy.$("node").unselect();
    onSelect(null);
    restoreAll();
  });
}
