import asyncio
import os
from services.routing_engine import _fetch_google_route, _fetch_mapbox_route, _fetch_osrm_route
from services.quota_guard import QuotaGuard

async def test_all_providers():
    pune_lat, pune_lon = 18.5204, 73.8567
    nagpur_lat, nagpur_lon = 21.1458, 79.0882

    print("--- 1. Testing Mapbox Directions ---")
    try:
        coords, dist, dur, steps = await _fetch_mapbox_route(pune_lat, pune_lon, nagpur_lat, nagpur_lon)
        print(f"[OK] Mapbox: {dist:.1f} km, {dur:.2f} hrs, {len(coords)} points")
    except Exception as e:
        print(f"[FAIL] Mapbox: {e}")

    print("\n--- 2. Testing Google Maps Directions ---")
    try:
        coords, dist, dur, steps = await _fetch_google_route(pune_lat, pune_lon, nagpur_lat, nagpur_lon)
        print(f"[OK] Google Maps: {dist:.1f} km, {dur:.2f} hrs, {len(coords)} points")
    except Exception as e:
        print(f"[FAIL] Google Maps: {e}")

    print("\n--- 3. Testing Local OSRM Fallback ---")
    try:
        coords, dist, dur, steps = await _fetch_osrm_route(pune_lat, pune_lon, nagpur_lat, nagpur_lon)
        print(f"[OK] OSRM: {dist:.1f} km, {dur:.2f} hrs, {len(coords)} points")
    except Exception as e:
        print(f"[FAIL] OSRM: {e}")

    print("\n--- 4. Quota Guard Status ---")
    print(QuotaGuard.get_usage_summary())

asyncio.run(test_all_providers())
