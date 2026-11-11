import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import DEFAULT_DB_PATH, init_db
from app.routes import router


def create_app(db_path=None):
    path = str(db_path or os.environ.get("ISSUE_TRACKER_DB", DEFAULT_DB_PATH))

    @asynccontextmanager
    async def lifespan(app):
        init_db(path)
        yield

    app = FastAPI(title="Mini Issue Tracker", lifespan=lifespan)
    app.state.db_path = path
    app.include_router(router)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()