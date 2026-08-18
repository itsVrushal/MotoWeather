import asyncio
from services.places_engine import resolve_live_amenity

async def test_places():
    # Near Jalna Interchange on Samruddhi Mahamarg (19.8655, 75.385)
    print("Searching for food near Jalna Interchange...")
    res = await resolve_live_amenity(19.8655, 75.385, "food")
    print("Result:", res)

    print("\nSearching for EV charging near Mehkar...")
    res_ev = await resolve_live_amenity(20.1521, 76.5207, "charging")
    print("EV Result:", res_ev)

asyncio.run(test_places())
