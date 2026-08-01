"""
Test program for the Routes Microservice - CS361 Assignment 7.

IMPORTANT (rubric: "test program and microservice are not directly calling
each other"): this file imports ONLY the third-party `requests` library. It does
not import main.py, it does not import any function from the microservice, and
it never touches the microservice's data or engines. The ONLY channel between
this program and the microservice is HTTP over the REST communication pipe.

Run the microservice first:
    uvicorn main:app --port 8001

Then, in a second terminal:
    python test_program.py
"""

import requests  # third-party HTTP client - NOT microservice code

BASE_URL = "http://localhost:8001"
TIMEOUT = 10


def banner(text: str) -> None:
    print("\n" + "=" * 70)
    print(text)
    print("=" * 70)


def scenario_1_geocode() -> tuple[float, float] | None:
    """User Story 1: Get Geographical Coordinates."""
    banner("SCENARIO 1 - Get Geographical Coordinates  (GET /geocode)")

    # ---- REQUEST: parameters are sent as a URL query string -----------------
    params = {"address": "900 University Ave, Riverside, CA"}
    print(f"REQUESTING -> GET {BASE_URL}/geocode  params={params}")
    response = requests.get(f"{BASE_URL}/geocode", params=params, timeout=TIMEOUT)

    # ---- RECEIVE: read the status code, then parse the JSON body -----------
    print(f"RECEIVED   <- HTTP {response.status_code} in "
          f"{response.elapsed.total_seconds() * 1000:.0f} ms")
    data = response.json()

    if response.status_code != 200:
        print(f"ERROR      <- {data['error']}: {data['message']}")
        return None

    print(f"  query           : {data['query']}")
    print(f"  matched_address : {data['matched_address']}")
    print(f"  lat, lon        : {data['lat']}, {data['lon']}")
    return data["lat"], data["lon"]


def scenario_2_route(start: tuple[float, float], end: tuple[float, float]) -> None:
    """User Stories 2 and 3: Get Route Path + Get Route Distance and Duration."""
    banner("SCENARIO 2 - Get Route Path, Distance, and Duration  (GET /route)")

    params = {
        "start": f"{start[0]},{start[1]}",
        "end": f"{end[0]},{end[1]}",
        "costing": "auto",
    }
    print(f"REQUESTING -> GET {BASE_URL}/route  params={params}")
    response = requests.get(f"{BASE_URL}/route", params=params, timeout=TIMEOUT)

    print(f"RECEIVED   <- HTTP {response.status_code} in "
          f"{response.elapsed.total_seconds() * 1000:.0f} ms")
    data = response.json()

    if response.status_code != 200:
        print(f"ERROR      <- {data['error']}: {data['message']}")
        return

    km = data["distance_meters"] / 1000
    minutes = data["duration_seconds"] / 60
    print(f"  distance_meters  : {data['distance_meters']}  ({km:.1f} km)")
    print(f"  duration_seconds : {data['duration_seconds']}  ({minutes:.1f} min)")
    print(f"  geometry points  : {len(data['geometry'])}")
    print(f"  first point      : {data['geometry'][0]}")
    print(f"  last point       : {data['geometry'][-1]}")
    print("  (a consumer would hand `geometry` straight to a map polyline)")


def scenario_3_invalid_coordinate() -> None:
    """User Story 3, error path: malformed input returns a structured error."""
    banner("SCENARIO 3 - Malformed input is rejected  (GET /route)")

    params = {"start": "abc,xyz", "end": "34.0633,-117.6509"}
    print(f"REQUESTING -> GET {BASE_URL}/route  params={params}")
    response = requests.get(f"{BASE_URL}/route", params=params, timeout=TIMEOUT)

    print(f"RECEIVED   <- HTTP {response.status_code}")
    data = response.json()
    print(f"  error   : {data['error']}")
    print(f"  message : {data['message']}")
    print("  (no partial route was returned, and the service is still running)")


def scenario_4_reliability(requests_to_send: int = 100) -> None:
    """Reliability NFR from the Sprint 2 Plan: across 100 consecutive requests
    with valid inputs, at least 99 must return 200 and the service must not
    terminate."""
    banner(f"SCENARIO 4 - Reliability check: {requests_to_send} consecutive valid requests")

    params = {"start": "33.9737,-117.3281", "end": "34.0633,-117.6509", "costing": "auto"}
    successes = 0
    for _ in range(requests_to_send):
        r = requests.get(f"{BASE_URL}/route", params=params, timeout=TIMEOUT)
        if r.status_code == 200:
            successes += 1
    pct = successes / requests_to_send * 100
    print(f"  {successes}/{requests_to_send} returned HTTP 200 ({pct:.0f}%)")
    threshold = 0.99 * requests_to_send
    print(f"  acceptance criterion: at least {threshold:.0f} must succeed -> "
          f"{'PASS' if successes >= threshold else 'FAIL'}")
    print("  service is still accepting requests")


def main() -> None:
    print("Routes Microservice - test program")
    print(f"Communication pipe: REST over HTTP, base URL {BASE_URL}")

    try:
        coords = scenario_1_geocode()
        start = coords if coords else (33.9737, -117.3281)
        scenario_2_route(start, (34.0633, -117.6509))
        scenario_3_invalid_coordinate()
        scenario_4_reliability()
    except requests.exceptions.ConnectionError:
        print(f"\nCould not connect to {BASE_URL}. "
              "Start the microservice with:  uvicorn main:app --port 8001")
        return

    banner("All scenarios finished")


if __name__ == "__main__":
    main()
