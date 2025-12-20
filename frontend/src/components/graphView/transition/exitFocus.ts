import type { Core } from "cytoscape";
import type { GraphOut } from "../types";

export async function exitFocusTransition(opts: {
  childLayerKey: string;
  childCy: Core;

  parentGraph: GraphOut;
  targetCamera: { pan: { x: number; y: number }; zoom: number } | null;

  layers: any[];
  setLayers: (l: any[] | ((prev: any[]) => any[])) => void;

  cyByKeyRef: React.MutableRefObject<Map<string, Core>>;
  registerCy: (key: string, cy: Core | null) => void;

  updateCamera: (pan: { x: number; y: number }, zoom: number) => void;
  onTopReady?: (cy: Core) => void;
}) {
  const {
    childCy,
    parentGraph,
    targetCamera,
    layers,
    setLayers,
    cyByKeyRef,
    updateCamera,
    onTopReady,
  } = opts;

  const parentKey = `back-${parentGraph.root_id}-${Date.now()}`;

  // Add parent layer underneath (fading in), keep child on top (fading out)
  setLayers([
    ...layers.map((l) => ({ ...l, active: false, opacity: 1 })),
    {
      key: parentKey,
      graph: parentGraph,
      opacity: 0,
      active: true,
    },
  ]);

  const waitForCy = async (key: string, maxFrames = 120): Promise<Core | null> => {
    for (let i = 0; i < maxFrames; i++) {
      await new Promise((r) => requestAnimationFrame(r));
      const cy = cyByKeyRef.current.get(key) ?? null;
      if (cy && !cy.destroyed()) {
        const c = cy.container();
        if (c && (c as any).isConnected) return cy;
      }
    }
    return null;
  };

  const parentCy = await waitForCy(parentKey);
  if (!parentCy) return;

  // Ensure both layers share the current camera *before* animating back
  updateCamera(childCy.pan(), childCy.zoom());

  // Start a single camera animation on the child (authoritative), mirrored via updateCamera
  childCy.stop();

  const anim = childCy.animation(
    targetCamera ? { pan: targetCamera.pan, zoom: targetCamera.zoom } : { zoom: childCy.zoom() },
    {
      duration: 650,
      easing: "ease-in-out-cubic",
      step: () => updateCamera(childCy.pan(), childCy.zoom()),
    }
  );
  anim.play();

  // Crossfade: parent in, child out
  setLayers((ls: any[]) =>
    ls.map((l) => {
      if (l.key === parentKey) return { ...l, opacity: 1, active: true };
      return { ...l, opacity: 0, active: false };
    })
  );

  await anim.promise("completed");

  // Keep only the parent layer
  setLayers((ls: any[]) =>
    ls.filter((l) => l.key === parentKey).map((l) => ({ ...l, opacity: 1, active: true }))
  );

  onTopReady?.(parentCy);
}
