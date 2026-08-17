import asyncio
import httpx

async def test_osrm_steps():
    # Pune to Nagpur coordinates
    # Pune: 18.52, 73.85
    # Nagpur: 21.14, 79.08
    coords = "73.85,18.52;79.08,21.14"
    url = f"http://localhost:5000/route/v1/driving/{coords}"
    params = {
        "overview": "full",
        "geometries": "geojson",
        "steps": "true",
    }
    async with httpx.AsyncClient() as client:
        r = await client.get(url, params=params, timeout=10.0)
        data = r.json()
        routes = data.get("routes", [])
        if routes:
            legs = routes[0].get("legs", [])
            print(f"Total distance: {routes[0]['distance']/1000:.1f} km, Duration: {routes[0]['duration']/3600:.1f} hrs")
            highways = {}
            for leg in legs:
                for step in leg.get("steps", []):
                    name = step.get("name", "").strip() or "Local Road"
                    dist_km = step.get("distance", 0) / 1000.0
                    highways[name] = highways.get(name, 0.0) + dist_km
            
            # Sort top highways by distance
            sorted_hw = sorted(highways.items(), key=lambda x: x[1], reverse=True)
            print("\nTop Highways & Roads on Route:")
            for name, dist in sorted_hw[:8]:
                print(f"  - {name}: {dist:.1f} km")

asyncio.run(test_osrm_steps())
