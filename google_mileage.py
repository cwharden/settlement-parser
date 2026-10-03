"""
Google Routes API mileage lookup.

HOW TO USE:
Paste get_driving_miles() into your app (or import it, same as
rate_calculator_tab.py), then call it like:

    miles = get_driving_miles("Hiram, GA", "Blythewood, SC", api_key)
    if miles is not None:
        st.write(f"{miles:.1f} miles")
    else:
        st.error("Couldn't get a route for those two locations.")

The api_key comes from Streamlit secrets:
    api_key = st.secrets["GOOGLE_MAPS_API_KEY"]

This returns ONE number: total driving miles between two points.
It does NOT split miles by state yet — that's the next, harder piece,
and deliberately left for later so this part can be tested on its own
first.
"""

import requests


def get_driving_miles(origin: str, destination: str, api_key: str):
    """
    Look up driving distance between two addresses using Google's Routes API.

    origin / destination: plain text, e.g. "Hiram, GA" or a full street address
    api_key: your Google Maps API key (restricted to Routes API)

    Returns: distance in miles (float), or None if the lookup failed
    (bad address, no route found, network error, etc.)
    """
    if not origin.strip() or not destination.strip():
        return None

    url = "https://routes.googleapis.com/directions/v2:computeRoutes"

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        # fieldMask limits what Google sends back — keeps the response
        # small and keeps us from accidentally paying for extra data
        "X-Goog-FieldMask": "routes.distanceMeters,routes.duration",
    }

    body = {
        "origin": {"address": origin},
        "destination": {"address": destination},
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_UNAWARE",
        "units": "IMPERIAL",
    }

    try:
        response = requests.post(url, headers=headers, json=body, timeout=10)
        response.raise_for_status()
        data = response.json()

        routes = data.get("routes")
        if not routes:
            return None

        meters = routes[0].get("distanceMeters")
        if meters is None:
            return None

        miles = meters / 1609.344
        return round(miles, 1)

    except requests.exceptions.RequestException:
        # Network error, bad key, Google service issue, etc.
        return None
    except (KeyError, IndexError, ValueError):
        # Unexpected response shape
        return None


# ---------- Quick manual test (not part of the app) ----------
if __name__ == "__main__":
    import os
    test_key = os.environ.get("GOOGLE_MAPS_API_KEY", "PASTE_KEY_HERE_TO_TEST")
    result = get_driving_miles("Hiram, GA", "Blythewood, SC", test_key)
    print(f"Hiram, GA -> Blythewood, SC: {result} miles")
    # His old spreadsheet showed 258.08 miles for this exact route —
    # a real run here should land close to that number.
