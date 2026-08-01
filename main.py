"""
Routes Microservice - CS361 Small Pool (Microservice A)
Map Questers: Kevin McDougal, Suvam Patel

Runs as a standalone HTTP service. Consumers call it over REST/HTTP and receive
JSON. Nothing in this file is imported by consumers, and this file imports
nothing from any consumer's main program.

Endpoints:
    GET /geocode?address=<string>
    GET /route?start=<lat,lon>&end=<lat,lon>[&costing=auto|bicycle|pedestrian]
    GET /health

Run:
    uvicorn main:app --port 8001 --reload
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
VALHALLA_URL = os.getenv("VALHALLA_URL", "http://localhost:8002")
ENGINE_TIMEOUT = float(os.getenv("ENGINE_TIMEOUT", "8.0"))

VALID_COSTINGS = {"auto", "bicycle", "pedestrian"}

app = FastAPI(title="Routes Microservice", version="1.0.0")


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


def decode_polyline(encoded: str, precision: int = 6) -> list[list[float]]:
    """Decode an encoded polyline into [[lat, lon], ...].

    NOTE: Valhalla encodes shapes at precision 6 (1e-6), not the Google
    default of 5 (1e-5). Using 5 here silently produces coordinates off the
    coast of Africa, so the factor is explicit.
    """
    factor = float(10**precision)
    coordinates: list[list[float]] = []
    index = 0
    lat = 0
    lon = 0
    length = len(encoded)

    while index < length:
        for is_longitude in (False, True):
            result = 0
            shift = 0
            while True:
                byte = ord(encoded[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else result >> 1
            if is_longitude:
                lon += delta
            else:
                lat += delta
        coordinates.append([round(lat / factor, 6), round(lon / factor, 6)])

    return coordinates


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


# ---------------------------------------------------------------------------
# User Stories 2 and 3: Get Route Path / Get Route Distance and Duration
# ---------------------------------------------------------------------------
@app.get("/route")
async def route(
    start: str = Query(default="", description="Start coordinate as 'lat,lon'"),
    end: str = Query(default="", description="End coordinate as 'lat,lon'"),
    costing: str = Query(default="auto", description="auto | bicycle | pedestrian"),
):
    if not start.strip() or not end.strip():
        return error(400, "missing_parameter", "Parameters 'start' and 'end' are both required.")

    try:
        start_lat, start_lon = parse_coordinate(start, "start")
        end_lat, end_lon = parse_coordinate(end, "end")
    except ValueError as exc:
        # No partial route is returned - the request stops here.
        return error(400, "invalid_coordinate", str(exc))

    if costing not in VALID_COSTINGS:
        return error(
            400,
            "invalid_costing",
            f"Parameter 'costing' must be one of: {', '.join(sorted(VALID_COSTINGS))}.",
        )

    payload = {
        "locations": [
            {"lat": start_lat, "lon": start_lon},
            {"lat": end_lat, "lon": end_lon},
        ],
        "costing": costing,
        "directions_options": {"units": "kilometers"},
    }

    try:
        async with httpx.AsyncClient(timeout=ENGINE_TIMEOUT) as client:
            resp = await client.post(f"{VALHALLA_URL}/route", json=payload)
    except httpx.HTTPError as exc:
        return error(502, "routing_engine_unavailable", f"Could not reach the routing engine: {exc}")

    if resp.status_code != 200:
        return error(404, "no_route_found", "The routing engine could not build a route between those points.")

    trip = resp.json().get("trip", {})
    legs = trip.get("legs", [])
    summary = trip.get("summary", {})
    if not legs:
        return error(404, "no_route_found", "The routing engine returned no route legs.")

    geometry: list[list[float]] = []
    for leg in legs:
        points = decode_polyline(leg.get("shape", ""), precision=6)
        # Drop the duplicated join point between consecutive legs.
        geometry.extend(points[1:] if geometry else points)

    return {
        "start": [start_lat, start_lon],
        "end": [end_lat, end_lon],
        "costing": costing,
        "distance_meters": round(summary.get("length", 0.0) * 1000),
        "duration_seconds": round(summary.get("time", 0.0)),
        "geometry": geometry,
    }


# ---------------------------------------------------------------------------
# Convenience endpoint - not part of the communication contract
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    status = {"service": "ok", "nominatim": "unknown", "valhalla": "unknown"}
    async with httpx.AsyncClient(timeout=3.0) as client:
        for name, url in (("nominatim", f"{NOMINATIM_URL}/status"), ("valhalla", f"{VALHALLA_URL}/status")):
            try:
                r = await client.get(url)
                status[name] = "ok" if r.status_code < 500 else f"http {r.status_code}"
            except httpx.HTTPError:
                status[name] = "unreachable"
    return status
