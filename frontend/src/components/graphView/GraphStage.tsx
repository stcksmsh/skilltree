"use client";

import React, {
  forwardRef,
  useCallback,
  useImperativeHandle,
  useRef,
  useState,
} from "react";
import type { Core } from "cytoscape";

import type { GraphOut } from "./types";
import { GraphViewLayer } from "./GraphViewLayer";
import { enterFocusTransition } from "./transition/enterFocus";
import { exitFocusTransition } from "./transition/exitFocus";

type StageLayer = {
  key: string;
  graph: GraphOut;
  opacity: number;
  active: boolean;
};

export type GraphStageHandle = {
  /** Animate exit to the provided parent graph + (optional) target camera snapshot */
  exitFocus: (opts: {
    parentGraph: GraphOut;
    targetCamera?: { pan: { x: number; y: number }; zoom: number } | null;
  }) => Promise<void>;
};

export const GraphStage = forwardRef<
  GraphStageHandle,
  {
    graph: GraphOut;
    onEnterFocus: (id: string) => Promise<GraphOut>;
    onDidEnterFocus?: (entry: {
      id: string;
      anchorPan: { x: number; y: number };
      anchorZoom: number;
      fromNodeId?: string;
    }) => void;
    onSelect: (n: any | null) => void;
    onCyReady?: (cy: Core) => void;
    selectedId?: string | null;
    highlightPrereqs?: boolean;
  }
>(function GraphStage(
  { graph, onEnterFocus, onDidEnterFocus, onSelect, onCyReady, selectedId, highlightPrereqs },
  ref
) {
  const cameraRef = useRef<{ pan: { x: number; y: number }; zoom: number } | null>(
    null
  );

  // Layer key -> cy instance
  const cyByKeyRef = useRef<Map<string, Core>>(new Map());

  const didInitialFrameRef = useRef(false);

  const registerCy = useCallback((key: string, cy: Core | null) => {
    const map = cyByKeyRef.current;
    if (!cy) {
      map.delete(key);
      return;
    }
    map.set(key, cy);
  }, []);

  const safeApplyCamera = useCallback(
    (cy: Core | null, pan: { x: number; y: number }, zoom: number) => {
      if (!cy) return;
      if (cy.destroyed()) return;
      const c = cy.container();
      if (!c) return;
      if (!(c as any).isConnected) return;
      cy.pan(pan);
      cy.zoom(zoom);
    },
    []
  );

  const updateCamera = useCallback(
    (pan: { x: number; y: number }, zoom: number) => {
      cameraRef.current = { pan, zoom };
      for (const cy of cyByKeyRef.current.values()) {
        safeApplyCamera(cy, pan, zoom);
      }
    },
    [safeApplyCamera]
  );

  const [layers, setLayers] = useState<StageLayer[]>([
    { key: "root", graph, opacity: 1, active: true },
  ]);

  // If the `graph` prop changes (e.g. page-level focus stack changes), you can
  // choose to ignore it because GraphStage runs transitions itself.
  // For now we keep the initial root only; transitions replace layers.

  const handleEnterFocus = useCallback(
    async (groupId: string, meta?: { fromNodeId?: string; fromRenderPos?: { x: number; y: number } }) => {
      const currentTop = layers[layers.length - 1];
      const parentCy = currentTop ? cyByKeyRef.current.get(currentTop.key) ?? null : null;
      if (!parentCy || parentCy.destroyed()) return;

      const anchorPan = parentCy.pan();
      const anchorZoom = parentCy.zoom();

      onDidEnterFocus?.({
        id: groupId,
        anchorPan,
        anchorZoom,
        fromNodeId: meta?.fromNodeId ?? groupId,
      });

      const childGraph = await onEnterFocus(groupId);

      await enterFocusTransition({
        parentLayerKey: currentTop.key,
        parentCy,
        childGraph,
        layers,
        setLayers,
        cyByKeyRef,
        registerCy,
        updateCamera,
        onTopReady: (cy) => onCyReady?.(cy),
      });
    },
    [layers, onEnterFocus, onCyReady, registerCy, updateCamera]
  );

  useImperativeHandle(
    ref,
    () => ({
      exitFocus: async ({ parentGraph, targetCamera }) => {
        const currentTop = layers[layers.length - 1];
        const childCy = currentTop ? cyByKeyRef.current.get(currentTop.key) ?? null : null;
        if (!childCy || childCy.destroyed()) return;

        await exitFocusTransition({
          childLayerKey: currentTop.key,
          childCy,
          parentGraph,
          targetCamera: targetCamera ?? null,
          layers,
          setLayers,
          cyByKeyRef,
          registerCy,
          updateCamera,
          onTopReady: (cy) => onCyReady?.(cy),
        });
      },
    }),
    [layers, onCyReady, registerCy, updateCamera]
  );

  return (
    <div style={{ position: "relative", width: "100%", height: "100%" }}>
      {layers.map((l) => (
        <GraphViewLayer
          key={l.key}
          layerKey={l.key}
          graph={l.graph}
          opacity={l.opacity}
          active={l.active}
          onCyInstance={(cy) => registerCy(l.key, cy)}
          onSelect={onSelect}
          onEnterFocus={handleEnterFocus}
          onCyReady={l.active ? onCyReady : undefined}
          // Option A: one-time initial framing on first active mount only.
          initialFrame={!didInitialFrameRef.current && l.active}
          onInitialFrameDone={() => {
            didInitialFrameRef.current = true;
          }}
          selectedId={selectedId}
          highlightPrereqs={highlightPrereqs}
        />
      ))}
    </div>
  );
});
