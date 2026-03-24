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
from fastapi.responses import FileResponse

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

# Animation state
animation_frames_dir = None
animation_sequence = None
is_animating = False
animation_task = None  # asyncio.Task for current animation

# Sim-walk state (synchronized frame-by-frame simulation)
sim_walk_paused = False
sim_walk_resume_event = asyncio.Event()
sim_walk_frames_dir = None


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
                    smpl_manager.save_obj(human_obj_path, for_sionna=False)
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
                
            elif message.get("action") == "animate":
                # Run animation as background task so WebSocket stays responsive
                global animation_task
                if animation_task and not animation_task.done():
                    animation_task.cancel()
                is_animating = False  # Reset before starting new
                animation_task = asyncio.create_task(
                    handle_animation(websocket, message.get("params", {}))
                )
                
            elif message.get("action") == "stop_animation":
                is_animating = False
                if animation_task and not animation_task.done():
                    animation_task.cancel()
                await websocket.send_json({
                    "status": "animation_stopped",
                    "message": "Animation stopped by user.",
                })

            # ── Sim Walk (synchronized frame-by-frame) ──────────────
            elif message.get("action") == "sim_walk":
                global sim_walk_paused
                if animation_task and not animation_task.done():
                    animation_task.cancel()
                is_animating = False
                sim_walk_paused = False
                animation_task = asyncio.create_task(
                    handle_sim_walk(websocket, message.get("params", {}))
                )

            elif message.get("action") == "pause_sim_walk":
                sim_walk_paused = True
                print("⏸️  Sim walk paused")

            elif message.get("action") == "resume_sim_walk":
                sim_walk_paused = False
                sim_walk_resume_event.set()
                print("▶️  Sim walk resumed")

            elif message.get("action") == "stop_sim_walk":
                is_animating = False
                sim_walk_paused = False
                sim_walk_resume_event.set()  # unblock if paused
                if animation_task and not animation_task.done():
                    animation_task.cancel()
                await websocket.send_json({
                    "status": "sim_walk_stopped",
                    "message": "Sim walk stopped.",
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


async def handle_animation(websocket: WebSocket, params: dict):
    """
    Handle walking animation: generate all frame meshes and send URLs.
    NO simulation is run — animation is purely visual on the frontend.
    The frontend loops through frames locally.
    """
    global is_animating, animation_frames_dir, animation_sequence
    
    if smpl_manager is None:
        await websocket.send_json({
            "status": "error",
            "message": "SMPL Manager not available. Cannot animate.",
        })
        return
    
    num_frames = params.get("num_frames", 16)
    
    is_animating = True
    
    await websocket.send_json({
        "status": "animation_start",
        "total_frames": num_frames,
        "message": f"Generating {num_frames} walk frames...",
    })
    
    # Generate all frame meshes upfront
    anim_dir = os.path.abspath(os.path.join("output", f"anim_{secrets.token_hex(4)}"))
    try:
        obj_paths, sequence = smpl_manager.save_walk_sequence_objs(
            anim_dir, num_frames=num_frames
        )
        animation_frames_dir = anim_dir
        animation_sequence = sequence
    except Exception as e:
        print(f"❌ Failed to generate walk sequence: {e}")
        is_animating = False
        await websocket.send_json({
            "status": "error",
            "message": f"Failed to generate walk meshes: {e}",
        })
        return
    
    # Build frame list with URLs and positions for the frontend
    frames = []
    for i, frame_data in enumerate(sequence):
        frames.append({
            "frame_index": i,
            "obj_url": f"/api/animation_frame/{i}",
            "position": frame_data.get('display_position', frame_data['transl']),
        })
    
    # Send all frame data at once — frontend handles the loop
    await websocket.send_json({
        "status": "animation_ready",
        "total_frames": num_frames,
        "frames": frames,
        "message": f"Generated {num_frames} frames. Animation starting...",
    })
    
    # Cleanup after 10 minutes (frontend loops, needs files for a while)
    asyncio.get_event_loop().call_later(600, _cleanup_animation_dir, anim_dir)
    
    # Mark animation as complete on backend so it can be restarted
    is_animating = False


def _cleanup_animation_dir(dir_path):
    """Remove animation frame files after a delay."""
    import shutil
    try:
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)
            print(f"🧹 Cleaned up animation frames: {dir_path}")
    except Exception as e:
        print(f"⚠️ Could not clean animation dir: {e}")


async def handle_sim_walk(websocket: WebSocket, params: dict):
    """
    Synchronized walk simulation: for each frame, generate SMPL mesh,
    inject into Sionna scene, run full simulation, send results.
    
    Supports pause/resume and cancellation via is_animating flag.
    """
    global is_animating, sim_walk_paused, sim_walk_frames_dir, scene, human_currently_in_scene
    
    if is_animating:
        print("⚠️ Sim walk already in progress, ignoring new request.")
        return
    
    if smpl_manager is None:
        await websocket.send_json({
            "status": "error",
            "message": "SMPL Manager not available.",
        })
        return
    
    num_frames = params.get("num_frames", 16)
    start_frame = params.get("start_frame", 0)
    sim_params = {
        "max_depth": params.get("max_depth"),
        "num_samples": params.get("num_samples"),
        "diffraction": params.get("diffraction"),
        "coverage_height": params.get("heatmap_height"),
    }
    
    is_animating = True
    sim_walk_paused = False
    
    # Import pose library
    from pose_library import generate_walk_sequence
    
    await websocket.send_json({
        "status": "sim_walk_start",
        "total_frames": num_frames,
        "start_frame": start_frame,
        "message": f"Starting continuous sim-walk: {num_frames} frames per cycle...",
    })
    
    # Generate walk sequence (poses + positions)
    sequence = generate_walk_sequence(num_frames)
    
    # Create directory for display OBJs (for frontend visualization)
    frames_dir = os.path.abspath(os.path.join("output", f"sim_walk_{secrets.token_hex(4)}"))
    os.makedirs(frames_dir, exist_ok=True)
    sim_walk_frames_dir = frames_dir
    
    try:
        frame_idx = start_frame
        while True:
            # ── Check cancellation ──
            if not is_animating:
                print(f"🛑 Sim walk stopped internally.")
                break
            
            # ── Check pause ──
            while sim_walk_paused and is_animating:
                await websocket.send_json({
                    "status": "sim_walk_paused",
                    "frame_index": frame_idx % num_frames,
                    "total_frames": num_frames,
                    "message": f"Paused at frame {(frame_idx % num_frames)+1}/{num_frames}",
                })
                sim_walk_resume_event.clear()
                await sim_walk_resume_event.wait()
            
            if not is_animating:
                break
            
            # Cycle through the sequence indefinitely
            seq_idx = frame_idx % num_frames
            frame = sequence[seq_idx]
            
            # ── 1. Generate OBJ for Sionna (Y↔Z swap, with position baked) ──
            temp_sionna_obj = os.path.join(frames_dir, f"sionna_{seq_idx:04d}.obj")
            smpl_manager.save_obj(
                temp_sionna_obj,
                body_pose=frame['body_pose'],
                global_orient=frame['global_orient'],
                transl=frame['sionna_position'],  # SMPL Y-up coords with position
                for_sionna=True,
            )
            
            # ── 2. Generate OBJ for frontend display (no swap, no position) ──
            display_obj = os.path.join(frames_dir, f"display_{seq_idx:04d}.obj")
            smpl_manager.save_obj(
                display_obj,
                body_pose=frame['body_pose'],
                global_orient=frame['global_orient'],
                transl=[0.0, 0.0, 0.0],  # Position handled by frontend
                for_sionna=False,
            )
            
            # ── 3. Load scene with human mesh ──
            scene = load_scene(human_mesh_path=temp_sionna_obj)
            human_currently_in_scene = True
            
            # ── 4. Run full Sionna simulation ──
            result = run_simulation(scene, **sim_params)
            
            # ── 5. Send frame + results to frontend ──
            await websocket.send_json({
                "status": "sim_walk_frame",
                "frame_index": seq_idx,
                "total_frames": num_frames,
                "obj_url": f"/api/sim_walk_frame/{seq_idx}",
                "position": frame['display_position'],
                "result": result,
                "message": f"Frame {seq_idx+1}/{num_frames} complete",
            })
            
            # Cleanup Sionna OBJ (display OBJ stays for frontend)
            try:
                os.remove(temp_sionna_obj)
            except:
                pass
            
            print(f"  📡 Sim-walk frame {seq_idx+1}/{num_frames}: {result.get('simulation_time', 0):.2f}s")
            
            # Small yield to allow WebSocket message processing (pause/stop)
            await asyncio.sleep(0.05)
            
            frame_idx += 1
        
    except asyncio.CancelledError:
        print("🛑 Sim walk task cancelled")
    except Exception as e:
        print(f"❌ Sim walk error: {e}")
        import traceback
        traceback.print_exc()
        await websocket.send_json({
            "status": "error",
            "message": f"Sim walk failed at frame: {e}",
        })
    finally:
        is_animating = False
        # Schedule cleanup of display OBJs after 10 minutes
        asyncio.get_event_loop().call_later(600, _cleanup_animation_dir, frames_dir)
    
    # Send completion
    if is_animating is False:
        try:
            await websocket.send_json({
                "status": "sim_walk_complete",
                "total_frames": num_frames,
                "message": f"Sim-walk complete: {num_frames} frames processed.",
            })
        except:
            pass


@app.get("/api/animation_frame/{frame_id}")
async def get_animation_frame(frame_id: int):
    """Serve a generated animation frame .obj file."""
    if animation_frames_dir is None:
        return {"error": "No animation frames available"}
    
    obj_path = os.path.join(animation_frames_dir, f"frame_{frame_id:04d}.obj")
    if not os.path.exists(obj_path):
        return {"error": f"Frame {frame_id} not found"}
    
    return FileResponse(
        obj_path,
        media_type="text/plain",
        filename=f"frame_{frame_id:04d}.obj"
    )


@app.get("/api/sim_walk_frame/{frame_id}")
async def get_sim_walk_frame(frame_id: int):
    """Serve a sim-walk display .obj file."""
    if sim_walk_frames_dir is None:
        return {"error": "No sim-walk frames available"}
    
    obj_path = os.path.join(sim_walk_frames_dir, f"display_{frame_id:04d}.obj")
    if not os.path.exists(obj_path):
        return {"error": f"Sim-walk frame {frame_id} not found"}
    
    return FileResponse(
        obj_path,
        media_type="text/plain",
        filename=f"display_{frame_id:04d}.obj"
    )


@app.get("/api/animation_info")
async def get_animation_info():
    """Get current animation state."""
    return {
        "is_animating": is_animating,
        "has_frames": animation_frames_dir is not None,
        "sequence": animation_sequence if animation_sequence else [],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=API_HOST,
        port=API_PORT,
        reload=True,
    )
