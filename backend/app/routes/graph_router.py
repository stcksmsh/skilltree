from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..schemas import GraphOut
from ..services.graph_focus import build_focus_graph
from ..services.graph import build_graph


router = APIRouter(prefix="/api/graph", tags=["graph"])


@router.get("/", response_model=GraphOut)
async def get_graph(
    session: AsyncSession = Depends(get_session),
):
    return await build_graph(session=session)


@router.get("/focus/{abstract_id}", response_model=GraphOut)
async def get_graph_focus(
    abstract_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    return await build_focus_graph(session=session, focus_abstract_id=abstract_id)
