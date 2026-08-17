import asyncio
from datetime import datetime
from routers.route import calculate_route, calculate_pitstops
from models.schemas import RouteRequest, PitstopRequest

async def test_full_pipeline():
    req = RouteRequest(
        start_address="Pune, Maharashtra",
        end_address="Nagpur, Maharashtra",
        start_lat=18.5204,
        start_lon=73.8567,
        end_lat=21.1458,
        end_lon=79.0882,
        preferred_departure=datetime(2026, 8, 17, 13, 30),
        avg_speed_kmh=60.0,
        tank_range_km=300.0,
        window_minutes=90,
    )
    print("--- 1. Testing calculate_route ---")
    resp = await calculate_route(req)
    print(f"Total distance: {resp.total_distance_km} km, Duration: {resp.estimated_duration_hours} hrs")
    print("\nHighways on route:")
    for hw in resp.briefing.highways:
        print(f"  - {hw.name}: {hw.distance_km} km ({hw.pct}%)")
    
    print("\nDaylight analysis:")
    if resp.briefing.daylight:
        print(f"  {resp.briefing.daylight.advisory}")

    print("\nHazards detected:")
    for h in resp.briefing.hazard_segments:
        print(f"  - [{h.title}] {h.stretch_km}: {h.description}")

    print("\n--- 2. Testing calculate_pitstops (EV mode, 300km range) ---")
    pit_req = PitstopRequest(
        waypoints=resp.waypoints,
        vehicle_type="ev",
        tank_range_km=300.0,
        pitstop_buffer_km=15.0,
    )
    pit_resp = await calculate_pitstops(pit_req)
    print(f"Total pitstops resolved: {len(pit_resp.pitstops)}")
    for line in pit_resp.pitstop_summary:
        print(f"  {line}")

asyncio.run(test_full_pipeline())
