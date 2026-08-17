import asyncio
import httpx

async def inspect_osm_ev():
    async with httpx.AsyncClient() as client:
        # Check around Karanja / Washim / Wardha / Amravati / Yavatmal
        coords = [
            (20.48, 77.48, "Karanja"),
            (20.74, 78.60, "Wardha"),
            (20.93, 77.75, "Amravati"),
            (20.38, 78.12, "Yavatmal"),
            (20.70, 77.00, "Akola")
        ]
        for lat, lon, name in coords:
            # Test 1: amenity=charging_station with wider box
            url = "https://nominatim.openstreetmap.org/search"
            params = {
                "amenity": "charging_station",
                "format": "json",
                "limit": 10,
                "countrycodes": "in",
                "viewbox": f"{lon-0.4},{lat-0.4},{lon+0.4},{lat+0.4}",
                "bounded": 1,
            }
            r = await client.get(url, params=params, headers={"User-Agent": "MotoWeather/2.0"}, timeout=10.0)
            res1 = r.json()
            
            # Test 2: query "EV charging" or "charging"
            params2 = {
                "q": "EV charging station",
                "format": "json",
                "limit": 10,
                "countrycodes": "in",
                "viewbox": f"{lon-0.4},{lat-0.4},{lon+0.4},{lat+0.4}",
                "bounded": 1,
            }
            r2 = await client.get(url, params=params2, headers={"User-Agent": "MotoWeather/2.0"}, timeout=10.0)
            res2 = r2.json()
            
            print(f"[{name}] amenity=charging_station: {len(res1)} results, q='EV charging station': {len(res2)} results")
            if res1:
                print("  amenity results:", [x.get('display_name')[:60] for x in res1[:2]])
            if res2:
                print("  q results:", [x.get('display_name')[:60] for x in res2[:2]])
            await asyncio.sleep(1.1)

asyncio.run(inspect_osm_ev())
