import asyncio
import httpx

async def test_trip_features():
    async with httpx.AsyncClient() as client:
        # Check Express Food plazas / Highway Rest Areas / Attractions along Pune-Nagpur corridor
        # Points: 
        # 1. Lonar Crater / Lake area (~350km)
        # 2. Samruddhi Mahamarg Rest Plazas / Wayside Amenities
        # 3. Scenic / Tourist spots
        
        spots = [
            ("Lonar Lake", 19.97, 76.51),
            ("Aurangabad / Caves / Heritage", 19.87, 75.34),
            ("Jalna / Sindkhed Raja", 19.96, 75.88),
            ("Samruddhi Mahamarg Waypoint", 20.30, 77.00),
        ]
        
        print("--- Testing Tourism / Attractions & Viewpoints ---")
        for name, lat, lon in spots:
            url = "https://nominatim.openstreetmap.org/search"
            # Tourist attractions / viewpoints / rest areas
            params = {
                "q": "attraction",
                "format": "json",
                "limit": 3,
                "countrycodes": "in",
                "viewbox": f"{lon-0.3},{lat-0.3},{lon+0.3},{lat+0.3}",
                "bounded": 1,
            }
            r = await client.get(url, params=params, headers={"User-Agent": "MotoWeather/2.0"}, timeout=10.0)
            res = r.json()
            print(f"[{name}] Attractions found: {len(res)}")
            for item in res:
                print(f"   -> {item.get('display_name')[:70]}")
            await asyncio.sleep(1.1)

asyncio.run(test_trip_features())
