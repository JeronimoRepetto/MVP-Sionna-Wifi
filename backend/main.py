"""
MVP-Sionna-WiFi: FastAPI Backend Server
Provides REST API and WebSocket for the 3D visualization frontend.
"""

import asyncio
import json
import time
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import API_HOST, API_PORT
from scene_loader import load_scene, get_scene_info, MITSUBA_VARIANT
from simulation import run_simulation
import os
import secrets

# Try to load the SMPL manager
try:
    from smpl_manager import SMPLManager
    smpl_manager = SMPLManager()
except ImportError:
    print("⚠️ SMPL Manager not available. Install smplx, torch, trimesh.")
    smpl_manager = None

# Global scene (loaded once at startup)
scene = None
last_simulation_result = None
human_currently_in_scene = False


@asynccontextmanager
async def lifespan(app):
    """Load the scene at server startup, clean up on shutdown."""
    global scene
    try:
        if smpl_manager is not None:
            try:
                frontend_public = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "public"))
                os.makedirs(frontend_public, exist_ok=True)
                human_obj_path = os.path.join(frontend_public, "human.obj")
                # Generate if missing or if we just want to ensure it's there
                if not os.path.exists(human_obj_path):
                    print("🏃 Generating static human.obj for frontend...")
                    smpl_manager.save_obj(human_obj_path)
            except Exception as e:
                print(f"⚠️ Could not generate static frontend human.obj: {e}")

        scene = load_scene()
        # Check what we actually got
        if isinstance(scene, dict) and scene.get("type") == "mock":
            print("⚠️  Running in mock mode (Sionna not available)")
        else:
            from scene_loader import MITSUBA_VARIANT as variant
            backend = "CUDA+OptiX (GPU)" if "cuda" in variant else "LLVM (CPU)"
            print(f"✅ Scene loaded at startup — Backend: {backend}")
    except Exception as e:
        print(f"⚠️  Could not load scene: {e}")
        print("   Running in mock mode")
        scene = {"type": "mock"}
    
    yield  # Server runs here
    
    # Shutdown
    print("🔴 Server shutting down")


app = FastAPI(
    title="MVP-Sionna-WiFi",
    description="WiFi propagation simulation using Sionna RT",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS for frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
                global scene, human_currently_in_scene
                smpl_params = params.get("smpl_params", None)
                
                if smpl_params is not None and smpl_manager is not None:
                    await websocket.send_json({
                        "status": "running",
                        "progress": 0.05,
                        "message": "Generating human mesh...",
                    })
                    # Use absolute paths or fixed relative temp path
                    os.makedirs("output", exist_ok=True)
                    temp_obj = f"output/temp_human_{secrets.token_hex(4)}.obj"
                    try:
                        smpl_manager.save_obj(
                            temp_obj, 
                            betas=smpl_params.get("betas"),
                            body_pose=smpl_params.get("body_pose"),
                            global_orient=smpl_params.get("global_orient"),
                            transl=smpl_params.get("transl")
                        )
                        # Reload the scene with the new mesh
                        scene = load_scene(human_mesh_path=temp_obj)
                        human_currently_in_scene = True
                    except Exception as e:
                        print(f"❌ Failed to generate or load human: {e}")
                    finally:
                        if os.path.exists(temp_obj):
                            try:
                                os.remove(temp_obj)
                            except:
                                pass
                else:
                    # If we had a human but now we don't, load base scene
                    if human_currently_in_scene:
                        scene = load_scene()
                        human_currently_in_scene = False

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
