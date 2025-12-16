import type cytoscape from "cytoscape";
import type { AbstractNodeOut } from "@/components/graphView/types";

export function installGraphEvents(opts: {
  cy: cytoscape.Core;
  onSelect: (n: AbstractNodeOut | null) => void;
  restoreAll: () => void;
  highlightSelected: (id: string) => void;
  shouldHighlight: () => boolean;
}) {
  const { cy, onSelect, restoreAll, highlightSelected, shouldHighlight } = opts;

  // node click
  cy.on("tap", "node", (evt) => {
    cy.$("node").unselect();
    evt.target.select();

    const d = evt.target.data();
    const node: AbstractNodeOut = {
      id: d.id,
      slug: d.slug,
      title: d.title,
      short_title: d.short_title,
      summary: d.summary,
      body_md: d.body_md,
      kind: d.kind,
      parent_id: d.parent_id,
      has_children: d.has_children,
      has_variants: d.has_variants,
      default_impl_id: d.default_impl_id,
      impls: d.impls,
    };
    onSelect(node);

    console.log("[tap] node", d.id, "highlight?", shouldHighlight());

    if (shouldHighlight()) {
      restoreAll();
      highlightSelected(d.id);
    }
  });

  // background click
  cy.on("tap", (evt) => {
    if (evt.target !== cy) return;

    cy.$("node").unselect();
    onSelect(null);

    // if highlight mode is on, still restore visuals on deselect
    restoreAll();

    console.log("[tap] background -> cleared selection");
  });
}
