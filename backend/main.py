"""
MVP-Sionna-WiFi: FastAPI Backend Server
Provides REST API and WebSocket for the 3D visualization frontend.
"""

import asyncio
import json
import time
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import API_HOST, API_PORT
from scene_loader import load_scene, get_scene_info
from simulation import run_simulation

app = FastAPI(
    title="MVP-Sionna-WiFi",
    description="WiFi propagation simulation using Sionna RT",
    version="0.1.0",
)

# CORS for frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global scene (loaded once at startup)
scene = None
last_simulation_result = None


@app.on_event("startup")
async def startup():
    """Load the scene at server startup."""
    global scene
    try:
        scene = load_scene()
        print("✅ Scene loaded at startup")
    except Exception as e:
        print(f"⚠️  Could not load scene: {e}")
        print("   Running in mock mode")
        scene = {"type": "mock"}


@app.get("/api/scene")
async def get_scene():
    """Get room geometry and sensor positions for 3D rendering."""
    return get_scene_info(scene)


@app.post("/api/simulate")
async def simulate(
    max_depth: Optional[int] = None,
    num_samples: Optional[int] = None,
    diffraction: Optional[bool] = None,
    heatmap_height: Optional[float] = None,
):
    """
    Run ray tracing simulation with optional parameter overrides.
    Returns paths, CIR, CSI, and coverage data.
    """
    global last_simulation_result
    
    result = run_simulation(
        scene,
        max_depth=max_depth,
        num_samples=num_samples,
        diffraction=diffraction,
        coverage_height=heatmap_height,
    )
    
    last_simulation_result = result
    return result


@app.get("/api/coverage")
async def get_coverage(height: Optional[float] = None):
    """Get the last computed coverage map, or compute a new one."""
    if last_simulation_result and "coverage" in last_simulation_result:
        return last_simulation_result["coverage"]
    
    # Run a quick simulation if none exists
    result = run_simulation(scene)
    return result.get("coverage", {})


@app.websocket("/ws/simulation")
async def websocket_simulation(websocket: WebSocket):
    """
    WebSocket endpoint for real-time simulation updates.
    Client can send: { "action": "simulate", "params": { ... } }
    Server streams: { "status": "...", "progress": 0.0-1.0, "result": {...} }
    """
    await websocket.accept()
    print("🔌 WebSocket client connected")
    
    try:
        while True:
            # Wait for client message
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("action") == "simulate":
                params = message.get("params", {})
                
                # Send progress updates
                await websocket.send_json({
                    "status": "running",
                    "progress": 0.1,
                    "message": "Loading scene...",
                })
                
                await asyncio.sleep(0.1)
                
                await websocket.send_json({
                    "status": "running",
                    "progress": 0.3,
                    "message": "Computing ray paths...",
                })
                
                # Run simulation
                result = run_simulation(
                    scene,
                    max_depth=params.get("max_depth"),
                    num_samples=params.get("num_samples"),
                    diffraction=params.get("diffraction"),
                    coverage_height=params.get("heatmap_height"),
                )
                
                global last_simulation_result
                last_simulation_result = result
                
                await websocket.send_json({
                    "status": "running",
                    "progress": 0.9,
                    "message": "Processing results...",
                })
                
                await asyncio.sleep(0.1)
                
                # Send final result
                await websocket.send_json({
                    "status": "complete",
                    "progress": 1.0,
                    "message": "Simulation complete!",
                    "result": result,
                })
                
            elif message.get("action") == "get_scene":
                info = get_scene_info(scene)
                await websocket.send_json({
                    "status": "complete",
                    "type": "scene_info",
                    "result": info,
                })
                
            elif message.get("action") == "ping":
                await websocket.send_json({"status": "pong"})
                
    except WebSocketDisconnect:
        print("🔌 WebSocket client disconnected")
    except Exception as e:
        print(f"❌ WebSocket error: {e}")
        try:
            await websocket.send_json({
                "status": "error",
                "message": str(e),
            })
        except:
            pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=API_HOST,
        port=API_PORT,
        reload=True,
    )
