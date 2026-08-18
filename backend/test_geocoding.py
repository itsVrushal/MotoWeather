import asyncio
from services.geocoding_engine import search_places
from services.quota_guard import QuotaGuard

async def test_geo():
    print("Testing Geocoding: 'Pune'...")
    res_pune = await search_places("Pune")
    print(f"Results: {len(res_pune)}")
    for r in res_pune[:3]:
        print(f"  [{r['provider']}] {r['name']} ({r['lat']}, {r['lon']})")

    print("\nTesting Geocoding: 'Nagpur Zero Mile'...")
    res_nagpur = await search_places("Nagpur Zero Mile")
    print(f"Results: {len(res_nagpur)}")
    for r in res_nagpur[:3]:
        print(f"  [{r['provider']}] {r['name']} ({r['lat']}, {r['lon']})")

    print("\nQuota Usage:")
    print(QuotaGuard.get_usage_summary())

asyncio.run(test_geo())
