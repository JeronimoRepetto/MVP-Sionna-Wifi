/**
 * MVP-Sionna-WiFi: Main Entry Point
 * Orchestrates Three.js scene, WebSocket, controls, and visualizations.
 */

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

import { createRoom, getRoomDimensions } from './scene3d.js';
import { createSensors, updateSensorAnimations, setActiveReceiver } from './sensors.js';
import { createRays, updateRayAnimations, clearRays } from './rays.js';
import { createHeatmap, setHeatmapVisible } from './heatmap.js';
import { initControls, populateReceiverList, updateConnectionStatus, 
         showProgress, resetSimulateButton, setSimulationResult, runNextLiveSimulation } from './controls.js';
import { initWebSocket, sendMessage } from './websocket.js';

// =============================================================================
// Three.js Setup
// =============================================================================

const canvas = document.getElementById('three-canvas');
const renderer = new THREE.WebGLRenderer({ 
    canvas, 
    antialias: true, 
    alpha: true,
    powerPreference: 'high-performance',
});
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(canvas.clientWidth, canvas.clientHeight);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.2;

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x080c14);
scene.fog = new THREE.Fog(0x080c14, 8, 20);

const camera = new THREE.PerspectiveCamera(
    50,
    canvas.clientWidth / canvas.clientHeight,
    0.01,
    100
);
camera.position.set(3, -3, 4);
camera.up.set(0, 0, 1); // Z-up to match Sionna/Blender

const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.rotateSpeed = 0.8;
controls.zoomSpeed = 1.2;
controls.target.set(0, 0, 0.8);
controls.minDistance = 1;
controls.maxDistance = 15;
controls.update();

// =============================================================================
// State
// =============================================================================

let sceneInfo = null;
let roomOffset = { x: 0, y: 0 };
let lastFrameTime = performance.now();
let frameCount = 0;
let fpsAccum = 0;

// =============================================================================
// Initialize
// =============================================================================

// Set up UI controls
initControls(onSimulationComplete);

// Connect WebSocket
initWebSocket(onWebSocketMessage, onConnectionStatus);

// Fetch scene info via REST as fallback
fetchSceneInfo();

// Start render loop
animate();

// Handle resize
window.addEventListener('resize', onResize);
onResize();

// =============================================================================
// REST API Fallback
// =============================================================================

async function fetchSceneInfo() {
    try {
        const response = await fetch('/api/scene');
        const data = await response.json();
        setupScene(data);
    } catch (e) {
        console.warn('Could not fetch scene info via REST, using defaults');
        setupScene(getDefaultSceneInfo());
    }
}

function getDefaultSceneInfo() {
    return {
        room: { width: 2.0, depth: 3.5, height: 2.0, wall_thickness: 0.12 },
        transmitter: { name: 'Router_Tx', position: [1.0, 3.4, 1.8] },
        receivers: [
            { name: 'ESP32_1', position: [0.1, 0.1, 1.8], label: 'Front-Left High' },
            { name: 'ESP32_2', position: [1.9, 0.1, 1.8], label: 'Front-Right High' },
            { name: 'ESP32_3', position: [0.1, 3.4, 1.8], label: 'Back-Left High' },
            { name: 'ESP32_4', position: [1.9, 3.4, 1.8], label: 'Back-Right High' },
            { name: 'ESP32_5', position: [0.1, 0.1, 0.15], label: 'Front-Left Low' },
            { name: 'ESP32_6', position: [1.9, 0.1, 0.15], label: 'Front-Right Low' },
            { name: 'ESP32_7', position: [0.1, 3.4, 0.15], label: 'Back-Left Low' },
            { name: 'ESP32_8', position: [1.9, 3.4, 0.15], label: 'Back-Right Low' },
        ],
        frequency_ghz: 2.437,
        bandwidth_mhz: 40,
        num_subcarriers: 114,
    };
}

// =============================================================================
// Scene Setup
// =============================================================================

function setupScene(info) {
    sceneInfo = info;
    
    // Calculate offset to center room at origin
    roomOffset = {
        x: -info.room.width / 2,
        y: -info.room.depth / 2,
    };
    
    // Create 3D room
    createRoom(scene, info.room);
    
    // Create sensors
    createSensors(scene, info, roomOffset);
    
    // Populate receiver list in UI
    populateReceiverList(info.receivers);
    
    // Position camera to see the full room
    const maxDim = Math.max(info.room.width, info.room.depth, info.room.height);
    camera.position.set(maxDim * 1.5, -maxDim * 1.5, maxDim * 1.8);
    controls.target.set(0, 0, info.room.height * 0.4);
    controls.update();

    // Update Sionna status badge
    const badge = document.getElementById('sionna-badge');
    if (badge) {
        if (info.sionna_active) {
            badge.textContent = "🟢 Sionna RT: Active";
            badge.style.backgroundColor = "rgba(40, 167, 69, 0.2)";
            badge.style.color = "#4ade80"; // Bright Green
        } else {
            badge.textContent = "🟠 Sionna RT: Mock Mode";
            badge.style.backgroundColor = "rgba(255, 193, 7, 0.2)";
            badge.style.color = "#fbbf24"; // Amber
        }
    }
    
    console.log('✅ Scene setup complete:', info);
}

// =============================================================================
// WebSocket Handlers
// =============================================================================

function onConnectionStatus(status) {
    updateConnectionStatus(status);
}

function onWebSocketMessage(data) {
    if (data.type === 'scene_info' && data.result) {
        setupScene(data.result);
        return;
    }
    
    if (data.status === 'running') {
        showProgress(data.progress, data.message);
        return;
    }
    
    if (data.status === 'complete' && data.result) {
        onSimulationComplete(data);
        return;
    }
    
    if (data.status === 'error') {
        console.error('Simulation error:', data.message);
        showProgress(0, `Error: ${data.message}`);
        resetSimulateButton();
    }
}

function onSimulationComplete(data) {
    const result = data.result;
    
    resetSimulateButton();
    showProgress(1, `Complete in ${result.simulation_time.toFixed(2)}s`);
    
    // Store result for UI
    setSimulationResult(result);
    
    // Render ray paths
    if (result.paths) {
        createRays(scene, result.paths, roomOffset);
    }
    
    // Render coverage heatmap (hidden by default, toggle to show)
    if (result.coverage) {
        createHeatmap(scene, result.coverage, sceneInfo.room, roomOffset);
        setHeatmapVisible(document.getElementById('toggle-heatmap').checked);
    }
    
    console.log('✅ Visualization updated with simulation results');
    
    // Trigger next loop frame if live simulation is active
    runNextLiveSimulation();
}

// =============================================================================
// Animation Loop
// =============================================================================

function animate() {
    requestAnimationFrame(animate);
    
    const now = performance.now();
    const deltaTime = (now - lastFrameTime) / 1000;
    lastFrameTime = now;
    
    // FPS counter
    frameCount++;
    fpsAccum += deltaTime;
    if (fpsAccum >= 0.5) {
        const fps = Math.round(frameCount / fpsAccum);
        document.getElementById('fps-counter').textContent = `${fps} FPS`;
        frameCount = 0;
        fpsAccum = 0;
    }
    
    // Update controls
    controls.update();
    
    // Animate sensors
    updateSensorAnimations(deltaTime);
    
    // Animate rays
    updateRayAnimations(deltaTime);
    
    // Render
    renderer.render(scene, camera);
}

// =============================================================================
// Resize
// =============================================================================

function onResize() {
    const container = document.getElementById('viewport-container');
    const width = container.clientWidth;
    const height = container.clientHeight;
    
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height);
}
