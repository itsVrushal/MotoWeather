import asyncio
from datetime import datetime, timedelta
import httpx

from services.routing_engine import get_unified_route
from algorithms.haversine import sample_route, compute_eta
from services.weather import fetch_weather_batch

async def analyze_weather_windows():
    # Pune -> Nagpur
    start_lat, start_lon = 18.5204, 73.8567
    end_lat, end_lon = 21.1458, 79.0882
    user_dep = datetime(2026, 8, 18, 13, 44)
    avg_speed_kmh = 60.0

    print(f"Fetching route for Pune -> Nagpur...")
    coords, total_dist, dur, steps, cong, alerts, prov = await get_unified_route(start_lat, start_lon, end_lat, end_lon)
    sampled = sample_route(coords, interval_km=25.0)
    sampled_coords = [(wp.lat, wp.lon) for wp in sampled]
    cumulative_kms = [wp.cumulative_km for wp in sampled]
    print(f"Sampled {len(sampled_coords)} waypoints along {total_dist:.1f} km.")

    # Let's test candidate departures across a 12-hour window: from 05:00 AM to 08:00 PM in 30-min steps
    candidates = []
    base_date = user_dep.date()
    for h in range(5, 23):
        for m in (0, 30):
            candidates.append(datetime(base_date.year, base_date.month, base_date.day, h, m))

    print("\n--- HOURLY CANDIDATE DEPARTURE ANALYSIS ---")
    print(f"{'Departure':<10} | {'Avg Rain%':<10} | {'Max Rain%':<10} | {'Max Wind':<9} | {'Max Temp':<9} | {'Daylight hrs':<13} | {'Night hrs':<10} | {'Traffic Delay'}")
    print("-" * 95)

    results = []
    for cand in candidates:
        etas = [compute_eta(cand, km, avg_speed_kmh) for km in cumulative_kms]
        weather = await fetch_weather_batch(sampled_coords, etas)

        precips = [w.precip_pct for w in weather]
        winds = [w.wind_kmh for w in weather]
        temps = [w.temp_c for w in weather]

        avg_rain = sum(precips) / len(precips)
        max_rain = max(precips)
        max_wind = max(winds)
        max_temp = max(temps)

        # Daylight calculation
        total_hours = total_dist / avg_speed_kmh
        total_mins = int(total_hours * 60)
        day_mins = sum(15 for m in range(0, total_mins, 15) if 6.25 <= (cand + timedelta(minutes=m)).hour + (cand + timedelta(minutes=m)).minute/60.0 <= 18.75)
        night_mins = total_mins - day_mins
        day_hrs = day_mins / 60.0
        night_hrs = night_mins / 60.0

        # Traffic
        hr = cand.hour + cand.minute / 60.0
        is_rush = (8.5 <= hr <= 10.5) or (17.5 <= hr <= 20.5)
        traffic_str = "RUSH HOUR" if is_rush else "Clear"

        results.append({
            "dep": cand,
            "avg_rain": avg_rain,
            "max_rain": max_rain,
            "max_wind": max_wind,
            "max_temp": max_temp,
            "day_hrs": day_hrs,
            "night_hrs": night_hrs,
            "traffic": traffic_str,
        })

        time_str = cand.strftime("%I:%M %p")
        print(f"{time_str:<10} | {avg_rain:<10.1f} | {max_rain:<10.1f} | {max_wind:<9.1f} | {max_temp:<9.1f} | {day_hrs:<13.1f} | {night_hrs:<10.1f} | {traffic_str}")

asyncio.run(analyze_weather_windows())
