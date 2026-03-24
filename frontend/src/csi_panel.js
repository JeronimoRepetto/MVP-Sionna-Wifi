/**
 * MVP-Sionna-WiFi: CSI Monitor Panel
 * Visualizes real Sionna simulation data for each ESP32 receiver.
 * 
 * 5 panels (matching wifi-csi-capture visualize_csi.py):
 *   1. Subcarrier Amplitude (current frame, linear scale)
 *   2. Subcarrier Phase (unwrapped)
 *   3. Amplitude Spectrogram (time × subcarrier heatmap)
 *   4. Activity Indicator (CV = std/mean turbulence)
 *   5. RSSI over time
 * 
 * Each ESP32 has its own independent history buffer.
 * Data is pushed in real-time via pushRealFrame() from simulation results.
 */

const MAX_SUBCARRIERS = 114;
const HISTORY_LEN = 100;

let active = false;
let currentReceiver = null;

// Per-receiver history storage: Map<receiverName, ReceiverState>
const receiverStates = new Map();

function createEmptyState() {
    const ampHistory = [];
    const phaseHistory = [];
    const rssiHistory = [];
    const activityHistory = [];
    for (let i = 0; i < HISTORY_LEN; i++) {
        ampHistory.push(new Float32Array(MAX_SUBCARRIERS));
        phaseHistory.push(new Float32Array(MAX_SUBCARRIERS));
        rssiHistory.push(-90);
        activityHistory.push(0);
    }
    return {
        ampHistory,
        phaseHistory,
        rssiHistory,
        activityHistory,
        frameCount: 0,
        baselineAmp: null,
        hasBaseline: false,
        spectroMaxVal: 1e-10,  // Only grows, never shrinks → stable colors
    };
}

function getState(receiverName) {
    if (!receiverStates.has(receiverName)) {
        receiverStates.set(receiverName, createEmptyState());
    }
    return receiverStates.get(receiverName);
}

// Canvas contexts
let ctxAmp, ctxPhase, ctxSpectro, ctxActivity, ctxRssi;

// Inferno-like colormap
function infernoColor(t) {
    t = Math.max(0, Math.min(1, t));
    const r = Math.min(255, Math.round(255 * Math.min(1, 1.5 * t)));
    const g = Math.min(255, Math.round(255 * Math.max(0, (t - 0.4) * 2)));
    const b = Math.min(255, Math.round(255 * Math.max(0, 0.5 - Math.abs(t - 0.3) * 2)));
    return { r, g, b };
}

export function initCSIPanel() {
    ctxAmp = document.getElementById('chart-amp')?.getContext('2d');
    ctxPhase = document.getElementById('chart-phase')?.getContext('2d');
    ctxSpectro = document.getElementById('chart-spectro')?.getContext('2d');
    ctxActivity = document.getElementById('chart-activity')?.getContext('2d');
    ctxRssi = document.getElementById('chart-rssi')?.getContext('2d');
    
    document.getElementById('close-csi-btn')?.addEventListener('click', closeCSI);
}

export function openCSI(receiverName, csiData, rssiData) {
    if (!ctxAmp) initCSIPanel();
    
    currentReceiver = receiverName;
    document.getElementById('csi-rx-name').textContent = receiverName;
    document.getElementById('csi-panel').classList.remove('hidden');
    active = true;
    
    // Redraw with this receiver's existing history
    const st = getState(receiverName);
    redrawAll(st, rssiData || -90);
    
    // If we have initial data, push it
    if (csiData) {
        pushRealFrame(csiData, rssiData);
    }
}

export function closeCSI() {
    document.getElementById('csi-panel').classList.add('hidden');
    active = false;
    currentReceiver = null;
}

/**
 * Reset history for a specific receiver (or all if no name given).
 */
export function resetCSIHistory(receiverName) {
    if (receiverName) {
        receiverStates.delete(receiverName);
    } else {
        receiverStates.clear();
    }
}

/**
 * Push a real Sionna simulation frame into the history for the SPECIFIED receiver.
 * Called from controls.js whenever a simulation result arrives.
 * 
 * @param {Object} csiData - { receiver, amplitude_db[], phase_rad[], mean_amplitude_db }
 * @param {number} rssiValue - RSSI in dBm
 * @param {string} [receiverName] - defaults to csiData.receiver or currentReceiver
 */
export function pushRealFrame(csiData, rssiValue, receiverName) {
    if (!csiData || !csiData.amplitude_db || !csiData.phase_rad) return;
    
    const rxName = receiverName || csiData.receiver || currentReceiver;
    if (!rxName) return;
    
    const st = getState(rxName);
    const subcount = Math.min(MAX_SUBCARRIERS, csiData.amplitude_db.length);
    
    // Convert dB to linear amplitude
    const ampLinear = new Float32Array(MAX_SUBCARRIERS);
    const phaseRaw = new Float32Array(MAX_SUBCARRIERS);
    
    for (let i = 0; i < subcount; i++) {
        ampLinear[i] = Math.pow(10, csiData.amplitude_db[i] / 20);
        phaseRaw[i] = csiData.phase_rad[i];
    }
    
    // Store baseline (first real frame for this receiver)
    if (!st.hasBaseline) {
        st.baselineAmp = new Float32Array(ampLinear);
        st.hasBaseline = true;
    }
    
    // Phase unwrap
    const phaseUnwrapped = unwrapPhase(phaseRaw);
    
    // Compute activity (CV = std/mean)
    const mean = ampLinear.reduce((a, b) => a + b, 0) / subcount;
    let variance = 0;
    for (let i = 0; i < subcount; i++) {
        variance += (ampLinear[i] - mean) ** 2;
    }
    const std = Math.sqrt(variance / subcount);
    const cv = mean > 0 ? std / mean : 0;
    
    // Push to this receiver's history
    st.ampHistory.shift();
    st.ampHistory.push(ampLinear);
    st.phaseHistory.shift();
    st.phaseHistory.push(phaseUnwrapped);
    st.rssiHistory.shift();
    st.rssiHistory.push(rssiValue || -90);
    st.activityHistory.shift();
    st.activityHistory.push(cv);
    st.frameCount++;
    
    // Only redraw if this receiver's panel is currently visible
    if (active && rxName === currentReceiver && ctxAmp) {
        redrawAll(st, rssiValue || -90);
    }
}

// Backward compat
export function updateBaseData(csiData, rssiData) {
    pushRealFrame(csiData, rssiData);
}

function redrawAll(st, currentRssi) {
    if (!ctxAmp) return;
    const lastAmp = st.ampHistory[st.ampHistory.length - 1];
    const lastPhase = st.phaseHistory[st.phaseHistory.length - 1];
    const lastCV = st.activityHistory[st.activityHistory.length - 1];
    
    drawAmp(ctxAmp, lastAmp, st);
    drawPhase(ctxPhase, lastPhase);
    drawSpectro(ctxSpectro, st);
    drawActivity(ctxActivity, st);
    drawRssi(ctxRssi, st, currentRssi);
    
    const statusEl = document.getElementById('csi-status');
    if (statusEl) {
        statusEl.textContent = `Frames: ${st.frameCount} | Subcarriers: ${MAX_SUBCARRIERS} | ` +
            `RSSI: ${currentRssi.toFixed(1)} dBm | CV: ${lastCV.toFixed(3)} | Real Sionna Data`;
    }
}

// --- Phase unwrap ---
function unwrapPhase(phases) {
    const out = new Float32Array(phases.length);
    out[0] = phases[0];
    for (let i = 1; i < phases.length; i++) {
        let diff = phases[i] - phases[i - 1];
        while (diff > Math.PI) diff -= 2 * Math.PI;
        while (diff < -Math.PI) diff += 2 * Math.PI;
        out[i] = out[i - 1] + diff;
    }
    return out;
}

// ==========================================================================
// Panel Renderers
// ==========================================================================

function drawAmp(ctx, amp, st) {
    const canvas = ctx.canvas;
    const w = canvas.width = canvas.clientWidth;
    const h = canvas.height = canvas.clientHeight;
    ctx.clearRect(0, 0, w, h);
    
    const n = Math.min(MAX_SUBCARRIERS, amp.length);
    const maxVal = Math.max(1e-6, ...amp) * 1.2;
    const bw = w / n;
    
    // Draw baseline reference if available
    if (st.hasBaseline && st.baselineAmp) {
        ctx.fillStyle = 'rgba(255, 180, 0, 0.25)';
        for (let i = 0; i < n; i++) {
            const hBar = (st.baselineAmp[i] / maxVal) * h;
            ctx.fillRect(i * bw, h - hBar, bw > 1 ? bw - 1 : bw, hBar);
        }
    }
    
    // Draw current frame
    ctx.fillStyle = '#00d4ff';
    for (let i = 0; i < n; i++) {
        const hBar = (amp[i] / maxVal) * h;
        ctx.fillRect(i * bw, h - hBar, bw > 1 ? bw - 1 : bw, hBar);
    }
    
    ctx.fillStyle = '#e0e0e0';
    ctx.font = '12px Inter, sans-serif';
    ctx.fillText('Subcarrier Amplitude (linear)', 5, 12);
    if (st.hasBaseline) {
        ctx.fillStyle = '#fbbf24';
        ctx.fillText('■ Baseline', w - 80, 12);
    }
}

function drawPhase(ctx, phase) {
    const canvas = ctx.canvas;
    const w = canvas.width = canvas.clientWidth;
    const h = canvas.height = canvas.clientHeight;
    ctx.clearRect(0, 0, w, h);
    
    const n = Math.min(MAX_SUBCARRIERS, phase.length);
    const bw = w / n;
    
    let minP = Infinity, maxP = -Infinity;
    for (let i = 0; i < n; i++) {
        if (phase[i] < minP) minP = phase[i];
        if (phase[i] > maxP) maxP = phase[i];
    }
    const range = (maxP - minP) || 1;
    
    ctx.strokeStyle = '#ff6b6b';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    for (let i = 0; i < n; i++) {
        const px = i * bw + bw / 2;
        const py = h - ((phase[i] - minP) / range) * (h - 20) - 10;
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
    }
    ctx.stroke();
    
    ctx.fillStyle = '#e0e0e0';
    ctx.font = '12px Inter, sans-serif';
    ctx.fillText('Phase (unwrapped, rad)', 5, 12);
}

function drawSpectro(ctx, st) {
    const canvas = ctx.canvas;
    const w = canvas.width = canvas.clientWidth;
    const h = canvas.height = canvas.clientHeight;
    
    // Update the running max (only grows → stable colors)
    for (const row of st.ampHistory) {
        for (let i = 0; i < row.length; i++) {
            if (row[i] > st.spectroMaxVal) st.spectroMaxVal = row[i];
        }
    }
    const maxVal = st.spectroMaxVal;
    
    const imgData = ctx.createImageData(w, h);
    const data = imgData.data;
    const cols = MAX_SUBCARRIERS;
    const rows = HISTORY_LEN;
    
    for (let y = 0; y < h; y++) {
        const rowIdx = Math.min(rows - 1, Math.floor((y / h) * rows));
        const rowData = st.ampHistory[rowIdx];
        
        for (let x = 0; x < w; x++) {
            const colIdx = Math.min(cols - 1, Math.floor((x / w) * cols));
            const val = rowData[colIdx] / maxVal;
            const c = infernoColor(val);
            
            const idx = (y * w + x) * 4;
            data[idx] = c.r;
            data[idx + 1] = c.g;
            data[idx + 2] = c.b;
            data[idx + 3] = 255;
        }
    }
    
    ctx.putImageData(imgData, 0, 0);
    
    ctx.fillStyle = '#e0e0e0';
    ctx.font = '12px Inter, sans-serif';
    ctx.fillText('Amplitude Spectrogram (time ↓ × subcarrier →)', 5, 12);
}

function drawActivity(ctx, st) {
    if (!ctx) return;
    const canvas = ctx.canvas;
    const w = canvas.width = canvas.clientWidth;
    const h = canvas.height = canvas.clientHeight;
    ctx.clearRect(0, 0, w, h);
    
    const history = st.activityHistory;
    const n = history.length;
    if (n < 2) return;
    
    let maxCV = 0.1;
    for (let i = 0; i < n; i++) {
        if (history[i] > maxCV) maxCV = history[i];
    }
    maxCV *= 1.2;
    
    const bw = w / n;
    const meanCV = history.reduce((a, b) => a + b, 0) / n;
    
    // Fill area
    ctx.fillStyle = 'rgba(74, 222, 128, 0.25)';
    ctx.beginPath();
    ctx.moveTo(0, h);
    for (let i = 0; i < n; i++) {
        const px = i * bw;
        const py = h - (history[i] / maxCV) * (h - 20) - 5;
        ctx.lineTo(px, py);
    }
    ctx.lineTo((n - 1) * bw, h);
    ctx.closePath();
    ctx.fill();
    
    // Line
    ctx.strokeStyle = '#4ade80';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    for (let i = 0; i < n; i++) {
        const px = i * bw;
        const py = h - (history[i] / maxCV) * (h - 20) - 5;
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
    }
    ctx.stroke();
    
    // Mean dashed line
    const meanY = h - (meanCV / maxCV) * (h - 20) - 5;
    ctx.strokeStyle = '#fbbf24';
    ctx.lineWidth = 0.8;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(0, meanY);
    ctx.lineTo(w, meanY);
    ctx.stroke();
    ctx.setLineDash([]);
    
    ctx.fillStyle = '#e0e0e0';
    ctx.font = '12px Inter, sans-serif';
    ctx.fillText(`Activity (CV = std/mean): ${history[n - 1].toFixed(3)}`, 5, 12);
}

function drawRssi(ctx, st, currentVal) {
    const canvas = ctx.canvas;
    const w = canvas.width = canvas.clientWidth;
    const h = canvas.height = canvas.clientHeight;
    ctx.clearRect(0, 0, w, h);
    
    const history = st.rssiHistory;
    const n = history.length;
    const bw = w / n;
    
    let rMin = Infinity, rMax = -Infinity;
    for (let i = 0; i < n; i++) {
        if (history[i] < rMin) rMin = history[i];
        if (history[i] > rMax) rMax = history[i];
    }
    const margin = Math.max((rMax - rMin) * 0.2, 2);
    rMin -= margin;
    rMax += margin;
    const range = rMax - rMin || 1;
    
    // Fill area
    ctx.fillStyle = 'rgba(56, 189, 248, 0.15)';
    ctx.beginPath();
    ctx.moveTo(0, h);
    for (let i = 0; i < n; i++) {
        const px = i * bw;
        const py = h - ((history[i] - rMin) / range) * (h - 10);
        ctx.lineTo(px, py);
    }
    ctx.lineTo((n - 1) * bw, h);
    ctx.closePath();
    ctx.fill();
    
    // Line
    ctx.strokeStyle = '#38bdf8';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    for (let i = 0; i < n; i++) {
        const px = i * bw;
        const py = h - ((history[i] - rMin) / range) * (h - 10);
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
    }
    ctx.stroke();
    
    // Mean dashed line
    const meanRSSI = history.reduce((a, b) => a + b, 0) / n;
    const meanY = h - ((meanRSSI - rMin) / range) * (h - 10);
    ctx.strokeStyle = '#fbbf24';
    ctx.lineWidth = 0.8;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(0, meanY);
    ctx.lineTo(w, meanY);
    ctx.stroke();
    ctx.setLineDash([]);
    
    ctx.fillStyle = '#e0e0e0';
    ctx.font = '12px Inter, sans-serif';
    ctx.fillText(`RSSI (dBm): ${currentVal.toFixed(1)}`, 5, 12);
}
