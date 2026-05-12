from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import Base, engine
import models  # noqa: F401 — registers all ORM classes with Base.metadata
from routes.agent import router as agent_router
from routes.attestations import router as attestations_router
from routes.tasks import router as tasks_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Safety net: create any tables that alembic may have missed
    Base.metadata.create_all(bind=engine, checkfirst=True)
    yield


app = FastAPI(
    title="KiteFuel API",
    version="0.1.0",
    description="Escrow-first programmable credit primitive for AI agents.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tasks_router)
app.include_router(attestations_router)
app.include_router(agent_router)


@app.get("/health", tags=["health"])
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "kitefuel-backend"}
