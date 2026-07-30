---
title: Started skilltree
date: 2025-12-12
tags: [devlog, skilltree, fastapi, nextjs]
---

Wanted a graph explorer for skills/topics with actual prerequisite structure — a DAG, not a flat list. [FastAPI + Postgres + Alembic on the backend](https://github.com/stcksmsh/skilltree/commit/1d30c7ab56fea55d1a90649e8e78ccd14fb54f39), [Cytoscape.js inside Next.js on the frontend](https://github.com/stcksmsh/skilltree/commit/62b36a6d7b217d344f9aa94e15185d6d1bed7ee0), wired together same night. Basic toolbar, edge toggles, hover highlighting with a fade so the graph doesn't feel like a wall of nodes and lines the second it loads.
