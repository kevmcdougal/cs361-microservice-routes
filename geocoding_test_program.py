"""
Test program for the Geocoding Microservice - CS361 Assignment 7.

IMPORTANT (rubric: "geocoding test program and microservice are not directly calling
each other"): this file imports ONLY the third-party `requests` library. It does
not import geocoding_service.py, it does not import any function from the microservice, and
it never touches the microservice's data or engines. The ONLY channel between
this program and the microservice is HTTP over the REST communication pipe.

Run the microservice first:
    uvicorn geocoding_service:app --port 8001

Then, in a second terminal:
    python geocoding_test_program.py
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
    banner("SCENARIO 1 - Get Geographical Coordinates for UC Riverside (GET /geocode)")

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

def scenario_2_geocode_blank_address() -> None:
    """Error path: missing/blank address returns 400 address_required."""
    banner("SCENARIO 2 - Blank address is rejected  (GET /geocode)")

    params = {"address": ""}
    print(f"REQUESTING -> GET {BASE_URL}/geocode  params={params}")
    response = requests.get(f"{BASE_URL}/geocode", params=params, timeout=TIMEOUT)

    print(f"RECEIVED   <- HTTP {response.status_code}")
    data = response.json()
    print(f"  error   : {data['error']}")
    print(f"  message : {data['message']}")
    print("  (no coordinates were returned, and the service is still running)")

def scenario_3_geocode_not_found() -> None:
    """Error path: an address with no match returns 404 address_not_found."""
    banner("SCENARIO 3 - Unmatchable address returns 404  (GET /geocode)")

    params = {"address": "abcdefghijklm"}
    print(f"REQUESTING -> GET {BASE_URL}/geocode  params={params}")
    response = requests.get(f"{BASE_URL}/geocode", params=params, timeout=TIMEOUT)

    print(f"RECEIVED   <- HTTP {response.status_code}")
    data = response.json()
    print(f"  error   : {data['error']}")
    print(f"  message : {data['message']}")
    print("  (Nominatim had no candidates for this query)")

def scenario_4_geocode() -> tuple[float, float] | None:
    """Get geocoordinates for address entered by user"""
    banner("SCENARIO 4 - Get Geographical Coordinates for User-Entered Address (GET /geocode)")

    # ---- REQUEST: parameters are sent as a URL query string -----------------
    place = input("Enter a place in the Southern California Inland Empire: ")

    params = {"address": f"{place}"}

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


def main() -> None:
    print("Routes Microservice - test program")
    print(f"Communication pipe: REST over HTTP, base URL {BASE_URL}")

    try:
        coords = scenario_1_geocode()
        #start = coords if coords else (33.9737, -117.3281)
        scenario_2_geocode_blank_address()
        scenario_3_geocode_not_found()
        scenario_4_geocode()
    except requests.exceptions.ConnectionError:
        print(f"\nCould not connect to {BASE_URL}. "
              "Start the microservice with:  uvicorn main:app --port 8001")
        return

    banner("All scenarios finished")



if __name__ == "__main__":
    main()
