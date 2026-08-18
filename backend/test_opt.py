import asyncio
from datetime import datetime
from services.routing_engine import get_unified_route
from algorithms.haversine import sample_route, compute_eta
from services.weather import fetch_weather_batch
from services.optimizer import find_optimal_departure

async def test_opt():
    coords, dist, dur, steps, cong, alerts, prov = await get_unified_route(18.5204, 73.8567, 21.1458, 79.0882)
    sampled = sample_route(coords, interval_km=25.0)
    sampled_coords = [(wp.lat, wp.lon) for wp in sampled]
    cumulative_kms = [wp.cumulative_km for wp in sampled]
    user_dep = datetime(2026, 8, 18, 13, 44)

    # 4 hour window (240 min)
    opt_time, scores = await find_optimal_departure(
        preferred_departure=user_dep,
        window_minutes=240,
        step_minutes=30,
        sampled_coords=sampled_coords,
        avg_speed_kmh=60.0,
        weather_fetcher=fetch_weather_batch,
        eta_calculator=compute_eta,
        cumulative_kms=cumulative_kms,
    )
    print(f"User Preferred: {user_dep.strftime('%I:%M %p')}")
    print(f"Optimal Found:  {opt_time.strftime('%I:%M %p')}")
    for s in scores:
        opt_mark = " <-- OPTIMAL" if s.is_optimal else ""
        print(f"{s.departure_time.strftime('%I:%M %p')}: Score {s.total_score:.4f} (Rain:{s.rain_component:.4f}, Wind:{s.wind_component:.4f}, Delay:{s.delay_component:.4f}, Traffic:{s.traffic_component:.4f}){opt_mark}")

asyncio.run(test_opt())
