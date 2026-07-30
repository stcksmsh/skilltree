---
title: The day I fought semantic zoom until it worked
date: 2025-12-20
tags: [devlog, skilltree, graph, ux]
---

Long day. Started reasonable — [added a docker-compose test stack and an actual async test harness](https://github.com/stcksmsh/skilltree/commit/e06f8864e910e079aa1ed29acba1f614688836bc) with real focus-graph tests, merged that as PR #1 (the repo's first one). Then spent the rest of the day chasing one thing: focus/drill-down navigation that doesn't jitter, doesn't lose your camera position, and doesn't show you a wrong node when you back out.

Went through several real attempts before landing on something that works: centralizing focus state so navigation and graph-loading both read from one source of truth, fixing a double-`fit()` call that was causing visible jitter on every transition, decoupling node selection from focus (selecting a node and entering focus on it turned out to be two different things pretending to be one), [fixing the baseline view rendering every node instead of just top-level ones](https://github.com/stcksmsh/skilltree/commit/8259dce8bad9d66f1b5dcb79e831fc31c2446a4c), and fixing drill-down landing on the wrong "super node." Along the way: directional boundary hints (`depends_on` vs `used_by`, instead of one undifferentiated "related" hint) and an `abstract_memberships` table with seed data to actually test hub/spoke shapes.

The thing that finally made it click: [a `GraphStage` with layered Cytoscape instances and a single camera authority](https://github.com/stcksmsh/skilltree/commit/9aa3a65731ba3094d1e567f0da0c9ef7d29757fd) — nothing else is allowed to call `fit()` mid-transition. Crossfade + dagre expansion on enter, stable camera snapshots on the way back out, one-time framing only on the initial root load. Landed late that night, then [one more pass](https://github.com/stcksmsh/skilltree/commit/5f2c93ee768582a39bfd04dfbe2dd392b56e52df) the next morning to fix back-navigation and edge visibility that broke slightly under the new layering. Whole day was basically: every fix surfaced the next inconsistency, until it didn't.
