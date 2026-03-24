/**
 * MVP-Sionna-WiFi: WebSocket Client
 * Manages connection to the FastAPI backend.
 */

const WS_URL = `ws://${window.location.hostname}:8000/ws/simulation`;
const RECONNECT_DELAY = 3000;

let ws = null;
let onMessageCallback = null;
let onStatusChangeCallback = null;
let reconnectTimer = null;

export function initWebSocket(onMessage, onStatusChange) {
    onMessageCallback = onMessage;
    onStatusChangeCallback = onStatusChange;
    connect();
}

function connect() {
    if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
    }
    
    try {
        ws = new WebSocket(WS_URL);
    } catch (e) {
        console.warn('WebSocket connection failed:', e);
        scheduleReconnect();
        return;
    }
    
    ws.onopen = () => {
        console.log('🔌 WebSocket connected');
        onStatusChangeCallback?.('connected');
        // Request scene info on connect
        sendMessage({ action: 'get_scene' });
    };
    
    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            onMessageCallback?.(data);
        } catch (e) {
            console.error('Failed to parse WebSocket message:', e);
        }
    };
    
    ws.onclose = () => {
        console.log('🔌 WebSocket disconnected');
        onStatusChangeCallback?.('disconnected');
        scheduleReconnect();
    };
    
    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        onStatusChangeCallback?.('disconnected');
    };
}

function scheduleReconnect() {
    if (!reconnectTimer) {
        reconnectTimer = setTimeout(() => {
            console.log('🔄 Reconnecting WebSocket...');
            connect();
        }, RECONNECT_DELAY);
    }
}

export function sendMessage(data) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(data));
        return true;
    }
    return false;
}

export function requestSimulation(params = {}) {
    return sendMessage({
        action: 'simulate',
        params: params,
    });
}

export function requestAnimation(params = {}) {
    return sendMessage({
        action: 'animate',
        params: params,
    });
}

export function stopAnimationWs() {
    return sendMessage({
        action: 'stop_animation',
    });
}

export function isConnected() {
    return ws && ws.readyState === WebSocket.OPEN;
}

// Synchronized walk simulation (frame-by-frame with Sionna)
export function requestSimWalk(params = {}) {
    return sendMessage({ action: 'sim_walk', params });
}

export function pauseSimWalk() {
    return sendMessage({ action: 'pause_sim_walk' });
}

export function resumeSimWalk() {
    return sendMessage({ action: 'resume_sim_walk' });
}

export function stopSimWalk() {
    return sendMessage({ action: 'stop_sim_walk' });
}
