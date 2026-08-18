# 🏍️ MotoWeather Maharashtra Ride Planner

Intelligent Motorcycle & Car Highway Route Planner with Real-time Weather, Daylight Analysis, and Multi-Provider Routing (Mapbox & Google Maps).

---

## 🚀 Quick Start Guide

### 1. Python FastAPI Backend (Port 8000)
Runs the route optimization, weather briefing, and Dual API routing engine:
```powershell
cd "d:\git reps\Motomaps\backend"
python -m uvicorn main:app --reload --port 8000
```

### 2. SvelteKit Frontend (Port 5173)
Runs the dashboard and MapLibre visual cockpit:
```powershell
cd "d:\git reps\Motomaps\frontend"
npm run dev
```

### 3. Optional Local OSRM Server (Offline Routing)
If you want to route 100% offline without external APIs, run the local OSRM Docker container:
```powershell
docker run --name osrm-server -d -p 5000:5000 -v "d:/git reps/Motomaps/osrm/data:/data" ghcr.io/project-osrm/osrm-backend osrm-routed --algorithm mld /data/western-zone-260814.osrm
```

---

## ⚙️ Multi-Provider Routing & Zero-Billing Protection

You can toggle the routing engine in [`backend/.env`](backend/.env):
```env
# Options: 'hybrid' (Mapbox -> Google -> OSRM), 'mapbox', 'google', 'osrm'
ROUTING_PROVIDER=hybrid

# API Keys
MAPBOX_ACCESS_TOKEN=sk.eyJ1I...
GOOGLE_MAPS_API_KEY=AIzaSy...

# Monthly Free Tier Hard Quotas (Circuit-Breakers set at ~90% of free limit)
MAPBOX_MONTHLY_LIMIT=90000
GOOGLE_MONTHLY_LIMIT=8500
```
- **Mapbox Directions API v5:** Primary routing (100,000 free requests/mo).
- **Google Maps Directions API:** Automatic failover.
- **Quota Guard:** Internal SQLite tracking prevents any accidental credit card charges.