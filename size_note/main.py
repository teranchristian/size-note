from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from size_note import __version__
from size_note.api.router import router as api_router
from size_note.config import get_settings
from size_note.database import Database
from size_note.exceptions import DomainError
from size_note.schemas import HealthRead


def create_app(
    *, database_url: str | None = None, auto_create_schema: bool | None = None
) -> FastAPI:
    settings = get_settings()
    database = Database(database_url or settings.database_url)
    should_create_schema = (
        settings.auto_create_schema if auto_create_schema is None else auto_create_schema
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if should_create_schema:
            database.create_schema()
        yield
        database.dispose()

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description="Private size records for the people you shop for.",
        lifespan=lifespan,
    )
    app.state.database = database
    app.state.settings = settings

    @app.exception_handler(DomainError)
    async def domain_error_handler(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message, "code": exc.code},
        )

    @app.get("/health", response_model=HealthRead, tags=["system"])
    def health() -> HealthRead:
        return HealthRead(version=__version__)

    app.include_router(api_router, tags=["api"])

    from size_note.web import templates
    from size_note.web.routes import router as web_router

    app.mount(
        "/static",
        StaticFiles(directory=settings.package_dir / "static"),
        name="static",
    )
    app.state.templates = templates
    app.include_router(web_router)
    return app


app = create_app()
