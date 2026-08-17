Here are the 3 commands you need to run the app. You can run these in three separate terminal/PowerShell windows:

### 1. OSRM Routing Server (Docker)
This runs the OSRM backend on port 5000 using the Western Zone data we processed.
```powershell
docker run --name osrm-server -d -p 5000:5000 -v "d:/git reps/Motomaps/osrm/data:/data" ghcr.io/project-osrm/osrm-backend osrm-routed --algorithm mld /data/western-zone-260814.osrm
```
*(Note: I already started this for you in the background earlier, so it might still be running. If it says the name `osrm-server` is in use, you're good to go!)*

### 2. Python FastAPI Backend
This runs the orchestration and weather API server on port 8000.
```powershell
cd "d:\git reps\Motomaps\backend"
python -m uvicorn main:app --reload --port 8000
```

### 3. SvelteKit Frontend
This runs the UI dashboard on port 5173.
```powershell
cd "d:\git reps\Motomaps\frontend"
npm run dev
```

Once all three are running, just open **http://localhost:5173** in your browser to plan your ride! Let me know if you hit any errors.