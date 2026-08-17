# Moto-Weather Router
**Project Blueprint & Architecture Brief**
*A purely deterministic, algorithm-driven routing and weather intelligence application for motorcycle riders.*

## 1. The Core Concept
A web application that takes a starting point and destination, calculates the route, and samples spatiotemporal weather data along the journey. Instead of generic weather forecasts, the system uses strict mathematical optimization to recommend the best departure time and intelligently identifies pitstops (fuel, breakfast, rain shelters) based on rider-specific constraints and live API data.

**Key Philosophy:** 100% deterministic logic. No LLMs, no generative AI text, no unpredictable API costs. Rule-based finite state machines and optimization algorithms power the core engine.

## 2. Architecture & Tech Stack
* **Frontend:** React, Vite, Tailwind CSS. Focus on a clean, high-contrast dashboard suitable for quick mobile viewing.
* **Backend:** Python (FastAPI). Lightweight, fast execution, excellent for spatial and mathematical operations.
* **Routing Engine:** OSRM (Open Source Routing Machine) or Mapbox Directions API for base polyline generation.
* **Weather API:** Open-Meteo (Free, no-key, high-resolution hourly data).
* **POI Data:** Overpass API (OpenStreetMap) for querying fuel, cafes, and shelters.

## 3. Algorithmic Logic Breakdown

### A. Departure Time Optimizer (Sliding Window Algorithm)
The system evaluates departure times in 15-minute increments (e.g., a 3-hour search window). For each potential departure time $t$, it calculates a Total Hazard Score $S(t)$:

$$S(t) = w_r \times R(t) + w_w \times W(t) + w_d \times D(t)$$

* $R(t)$: Accumulated precipitation probability along waypoints at calculated ETAs.
* $W(t)$: Maximum wind speed encountered on the route.
* $D(t)$: Time penalty representing the absolute difference from the rider's preferred departure time.
* $w$: Assigned weights prioritizing rain avoidance over time delays.

The optimal departure time is the mathematical minimum of $S(t)$.

### B. Spatiotemporal Route Sampling
The routing engine returns a high-density polyline. The backend applies a Haversine distance algorithm to sample waypoints at regular intervals (e.g., every 25 km).

For each sampled point $P_i$, the Expected Time of Arrival is calculated:

$$ETA(P_i) = \text{Departure Time} + \frac{\text{Cumulative Distance}(P_i)}{\text{Average Speed}}$$

The backend then batches queries to Open-Meteo to fetch weather exactly at coordinate $P_i$ for hour $ETA(P_i)$.

### C. Pitstop Constraint Solver (Finite State Machine)
Overpass API queries are triggered strictly by rider constraints and environmental hazards, applying a spatial buffer to the route polyline.

* **Fuel Trigger:** If $\text{Distance Since Fuel} \ge (\text{Tank Range} - 30\text{km}) \rightarrow$ Search `amenity=fuel` ahead.
* **Food Trigger:** If $08:00 \le ETA(P_i) \le 09:30 \rightarrow$ Search `amenity=cafe` along that segment.
* **Rain Shelter Trigger:** If $\text{Rain Prob}(P_i) > 60\% \rightarrow$ Search `amenity=shelter` at the preceding waypoint $P_{i-1}$.

## 4. The "Learn With Me" Content Strategy
This deterministic approach provides excellent technical hooks for a YouTube devlog:
* **The Setup:** Explain the math behind the $S(t)$ cost function. Visually graph why leaving at 7:30 AM is safer than 7:00 AM.
* **The Build:** Show the Python implementation of the Haversine sampling and the Overpass API query structuring.
* **The Payoff:** Demonstrate the UI ingesting the mathematical output, mapping the color-coded weather route, and dynamically rendering the deterministic text briefing.
