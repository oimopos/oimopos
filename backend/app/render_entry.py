"""Same-origin cloud entry point; local Compose continues using app.main."""
import os
from pathlib import Path
from urllib.parse import urlsplit

from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles


def configure_environment():
    for key, minimum in (("DATABASE_URL", 1), ("EMPLOYEE_PIN_KEY", 32), ("PLATFORM_INITIAL_PASSWORD", 16)):
        value = os.environ.get(key, "")
        if len(value) < minimum or value == "ChangeMe-Platform-2026":
            raise RuntimeError(f"Set a valid {key} in the service environment")
    if os.environ.get("SESSION_COOKIE_SECURE", "").lower() != "true":
        raise RuntimeError("SESSION_COOKIE_SECURE must be true")
    origins = [v.strip().rstrip("/") for v in os.environ.get("CORS_ORIGINS", "").split(",") if v.strip()]
    external = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
    if external:
        origins.append(external)
    if not origins or any(urlsplit(v).scheme != "https" or not urlsplit(v).netloc or urlsplit(v).path for v in origins):
        raise RuntimeError("Configure HTTPS origins using RENDER_EXTERNAL_URL or CORS_ORIGINS")
    os.environ["CORS_ORIGINS"] = ",".join(dict.fromkeys(origins))


configure_environment()
from .main import app  # noqa: E402


@app.middleware("http")
async def cloud_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store" if request.url.path.startswith(("/api/", "/health")) or request.url.path.endswith(".html") else "no-cache"
    return response


@app.get("/", include_in_schema=False)
def home():
    return RedirectResponse("/login.html")


app.mount("/", StaticFiles(directory=Path(__file__).resolve().parents[1] / "public", html=True), name="frontend")
