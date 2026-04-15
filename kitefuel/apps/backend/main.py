from fastapi import FastAPI

from routes.attestations import router as attestations_router
from routes.tasks import router as tasks_router

app = FastAPI(
    title="KiteFuel API",
    version="0.1.0",
    description="Escrow-first programmable credit primitive for AI agents.",
)

app.include_router(tasks_router)
app.include_router(attestations_router)


@app.get("/health", tags=["health"])
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "kitefuel-backend"}
