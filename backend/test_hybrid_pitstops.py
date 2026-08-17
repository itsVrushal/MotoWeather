import asyncio
from datetime import datetime
from routers.route import calculate_route, calculate_pitstops
from models.schemas import RouteRequest, PitstopRequest

async def test_hybrid():
    req = RouteRequest(
        start_address="Pune, Maharashtra",
        end_address="Nagpur, Maharashtra",
        start_lat=18.5204,
        start_lon=73.8567,
        end_lat=21.1458,
        end_lon=79.0882,
        preferred_departure=datetime(2026, 8, 17, 16, 30),
        avg_speed_kmh=60.0,
        tank_range_km=300.0,
        window_minutes=90,
    )
    resp = await calculate_route(req)
    print("--- Testing EV Pitstops ---")
    pit_req_ev = PitstopRequest(
        waypoints=resp.waypoints,
        vehicle_type="ev",
        tank_range_km=300.0,
        pitstop_buffer_km=15.0,
    )
    pit_resp_ev = await calculate_pitstops(pit_req_ev)
    print(f"EV Pitstops found: {len(pit_resp_ev.pitstops)}")
    for line in pit_resp_ev.pitstop_summary:
        print(f"  {line.encode('ascii', 'ignore').decode()}")

    print("\n--- Testing Petrol Pitstops ---")
    pit_req_petrol = PitstopRequest(
        waypoints=resp.waypoints,
        vehicle_type="petrol",
        tank_range_km=300.0,
        pitstop_buffer_km=15.0,
    )
    pit_resp_petrol = await calculate_pitstops(pit_req_petrol)
    print(f"Petrol Pitstops found: {len(pit_resp_petrol.pitstops)}")
    for line in pit_resp_petrol.pitstop_summary:
        print(f"  {line.encode('ascii', 'ignore').decode()}")

asyncio.run(test_hybrid())
