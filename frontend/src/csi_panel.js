/**
 * MVP-Sionna-WiFi: CSI Spectrogram Panel
 * Visualizes the 114 OFDM subcarriers similar to the wifi-csi-capture tool.
 * Draws Amplitude, Phase, Spectrogram, and RSSI.
 */

const MAX_SUBCARRIERS = 114;
const HISTORY_LEN = 100;
let animationId = null;
let currentReceiver = null;
let active = false;

// We fake continuous data by adding noise to the static mock CSI
// This creates the "turbulence" required to see a live spectrogram
let baseCSI_Amp = new Float32Array(MAX_SUBCARRIERS);
let baseCSI_Phase = new Float32Array(MAX_SUBCARRIERS);
let baseRSSI = -50;

// History buffers
const ampHistory = [];
const rssiHistory = [];
const frameCount = { value: 0 };

// Canvas Contexts
let ctxAmp, ctxPhase, ctxSpectro, ctxRssi;

const jetColormap = (t) => {
    t = Math.max(0, Math.min(1, t));
    const r = Math.max(0, Math.min(255, Math.round(255 * (1.5 - Math.abs(1 - 4 * (t - 0.75))))));
    const g = Math.max(0, Math.min(255, Math.round(255 * (1.5 - Math.abs(1 - 4 * (t - 0.5))))));
    const b = Math.max(0, Math.min(255, Math.round(255 * (1.5 - Math.abs(1 - 4 * (t - 0.25))))));
    return `rgb(${r},${g},${b})`;
};

export function initCSIPanel() {
    ctxAmp = document.getElementById('chart-amp').getContext('2d');
    ctxPhase = document.getElementById('chart-phase').getContext('2d');
    ctxSpectro = document.getElementById('chart-spectro').getContext('2d');
    ctxRssi = document.getElementById('chart-rssi').getContext('2d');
    
    document.getElementById('close-csi-btn').addEventListener('click', closeCSI);
    
    // Fill initial history
    for(let i=0; i<HISTORY_LEN; i++) {
        ampHistory.push(new Float32Array(MAX_SUBCARRIERS));
        rssiHistory.push(-90);
    }
}

export function openCSI(receiverName, csiData, rssiData) {
    if (!ctxAmp) initCSIPanel();
    
    currentReceiver = receiverName;
    document.getElementById('csi-rx-name').textContent = receiverName;
    document.getElementById('csi-panel').classList.remove('hidden');
    active = true;
    
    if (csiData) {
        updateBaseData(csiData, rssiData);
    }
    
    if (!animationId) {
        lastTime = performance.now();
        animationId = requestAnimationFrame(renderLoop);
    }
}

export function closeCSI() {
    document.getElementById('csi-panel').classList.add('hidden');
    active = false;
    currentReceiver = null;
    if (animationId) {
        cancelAnimationFrame(animationId);
        animationId = null;
    }
}

export function updateBaseData(csiData, rssiData) {
    baseRSSI = rssiData;
    // Extract 114 subcarriers from the flat array [amp1, phase1, amp2, phase2...]
    // If not matching, pad or truncate
    const subcount = Math.min(MAX_SUBCARRIERS, csiData.length / 2);
    for (let i = 0; i < subcount; i++) {
        baseCSI_Amp[i] = csiData[2*i] * 50;   // Scaling factor for visibility
        baseCSI_Phase[i] = csiData[2*i + 1];
    }
}

// Generate one frame of noisy data from the base CSI to animate the spectrogram
function generateFrame() {
    const amp = new Float32Array(MAX_SUBCARRIERS);
    const phase = new Float32Array(MAX_SUBCARRIERS);
    
    const noiseLevel = 0.05; // 5% noise
    for (let i = 0; i < MAX_SUBCARRIERS; i++) {
        amp[i] = Math.max(0, baseCSI_Amp[i] * (1.0 + (Math.random() * 2 - 1) * noiseLevel));
        phase[i] = baseCSI_Phase[i] + (Math.random() * 0.2 - 0.1);
    }
    
    // RSSI with +-1 dBm wobble
    const rssi = baseRSSI + (Math.random() * 2 - 1);
    
    ampHistory.shift();
    ampHistory.push(amp);
    
    rssiHistory.shift();
    rssiHistory.push(rssi);
    
    frameCount.value++;
    return { amp, phase, rssi };
}

let lastTime = 0;
function renderLoop(time) {
    if (!active) return;
    
    const dt = time - lastTime;
    if (dt > 30) { // ~30 fps max
        lastTime = time;
        const data = generateFrame();
        
        drawAmp(ctxAmp, data.amp);
        drawPhase(ctxPhase, data.phase);
        drawSpectro(ctxSpectro);
        drawRssi(ctxRssi, data.rssi);
        
        document.getElementById('csi-status').textContent = 
            `Frames: ${frameCount.value} | Subcarriers: ${MAX_SUBCARRIERS} | RSSI: ${data.rssi.toFixed(1)} dBm | Live Simulation`;
    }
    
    animationId = requestAnimationFrame(renderLoop);
}

// --- Renderers ---

function drawAmp(ctx, amp) {
    const canvas = ctx.canvas;
    const w = canvas.width = canvas.clientWidth;
    const h = canvas.height = canvas.clientHeight;
    
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#00d4ff";
    
    const maxVal = Math.max(10, Math.max(...amp) * 1.2);
    const bw = w / MAX_SUBCARRIERS;
    
    for (let i = 0; i < MAX_SUBCARRIERS; i++) {
        const hBar = (amp[i] / maxVal) * h;
        ctx.fillRect(i * bw, h - hBar, bw > 1 ? bw - 1 : bw, hBar);
    }
    
    // Title
    ctx.fillStyle = "#e0e0e0";
    ctx.font = "12px Inter";
    ctx.fillText("Subcarrier Amplitude", 5, 12);
}

function drawPhase(ctx, phase) {
    const canvas = ctx.canvas;
    const w = canvas.width = canvas.clientWidth;
    const h = canvas.height = canvas.clientHeight;
    
    ctx.clearRect(0, 0, w, h);
    ctx.strokeStyle = "#ff6b6b";
    ctx.lineWidth = 1.5;
    
    ctx.beginPath();
    const bw = w / MAX_SUBCARRIERS;
    for (let i = 0; i < MAX_SUBCARRIERS; i++) {
        const px = i * bw + bw/2;
        // Map -PI .. PI to h .. 0
        const py = h - ((phase[i] + Math.PI) / (2 * Math.PI)) * h;
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
    }
    ctx.stroke();
    
    ctx.fillStyle = "#e0e0e0";
    ctx.font = "12px Inter";
    ctx.fillText("Subcarrier Phase (rad)", 5, 12);
}

function drawSpectro(ctx) {
    const canvas = ctx.canvas;
    const w = canvas.width = canvas.clientWidth;
    const h = canvas.height = canvas.clientHeight;
    
    // Find absolute max in history for normalization
    let maxVal = 0.01;
    for (let row of ampHistory) {
        for (let val of row) if (val > maxVal) maxVal = val;
    }
    
    const imgData = ctx.createImageData(w, h);
    const data = imgData.data;
    
    const cols = MAX_SUBCARRIERS;
    const rows = HISTORY_LEN;
    
    const cellW = w / cols;
    const cellH = h / rows;
    
    // Paint pixels
    for (let y = 0; y < h; y++) {
        // Map y to history row (0 is newest at bottom, so h is old)
        const rowIdx = rows - 1 - Math.min(rows - 1, Math.floor((y / h) * rows));
        const rowData = ampHistory[rowIdx];
        
        for (let x = 0; x < w; x++) {
            const colIdx = Math.min(cols - 1, Math.floor((x / w) * cols));
            const val = rowData[colIdx] / maxVal; // 0..1
            
            // Jet colormap inline
            const t = Math.max(0, Math.min(1, val));
            const r = Math.max(0, Math.min(255, Math.round(255 * (1.5 - Math.abs(1 - 4 * (t - 0.75))))));
            const g = Math.max(0, Math.min(255, Math.round(255 * (1.5 - Math.abs(1 - 4 * (t - 0.5))))));
            const b = Math.max(0, Math.min(255, Math.round(255 * (1.5 - Math.abs(1 - 4 * (t - 0.25))))));
            
            const idx = (y * w + x) * 4;
            data[idx] = r;
            data[idx+1] = g;
            data[idx+2] = b;
            data[idx+3] = 255;
        }
    }
    
    ctx.putImageData(imgData, 0, 0);
    
    ctx.fillStyle = "#e0e0e0";
    ctx.font = "12px Inter";
    ctx.fillText("Amplitude Spectrogram", 5, 12);
}

function drawRssi(ctx, currentVal) {
    const canvas = ctx.canvas;
    const w = canvas.width = canvas.clientWidth;
    const h = canvas.height = canvas.clientHeight;
    
    ctx.clearRect(0, 0, w, h);
    ctx.strokeStyle = "#38bdf8";
    ctx.lineWidth = 1.5;
    
    ctx.beginPath();
    const bw = w / HISTORY_LEN;
    for (let i = 0; i < HISTORY_LEN; i++) {
        const val = rssiHistory[i];
        const px = i * bw;
        // Map -90..-30 to h..0
        let py = h - ((val - (-90)) / 60) * h;
        py = Math.max(0, Math.min(h, py));
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
    }
    ctx.stroke();
    
    ctx.fillStyle = "#e0e0e0";
    ctx.font = "12px Inter";
    ctx.fillText(`RSSI (dBm): ${currentVal.toFixed(1)}`, 5, 12);
}
