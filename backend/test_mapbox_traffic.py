import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv()
MAPBOX_TOKEN = os.getenv("MAPBOX_ACCESS_TOKEN", "").strip()

async def test_traffic():
    start_lat, start_lon = 18.5204, 73.8567
    end_lat, end_lon = 21.1458, 79.0882
    url = (
        f"https://api.mapbox.com/directions/v5/mapbox/driving-traffic/"
        f"{start_lon},{start_lat};{end_lon},{end_lat}"
    )
    params = {
        "access_token": MAPBOX_TOKEN,
        "geometries": "geojson",
        "overview": "full",
        "steps": "true",
        "annotations": "congestion,maxspeed",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(url, params=params)
        data = r.json()
        route = data["routes"][0]
        legs = route.get("legs", [])
        print("Distance:", route["distance"] / 1000.0)
        print("Duration with traffic:", route["duration"] / 3600.0)
        if legs:
            ann = legs[0].get("annotation", {})
            congestion = ann.get("congestion", [])
            print("Congestion segments count:", len(congestion))
            from collections import Counter
            print("Congestion distribution:", Counter(congestion))

asyncio.run(test_traffic())
