"""
Geocoding Microservice - CS361 Small Pool (Microservice 1)
Map Questers: Kevin McDougal, Suvam Patel

Runs as a standalone HTTP service. Consumers call it over REST/HTTP and receive
JSON. Nothing in this file is imported by consumers, and this file imports
nothing from any consumer's main program.

Endpoints:
    GET /geocode?address=<string>

Run:
    uvicorn geocoding_service:app --port 8001 --reload
"""


import os
import time

import httpx
from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse

# ---------------------------------------------------------------------------
# Configuration - the two routing/geocoding engines this service calls.
# Override with environment variables if your Docker ports differ.
# ---------------------------------------------------------------------------
NOMINATIM_URL = os.getenv("NOMINATIM_URL", "http://localhost:8080")
ENGINE_TIMEOUT = float(os.getenv("ENGINE_TIMEOUT", "8.0"))

app = FastAPI(title="Geocoding Microservice", version="1.0.0")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def error(status: int, code: str, message: str) -> JSONResponse:
    """Every failure leaves through here, so consumers can branch on status
    code alone and always find an `error` field in the body."""
    return JSONResponse(status_code=status, content={"error": code, "message": message})


def parse_coordinate(raw: str, name: str) -> tuple[float, float]:
    """Parse a 'lat,lon' string. Raises ValueError with a consumer-facing message."""
    parts = [p.strip() for p in raw.split(",")]
    if len(parts) != 2:
        raise ValueError(f"Parameter '{name}' must be formatted as 'lat,lon'.")
    try:
        lat, lon = float(parts[0]), float(parts[1])
    except ValueError:
        raise ValueError(f"Parameter '{name}' must contain two numbers, e.g. '33.9737,-117.3281'.")
    if not -90.0 <= lat <= 90.0:
        raise ValueError(f"Latitude in '{name}' must be between -90 and 90.")
    if not -180.0 <= lon <= 180.0:
        raise ValueError(f"Longitude in '{name}' must be between -180 and 180.")
    return lat, lon



@app.middleware("http")
async def log_elapsed(request: Request, call_next):
    """Prints elapsed milliseconds per request. Used to demonstrate the
    Responsiveness non-functional requirement (< 3000 ms) on camera."""
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000
    print(f"[routes-ms] {request.method} {request.url.path} -> "
          f"{response.status_code} in {elapsed_ms:.0f} ms")
    response.headers["X-Elapsed-Ms"] = f"{elapsed_ms:.0f}"
    return response


# ---------------------------------------------------------------------------
# User Story 1: Get Geographical Coordinates
# ---------------------------------------------------------------------------
@app.get("/geocode")
async def geocode(address: str = Query(default="", description="Free-form street address")):
    if not address.strip():
        return error(400, "address_required", "Parameter 'address' is required and must not be blank.")

    try:
        async with httpx.AsyncClient(timeout=ENGINE_TIMEOUT) as client:
            resp = await client.get(
                f"{NOMINATIM_URL}/search",
                params={"q": address, "format": "json", "limit": 1, "addressdetails": 0},
                headers={"User-Agent": "cs361-routes-microservice/1.0"},
            )
    except httpx.HTTPError as exc:
        return error(502, "geocoder_unavailable", f"Could not reach the geocoding engine: {exc}")

    if resp.status_code != 200:
        return error(502, "geocoder_error", f"Geocoding engine returned status {resp.status_code}.")

    matches = resp.json()
    if not matches:
        return error(404, "address_not_found", f"No coordinates could be found for '{address}'.")

    top = matches[0]
    return {
        "query": address,
        "matched_address": top.get("display_name", address),
        "lat": round(float(top["lat"]), 6),
        "lon": round(float(top["lon"]), 6),
    }

