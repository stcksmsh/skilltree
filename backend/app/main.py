from __future__ import annotations

from fastapi.middleware.cors import CORSMiddleware
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_session
from .seed import seed_minimal

from .routes.graph_router import router as graph_router


app = FastAPI(title="SkillTree MVP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
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


@app.post("/api/nodes", status_code=503)
async def create_node(payload: NodeCreateIn, session: AsyncSession = Depends(get_session)):
    return HTTPException(status_code=503, detail="Not implemented yet")


app.include_router(graph_router)