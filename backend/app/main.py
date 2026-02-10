from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import engine, Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(title="fibenchi", lifespan=lifespan)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
