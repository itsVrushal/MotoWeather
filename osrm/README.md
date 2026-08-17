# OSRM Local Setup — Maharashtra

This file guides you through running OSRM locally via Docker for Maharashtra routing.
**One-time setup. Takes about 10–15 minutes.**

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- ~2 GB free disk space (for the OSM data + OSRM graph)

---

## Step 1 — Download Maharashtra OSM Data

```powershell
# Create a data directory inside osrm/
mkdir data

# Download Maharashtra extract from Geofabrik (~150–200 MB)
Invoke-WebRequest `
  -Uri "https://download.geofabrik.de/asia/india/maharashtra-latest.osm.pbf" `
  -OutFile "data\maharashtra-latest.osm.pbf"
```

---

## Step 2 — Pre-process the Data (One-time)

These three commands prepare the routing graph. Run them in order from the `osrm/` directory.

```powershell
# 2a — Extract (parse OSM data with the car profile)
docker run --rm -t -v "${PWD}/data:/data" `
  ghcr.io/project-osrm/osrm-backend `
  osrm-extract -p /opt/car.lua /data/maharashtra-latest.osm.pbf

# 2b — Partition (multi-level Dijkstra partitioning)
docker run --rm -t -v "${PWD}/data:/data" `
  ghcr.io/project-osrm/osrm-backend `
  osrm-partition /data/maharashtra-latest.osrm

# 2c — Customize (precompute route weights)
docker run --rm -t -v "${PWD}/data:/data" `
  ghcr.io/project-osrm/osrm-backend `
  osrm-customize /data/maharashtra-latest.osrm
```

> ⚠️ Step 2a can take 5–10 minutes and uses significant RAM (~2 GB peak).
> Steps 2b and 2c are faster.

---

## Step 3 — Start the OSRM Server

```powershell
# Run OSRM routing server on port 5000
docker run --rm -t -p 5000:5000 -v "${PWD}/data:/data" `
  ghcr.io/project-osrm/osrm-backend `
  osrm-routed --algorithm mld /data/maharashtra-latest.osrm
```

Keep this terminal open while developing. OSRM is now listening at `http://localhost:5000`.

---

## Step 4 — Verify

```powershell
# Test: Pune to Nashik route
Invoke-RestMethod "http://localhost:5000/route/v1/driving/73.8567,18.5204;73.7898,19.9975?overview=false"
```

You should see a JSON response with `"code": "Ok"` and a `routes` array.

---

## Notes

- You only need to do Steps 1–2 once. Step 3 is run every time you want to develop.
- To update the map data, re-download the `.osm.pbf` file and repeat Steps 2–3.
- The server handles routing **only within Maharashtra**. Cross-state routes will fail gracefully with an error message from the backend.
- For future Go migration: OSRM's HTTP API is language-agnostic — the Go backend will call the same `localhost:5000` endpoint.
