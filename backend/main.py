"""App entry point. Shared file: it only wires the routers together.

Run from the repo root:  uvicorn backend.main:app --reload
"""

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

from backend.ai_core import router as ai_core_router  # noqa: E402
from backend.sourcing import router as sourcing_router  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

app = FastAPI(title="Brand DNA")


@app.exception_handler(RequestValidationError)
async def invalid_request(request, exc):
    # Keep the error shape from AGENTS.md instead of FastAPI's default {"detail": …}
    first = exc.errors()[0]
    where = ".".join(str(part) for part in first["loc"])
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "invalid_request", "message": f"{where}: {first['msg']}"}},
    )


app.include_router(sourcing_router)
app.include_router(ai_core_router)

# Mounted last so /api/* routes win over static files.
app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True), name="frontend")
