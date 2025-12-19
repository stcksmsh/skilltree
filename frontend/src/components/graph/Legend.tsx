"use client";

import React from "react";
import { legendStyles } from "./styles";

export function Legend() {
  return (
    <div style={legendStyles.container}>
      <div>
        <strong>Legend</strong>
      </div>
      <div>→ solid arrow: requires</div>
      <div>→ dashed arrow: recommended</div>
      <div>→ dotted line: related</div>
    </div>
  );
}
