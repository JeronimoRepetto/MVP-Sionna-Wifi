/**
 * MVP-Sionna-WiFi: UI Controls
 * Manages panel interactions, parameter changes, receiver selection, and animation.
 */

import { requestSimulation, requestAnimation, stopAnimationWs, isConnected } from './websocket.js';
import { filterRaysByReceiver, setRaysVisible } from './rays.js';
import { setHeatmapVisible, setHeatmapHeight } from './heatmap.js';
import { setActiveReceiver } from './sensors.js';
import { initCSIPanel, openCSI, closeCSI } from './csi_panel.js';
import { setHumanVisible, getSmplParams, updateHumanMesh, setHumanPosition,
         startAnimation as startHumanAnim, stopAnimation as stopHumanAnim,
         setAnimationFrame, getAnimationState } from './human.js';

let lastSimResult = null;
let currentSceneInfo = null;

export function setControlsSceneInfo(info) {
    currentSceneInfo = info;
}

let selectedReceiver = 'all';
let onSimulateCallback = null;
let isLiveSimulation = false;

// Animation state
let isWalkAnimating = false;

export function runNextLiveSimulation() {
    if (isLiveSimulation && isConnected()) {
        // Small delay to let the UI update and render before next intense calculation
        setTimeout(() => {
            if (isLiveSimulation) {
                requestSimulation(getSimulationParams());
            }
        }, 100);
    }
}

export function initControls(onSimulate) {
    initCSIPanel();
    onSimulateCallback = onSimulate;
    
    setupSimulationButton();
    setupParameterSliders();
    setupDisplayToggles();
    setupAnimationControls();
}

function setupSimulationButton() {
    const btn = document.getElementById('btn-simulate');
    btn.addEventListener('click', () => {
        if (isLiveSimulation) {
            // Stop live sim only (animation continues independently)
            isLiveSimulation = false;
            resetSimulateButton();
            showProgress(1, 'Simulation stopped.');
            return;
        }

        if (!isConnected()) {
            runSimulationREST();
            return;
        }
        
        // Animation is visual-only, no need to stop it when starting sim
        
        isLiveSimulation = true;
        btn.classList.add('running');
        btn.innerHTML = '<span class="btn-icon">⏸</span> STOP LIVE SIM';
        
        showProgress(0.1, 'Running continuously...');
        requestSimulation(getSimulationParams());
    });
}

async function runSimulationREST() {
    const btn = document.getElementById('btn-simulate');
    const params = getSimulationParams();
    
    btn.disabled = true;
    btn.classList.add('running');
    btn.innerHTML = '<span class="btn-icon">⏳</span> Simulating...';
    showProgress(0.2, 'Running simulation via REST...');
    
    try {
        const queryParams = new URLSearchParams();
        if (params.max_depth) queryParams.set('max_depth', params.max_depth);
        if (params.num_samples) queryParams.set('num_samples', params.num_samples);
        if (params.diffraction !== undefined) queryParams.set('diffraction', params.diffraction);
        
        const response = await fetch(`/api/simulate?${queryParams}`, { method: 'POST' });
        const result = await response.json();
        
        showProgress(1, 'Complete!');
        onSimulateCallback?.({ status: 'complete', result });
    } catch (e) {
        console.error('REST simulation failed:', e);
        showProgress(0, 'Failed! Check backend connection.');
    } finally {
        resetSimulateButton();
    }
}

function getSimulationParams() {
    return {
        max_depth: parseInt(document.getElementById('param-depth').value),
        num_samples: parseInt(document.getElementById('param-samples').value),
        diffraction: document.getElementById('param-diffraction').checked,
        heatmap_height: parseFloat(document.getElementById('heatmap-height').value) || 0.2,
        smpl_params: getSmplParams(),
    };
}

export function resetSimulateButton() {
    const btn = document.getElementById('btn-simulate');
    if (isLiveSimulation) return;
    btn.disabled = false;
    btn.classList.remove('running');
    btn.innerHTML = '<span class="btn-icon">▶</span> START LIVE SIM';
}

function setupParameterSliders() {
    // Max depth
    const depthSlider = document.getElementById('param-depth');
    const depthVal = document.getElementById('param-depth-val');
    depthSlider.addEventListener('input', () => {
        depthVal.textContent = depthSlider.value;
    });
    
    // Ray density
    const samplesSlider = document.getElementById('param-samples');
    const samplesVal = document.getElementById('param-samples-val');
    samplesSlider.addEventListener('input', () => {
        const val = parseInt(samplesSlider.value);
        samplesVal.textContent = val >= 1000000 ? `${(val / 1000000).toFixed(1)}M` : `${(val / 1000).toFixed(0)}K`;
    });
}

function setupDisplayToggles() {
    // Human Obstacle
    document.getElementById('toggle-human').addEventListener('change', (e) => {
        setHumanVisible(e.target.checked);
        // Show/hide animation controls
        const animControls = document.getElementById('animation-controls');
        if (animControls) {
            animControls.style.display = e.target.checked ? 'block' : 'none';
        }
        // Stop animation if human is disabled
        if (!e.target.checked && isWalkAnimating) {
            handleStopAnimation();
        }
    });

    // Show rays
    document.getElementById('toggle-rays').addEventListener('change', (e) => {
        setRaysVisible(e.target.checked);
    });
    
    // Show heatmap
    const heatmapToggle = document.getElementById('toggle-heatmap');
    const heatmapHeightGroup = document.getElementById('heatmap-height-group');
    heatmapToggle.addEventListener('change', (e) => {
        setHeatmapVisible(e.target.checked);
        heatmapHeightGroup.style.display = e.target.checked ? 'block' : 'none';
    });
    
    // Heatmap opacity
    const heatmapSlider = document.getElementById('heatmap-height');
    const heatmapVal = document.getElementById('heatmap-height-val');
    heatmapSlider.addEventListener('input', () => {
        heatmapVal.textContent = parseFloat(heatmapSlider.value).toFixed(2);
        setHeatmapHeight(parseFloat(heatmapSlider.value));
    });
}

// =============================================================================
// Animation Controls
// =============================================================================

function setupAnimationControls() {
    const animBtn = document.getElementById('btn-animate');
    if (!animBtn) return;
    
    animBtn.addEventListener('click', () => {
        if (isWalkAnimating) {
            handleStopAnimation();
        } else {
            handleStartAnimation();
        }
    });
    
    // Speed slider
    const speedSlider = document.getElementById('anim-speed');
    const speedVal = document.getElementById('anim-speed-val');
    if (speedSlider) {
        speedSlider.addEventListener('input', () => {
            speedVal.textContent = `${parseFloat(speedSlider.value).toFixed(1)}x`;
        });
    }
    
    // Frames slider
    const framesSlider = document.getElementById('anim-frames');
    const framesVal = document.getElementById('anim-frames-val');
    if (framesSlider) {
        framesSlider.addEventListener('input', () => {
            framesVal.textContent = framesSlider.value;
        });
    }
}

function handleStartAnimation() {
    if (!isConnected()) {
        showProgress(0, 'Cannot animate: not connected to backend.');
        return;
    }
    
    // Animation is visual-only — doesn't interfere with Live Sim
    
    isWalkAnimating = true;
    const btn = document.getElementById('btn-animate');
    btn.classList.add('animating');
    btn.innerHTML = '<span class="btn-icon">⏸</span> Stop Walk';
    
    const numFrames = parseInt(document.getElementById('anim-frames')?.value || '16');
    
    startHumanAnim(numFrames);
    
    // Show animation progress bar
    const progBar = document.getElementById('anim-progress-bar');
    if (progBar) progBar.classList.remove('hidden');
    
    // Send animation request — backend generates meshes only, no simulation
    requestAnimation({
        num_frames: numFrames,
    });
    
    showProgress(0.05, 'Generating walk frames...');
}

// Animation loop state
let animFrames = null;     // Array of { obj_url, position } from backend
let animLoopTimer = null;  // setInterval ID
let animCurrentIdx = 0;    // Current frame index in the loop

function startAnimationLoop(frames) {
    animFrames = frames;
    animCurrentIdx = 0;
    
    const speed = parseFloat(document.getElementById('anim-speed')?.value || '1.0');
    const intervalMs = Math.max(50, Math.round(200 / speed));  // ~5 FPS at 1x speed
    
    // Clear any previous loop
    if (animLoopTimer) clearInterval(animLoopTimer);
    
    animLoopTimer = setInterval(() => {
        if (!isWalkAnimating || !animFrames) {
            clearInterval(animLoopTimer);
            animLoopTimer = null;
            return;
        }
        
        const frame = animFrames[animCurrentIdx];
        
        // Update mesh and position
        updateHumanMesh(`${frame.obj_url}?t=${Date.now()}`);
        if (frame.position) {
            setHumanPosition(frame.position[0], frame.position[1], frame.position[2]);
        }
        setAnimationFrame(animCurrentIdx, animFrames.length);
        
        // Update UI
        const counter = document.getElementById('anim-frame-counter');
        if (counter) counter.textContent = `${animCurrentIdx + 1}/${animFrames.length}`;
        
        const progFill = document.querySelector('.anim-progress-fill');
        if (progFill) progFill.style.width = `${((animCurrentIdx + 1) / animFrames.length) * 100}%`;
        
        // Loop back to start
        animCurrentIdx = (animCurrentIdx + 1) % animFrames.length;
        
    }, intervalMs);
}

function handleStopAnimation() {
    isWalkAnimating = false;
    
    // Stop the frontend loop
    if (animLoopTimer) {
        clearInterval(animLoopTimer);
        animLoopTimer = null;
    }
    animFrames = null;
    animCurrentIdx = 0;
    
    stopHumanAnim();
    // Don't send stop_animation to backend here — it creates a race condition
    // where the backend's 'animation_stopped' response kills a newly started animation.
    
    const btn = document.getElementById('btn-animate');
    btn.classList.remove('animating');
    btn.innerHTML = '<span class="btn-icon">▶</span> Play Walk';
    
    const counter = document.getElementById('anim-frame-counter');
    if (counter) counter.textContent = '—';
    
    const progBar = document.getElementById('anim-progress-bar');
    if (progBar) progBar.classList.add('hidden');
    
    showProgress(1, 'Animation stopped.');
}

/**
 * Handle incoming animation WebSocket messages.
 * Called from main.js onWebSocketMessage.
 */
export function handleAnimationMessage(data) {
    switch (data.status) {
        case 'animation_start':
            showProgress(0.1, data.message);
            break;
            
        case 'animation_ready':
            // Backend sent all frame URLs — start frontend loop
            if (data.frames && data.frames.length > 0) {
                showProgress(1, `${data.frames.length} frames ready. Playing...`);
                startAnimationLoop(data.frames);
            }
            break;
            
        case 'animation_stopped':
            // Only stop if we're still in animating state
            // (prevents race condition when user quickly presses Stop then Play)
            if (isWalkAnimating) {
                handleStopAnimation();
            }
            break;
    }
}

export function populateReceiverList(receivers) {
    const container = document.getElementById('receiver-list');
    container.innerHTML = '';
    
    // "All" button
    const allCard = document.createElement('div');
    allCard.className = 'receiver-card all-active active';
    allCard.innerHTML = `
        <span class="receiver-name">📡 All Receivers</span>
        <span class="receiver-pos">8 links</span>
    `;
    allCard.addEventListener('click', () => selectReceiver('all', container));
    container.appendChild(allCard);
    
    // Individual receivers
    receivers.forEach(rx => {
        const card = document.createElement('div');
        const isHigh = rx.position[2] > 1.0;
        card.className = 'receiver-card';
        card.dataset.name = rx.name;
        card.innerHTML = `
            <span class="receiver-name">${isHigh ? '🔵' : '🟣'} ${rx.name.replace('ESP32_', 'Rx ')}</span>
            <span class="receiver-pos">[${rx.position.map(v => v.toFixed(1)).join(', ')}]</span>
            <span class="receiver-power" id="power-${rx.name}">--</span>
        `;
        card.addEventListener('click', () => selectReceiver(rx.name, container));
        container.appendChild(card);
    });
}

function selectReceiver(name, container) {
    selectedReceiver = name;
    
    // Update UI
    container.querySelectorAll('.receiver-card').forEach(card => {
        card.classList.remove('active');
    });
    
    if (name === 'all') {
        container.querySelector('.all-active').classList.add('active');
        setActiveReceiver('all');
        filterRaysByReceiver('all');
        closeCSI(); // Close CSI panel when "All" is selected
    } else {
        const card = container.querySelector(`[data-name="${name}"]`);
        if (card) {
            card.classList.add('active');
            // Select and show CSI Spectrogram Panel
            setActiveReceiver(name);
            filterRaysByReceiver(name);
            
            // Extract CSI and RSSI
            let csiData = null;
            let rssi = -90; // Default RSSI if not found
            if (lastSimResult) {
                if (lastSimResult.csi) {
                    csiData = lastSimResult.csi.find(c => c.receiver === name);
                }
                
                // Calculate RSSI from paths
                if (lastSimResult.paths && lastSimResult.paths[name]) {
                    let totalPowerLin = 0;
                    lastSimResult.paths[name].forEach(p => totalPowerLin += p.power_lin);
                    if (totalPowerLin > 0) {
                        rssi = 10 * Math.log10(totalPowerLin);
                    }
                }
            }
            
            openCSI(name, csiData, rssi);
        }
    }
    
    // Update signal info
    updateSignalInfo(name);
}

export function getSelectedReceiver() {
    return selectedReceiver;
}

export function showProgress(progress, message) {
    const bar = document.getElementById('progress-bar');
    const fill = bar.querySelector('.progress-fill');
    const text = bar.querySelector('.progress-text');
    const msg = document.getElementById('progress-message');
    
    bar.classList.remove('hidden');
    msg.classList.remove('hidden');
    
    fill.style.width = `${progress * 100}%`;
    text.textContent = `${Math.round(progress * 100)}%`;
    msg.textContent = message;
    
    if (progress >= 1) {
        setTimeout(() => {
            bar.classList.add('hidden');
            msg.classList.add('hidden');
        }, 2000);
    }
}

export function updateConnectionStatus(status) {
    const badge = document.getElementById('connection-status');
    const text = badge.querySelector('.status-text');
    
    badge.className = `status-badge ${status}`;
    text.textContent = status === 'connected' ? 'Connected' : 'Disconnected';
}

export function setSimulationResult(result) {
    lastSimResult = result;
    
    // Update sim time
    const simTime = document.getElementById('sim-time');
    simTime.querySelector('.metric-value').textContent = 
        `${result.simulation_time.toFixed(2)}s`;
    
    // Update receiver powers
    result.cir?.forEach(cirData => {
        const powerEl = document.getElementById(`power-${cirData.receiver}`);
        if (powerEl) {
            powerEl.textContent = `${cirData.total_power_db.toFixed(1)} dB`;
        }
    });
    
    // Update signal info for selected receiver
    updateSignalInfo(selectedReceiver);
}

function updateSignalInfo(receiverName) {
    const infoSection = document.getElementById('signal-info');
    
    if (!lastSimResult || receiverName === 'all') {
        infoSection.style.display = 'none';
        return;
    }
    
    infoSection.style.display = 'block';
    
    const cirData = lastSimResult.cir?.find(c => c.receiver === receiverName);
    const pathData = lastSimResult.paths?.find(p => p.receiver === receiverName);
    
    if (cirData) {
        document.getElementById('info-power').textContent = 
            `${cirData.total_power_db.toFixed(1)} dB`;
        document.getElementById('info-delay').textContent = 
            `${cirData.delay_spread_ns.toFixed(1)} ns`;
    }
    
    if (pathData) {
        document.getElementById('info-paths').textContent = pathData.num_paths;
    }
    
    // Calculate distance from Tx
    if (currentSceneInfo && currentSceneInfo.transmitter && currentSceneInfo.receivers) {
        const txPos = currentSceneInfo.transmitter.position;
        const rx = currentSceneInfo.receivers.find(r => r.name === receiverName);
        if (rx) {
            const rxPos = rx.position;
            const dist = Math.sqrt(
                Math.pow(txPos[0] - rxPos[0], 2) +
                Math.pow(txPos[1] - rxPos[1], 2) +
                Math.pow(txPos[2] - rxPos[2], 2)
            );
            document.getElementById('info-distance').textContent = `${dist.toFixed(2)} m`;
        } else {
            document.getElementById('info-distance').textContent = '—';
        }
    } else {
        document.getElementById('info-distance').textContent = '—';
    }
}
