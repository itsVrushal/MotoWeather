import asyncio
import httpx
from algorithms.fsm import PitstopTrigger, TriggerType
from services.pitstops import resolve_pitstops, _resolve_one

async def test_ev_triggers():
    # Let's test EV charging search near 270km and 540km on Pune -> Nagpur
    # Waypoint 1: ~270km (Aurangabad/Jalna area)
    t1 = PitstopTrigger(
        trigger_type=TriggerType.FUEL,
        search_lat=19.876,
        search_lon=75.343,
        at_waypoint_index=11,
        eta=None,
        vehicle_type="ev",
        route_dist_from_last_stop_km=270,
    )
    # Waypoint 2: ~540km (Karanja / Wardha / Amravati stretch)
    t2 = PitstopTrigger(
        trigger_type=TriggerType.FUEL,
        search_lat=20.70,
        search_lon=77.50,
        at_waypoint_index=22,
        eta=None,
        vehicle_type="ev",
        route_dist_from_last_stop_km=270,
    )
    # Waypoint 3: Another point along Samruddhi Mahamarg / NH around Wardha
    t3 = PitstopTrigger(
        trigger_type=TriggerType.FUEL,
        search_lat=20.74,
        search_lon=78.60,
        at_waypoint_index=26,
        eta=None,
        vehicle_type="ev",
        route_dist_from_last_stop_km=270,
    )

    async with httpx.AsyncClient() as client:
        print("Testing t1 (Aurangabad)...")
        r1 = await _resolve_one(t1, client)
        print("t1 result:", r1)
        
        print("\nTesting t2 (Karanja/Amravati)...")
        r2 = await _resolve_one(t2, client)
        print("t2 result:", r2)

        print("\nTesting t3 (Wardha)...")
        r3 = await _resolve_one(t3, client)
        print("t3 result:", r3)

asyncio.run(test_ev_triggers())
