from __future__ import annotations

from fastapi.middleware.cors import CORSMiddleware
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_session
from .models import Node, Edge, RelatedEdge
from .schemas import GraphOut, NodeOut, EdgeOut, RelatedOut, NodeCreateIn, NodeCreateOut
from .seed import seed_minimal


app = FastAPI(title="SkillTree MVP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"ok": True}


@app.post("/api/admin/seed")
async def admin_seed(session: AsyncSession = Depends(get_session)):
    # MVP: no auth; delete later
    await seed_minimal(session)
    return {"seeded": True}


@app.get("/api/graph", response_model=GraphOut)
async def get_graph(session: AsyncSession = Depends(get_session)):
    nodes = (await session.execute(select(Node))).scalars().all()
    edges = (await session.execute(select(Edge))).scalars().all()
    related = (await session.execute(select(RelatedEdge))).scalars().all()

    return GraphOut(
        nodes=[NodeOut(id=n.id, slug=n.slug, title=n.title, summary=n.summary) for n in nodes],
        edges=[
            EdgeOut(id=e.id, source=e.src_id, target=e.dst_id, type=e.type.value, rank=e.rank)
            for e in edges
        ],
        related=[RelatedOut(a=r.a_id, b=r.b_id) for r in related],
    )


@app.post("/api/nodes", response_model=NodeOut, status_code=201)
async def create_node(payload: NodeCreateIn, session: AsyncSession = Depends(get_session)):
    slug = payload.slug.strip()
    title = payload.title.strip()
    summary = payload.summary.strip() if payload.summary else None

    if not slug or not title:
        raise HTTPException(status_code=400, detail="slug and title are required")

    n = Node(slug=slug, title=title, summary=summary)
    session.add(n)

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        # slug unique constraint is the likely cause
        raise HTTPException(status_code=409, detail="slug already exists")

    await session.refresh(n)
    return NodeOut(id=n.id, slug=n.slug, title=n.title, summary=n.summary)
