/**
 * MVP-Sionna-WiFi: UI Controls
 * Manages panel interactions, parameter changes, and receiver selection.
 */

import { requestSimulation, isConnected } from './websocket.js';
import { filterRaysByReceiver, setRaysVisible } from './rays.js';
import { setHeatmapVisible, setHeatmapHeight } from './heatmap.js';
import { setActiveReceiver } from './sensors.js';
import { initCSIPanel, openCSI, closeCSI } from './csi_panel.js';

let lastSimResult = null;

let selectedReceiver = 'all';
let onSimulateCallback = null;
let isLiveSimulation = false;

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
}

function setupSimulationButton() {
    const btn = document.getElementById('btn-simulate');
    btn.addEventListener('click', () => {
        if (isLiveSimulation) {
            // Stop
            isLiveSimulation = false;
            resetSimulateButton();
            showProgress(1, 'Simulation stopped.');
            return;
        }

        if (!isConnected()) {
            // Fallback: use REST API
            runSimulationREST();
            return;
        }
        
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
    
    // Heatmap height
    const heatmapSlider = document.getElementById('heatmap-height');
    const heatmapVal = document.getElementById('heatmap-height-val');
    heatmapSlider.addEventListener('input', () => {
        heatmapVal.textContent = parseFloat(heatmapSlider.value).toFixed(1);
        setHeatmapHeight(parseFloat(heatmapSlider.value));
    });
    
    // Labels toggle (for future use)
    document.getElementById('toggle-labels').addEventListener('change', () => {
        // TODO: implement label visibility
    });
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
                
                // Calculamos RSSI desde los paths
                if (lastSimResult.paths && lastSimResult.paths[name]) {
                    let totalPowerLin = 0;
                    lastSimResult.paths[name].forEach(p => totalPowerLin += p.power_lin);
                    if (totalPowerLin > 0) {
                        rssi = 10 * Math.log10(totalPowerLin);
                    }
                }
            }
            
            // Si no hay datos (aún no se simuló), pasamos null y se pondrá en waiting o ruido por defecto
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
    const rxConfig = lastSimResult.paths?.find(p => p.receiver === receiverName);
    if (rxConfig) {
        document.getElementById('info-distance').textContent = '—';
    }
}
