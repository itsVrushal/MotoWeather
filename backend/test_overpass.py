"""Verify the pitstops service end-to-end using Nominatim"""
import asyncio
import sys
sys.path.insert(0, '.')

from algorithms.fsm import PitstopTrigger, TriggerType
from datetime import datetime
from services.pitstops import resolve_pitstops

async def main():
    # Simulate 2 fuel triggers along Pune-Nagpur highway
    triggers = [
        PitstopTrigger(
            trigger_type=TriggerType.FUEL,
            search_lat=19.876, search_lon=75.343,  # ~270km mark near Aurangabad
            at_waypoint_index=10,
            eta=datetime(2026, 8, 17, 5, 0),
        ),
        PitstopTrigger(
            trigger_type=TriggerType.FUEL,
            search_lat=20.7, search_lon=77.0,  # ~540km mark
            at_waypoint_index=21,
            eta=datetime(2026, 8, 17, 9, 0),
        ),
        PitstopTrigger(
            trigger_type=TriggerType.FOOD,
            search_lat=20.0, search_lon=76.0,
            at_waypoint_index=15,
            eta=datetime(2026, 8, 17, 8, 0),
        ),
    ]

    print(f"Resolving {len(triggers)} triggers via Nominatim...")
    results = await resolve_pitstops(triggers)
    print(f"\nFound {len(results)} pitstops:")
    for r in results:
        print(f"  [{r.trigger.trigger_type.value}] {r.name}  @ ({r.lat:.4f},{r.lon:.4f})  {r.dist_from_query_km:.1f}km off route")

asyncio.run(main())
