import asyncio
import httpx

async def test_food_and_chill():
    async with httpx.AsyncClient() as client:
        spots = [
            ("Shikrapur / Shirur (Near Pune)", 18.82, 74.37),
            ("Ahmednagar bypass", 19.10, 74.75),
            ("Aurangabad / Jalna junction", 19.87, 75.80),
            ("Mehkar / Lonar stretch", 20.15, 76.57),
            ("Karanja / Amravati stretch", 20.48, 77.48),
            ("Wardha / Butibori", 20.80, 78.85),
        ]
        
        for name, lat, lon in spots:
            print(f"\n--- Checking {name} ({lat}, {lon}) ---")
            url = "https://nominatim.openstreetmap.org/search"
            params = {
                "amenity": "restaurant",
                "format": "json",
                "limit": 3,
                "countrycodes": "in",
                "viewbox": f"{lon-0.2},{lat-0.2},{lon+0.2},{lat+0.2}",
                "bounded": 1,
            }
            r = await client.get(url, params=params, headers={"User-Agent": "MotoWeather/2.0"}, timeout=10.0)
            res = r.json()
            print(f"  Restaurants found: {len(res)}")
            for item in res:
                name_clean = item.get('display_name').split(',')[0]
                print(f"    Food: {name_clean} @ {item.get('lat')},{item.get('lon')}")
                
            await asyncio.sleep(1.1)

asyncio.run(test_food_and_chill())
