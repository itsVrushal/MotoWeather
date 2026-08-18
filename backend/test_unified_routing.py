import asyncio
from services.routing_engine import get_unified_route
from services.quota_guard import QuotaGuard

async def test_routing():
    print("Testing Pune -> Nagpur route via unified engine...")
    coords, dist, dur, steps, provider = await get_unified_route(
        18.5204, 73.8567, 21.1458, 79.0882
    )
    print(f"Provider used: {provider.upper()}")
    print(f"Distance: {dist:.2f} km | Duration: {dur:.2f} hrs | Points: {len(coords)}")
    print(f"Highway Steps found: {len(steps)}")
    for s in steps[:5]:
        print(f"  - {s['name']}: {s['distance_km']:.1f} km")

    print("\nQuota Summary:")
    print(QuotaGuard.get_usage_summary())

asyncio.run(test_routing())
