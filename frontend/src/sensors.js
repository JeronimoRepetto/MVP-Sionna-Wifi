/**
 * MVP-Sionna-WiFi: Sensor Visualization
 * Renders transmitter (Router) and receivers (ESP32-S3) in 3D.
 */

import * as THREE from 'three';

const TX_COLOR = 0xf59e0b;       // Orange/gold for router
const TX_GLOW_COLOR = 0xfbbf24;
const RX_COLOR_HIGH = 0x3b82f6;  // Blue for high receivers
const RX_COLOR_LOW = 0x8b5cf6;   // Purple for low receivers
const RX_ACTIVE = 0x76B900;      // NVIDIA green when selected
const LABEL_OFFSET_Y = 0.15;

let sensorsGroup = null;
let txMesh = null;
let rxMeshes = {};
let labels = [];
let pulsePhase = 0;
let roomOffset = { x: 0, y: 0 };

export function createSensors(scene, sceneInfo, offset = { x: 0, y: 0 }) {
    roomOffset = offset;
    
    // Remove existing
    if (sensorsGroup) {
        scene.remove(sensorsGroup);
        sensorsGroup.traverse(c => {
            if (c.geometry) c.geometry.dispose();
            if (c.material) {
                if (Array.isArray(c.material)) c.material.forEach(m => m.dispose());
                else c.material.dispose();
            }
        });
    }
    
    sensorsGroup = new THREE.Group();
    sensorsGroup.name = 'sensors';
    rxMeshes = {};
    labels = [];
    
    // Create transmitter
    txMesh = createTransmitter(sceneInfo.transmitter);
    sensorsGroup.add(txMesh);
    
    // Create receivers
    sceneInfo.receivers.forEach(rx => {
        const rxGroup = createReceiver(rx);
        rxMeshes[rx.name] = rxGroup;
        sensorsGroup.add(rxGroup);
    });
    
    // Apply room centering offset
    sensorsGroup.position.set(offset.x, offset.y, 0);
    
    scene.add(sensorsGroup);
    return sensorsGroup;
}

function createTransmitter(txInfo) {
    const group = new THREE.Group();
    const pos = txInfo.position;
    
    // Main sphere
    const geo = new THREE.SphereGeometry(0.06, 24, 24);
    const mat = new THREE.MeshStandardMaterial({
        color: TX_COLOR,
        emissive: TX_COLOR,
        emissiveIntensity: 0.5,
        roughness: 0.3,
        metalness: 0.7,
    });
    const sphere = new THREE.Mesh(geo, mat);
    sphere.name = 'tx_sphere';
    group.add(sphere);
    
    // Glow ring
    const ringGeo = new THREE.RingGeometry(0.08, 0.12, 32);
    const ringMat = new THREE.MeshBasicMaterial({
        color: TX_GLOW_COLOR,
        transparent: true,
        opacity: 0.3,
        side: THREE.DoubleSide,
    });
    const ring = new THREE.Mesh(ringGeo, ringMat);
    ring.name = 'tx_ring';
    group.add(ring);
    
    // Outer pulse ring
    const pulseGeo = new THREE.RingGeometry(0.12, 0.14, 32);
    const pulseMat = new THREE.MeshBasicMaterial({
        color: TX_GLOW_COLOR,
        transparent: true,
        opacity: 0.15,
        side: THREE.DoubleSide,
    });
    const pulse = new THREE.Mesh(pulseGeo, pulseMat);
    pulse.name = 'tx_pulse';
    group.add(pulse);
    
    // Point light for glow effect
    const light = new THREE.PointLight(TX_COLOR, 0.5, 2);
    group.add(light);
    
    group.position.set(pos[0], pos[1], pos[2]);
    group.name = 'transmitter';
    
    return group;
}

function createReceiver(rxInfo) {
    const group = new THREE.Group();
    const pos = rxInfo.position;
    const isHigh = pos[2] > 1.0;
    const baseColor = isHigh ? RX_COLOR_HIGH : RX_COLOR_LOW;
    
    // ESP32 box
    const geo = new THREE.BoxGeometry(0.04, 0.04, 0.02);
    const mat = new THREE.MeshStandardMaterial({
        color: baseColor,
        emissive: baseColor,
        emissiveIntensity: 0.2,
        roughness: 0.5,
        metalness: 0.3,
    });
    const box = new THREE.Mesh(geo, mat);
    box.name = 'rx_box';
    group.add(box);
    
    // Antenna stub
    const antGeo = new THREE.CylinderGeometry(0.003, 0.003, 0.05, 8);
    const antMat = new THREE.MeshStandardMaterial({
        color: 0xaaaaaa,
        metalness: 0.8,
        roughness: 0.2,
    });
    const antenna = new THREE.Mesh(antGeo, antMat);
    antenna.position.y = 0.035;
    antenna.rotation.x = Math.PI / 2;
    group.add(antenna);
    
    // Small signal indicator sphere
    const indGeo = new THREE.SphereGeometry(0.008, 12, 12);
    const indMat = new THREE.MeshBasicMaterial({
        color: baseColor,
        transparent: true,
        opacity: 0.6,
    });
    const indicator = new THREE.Mesh(indGeo, indMat);
    indicator.position.y = 0.06;
    indicator.rotation.x = Math.PI / 2;
    indicator.name = 'rx_indicator';
    group.add(indicator);
    
    group.position.set(pos[0], pos[1], pos[2]);
    group.name = rxInfo.name;
    group.userData = { ...rxInfo, baseColor };
    
    return group;
}

export function setActiveReceiver(name) {
    Object.entries(rxMeshes).forEach(([rxName, group]) => {
        const box = group.getObjectByName('rx_box');
        const indicator = group.getObjectByName('rx_indicator');
        if (!box) return;
        
        if (name === 'all' || rxName === name) {
            box.material.color.set(RX_ACTIVE);
            box.material.emissive.set(RX_ACTIVE);
            box.material.emissiveIntensity = 0.5;
            if (indicator) indicator.material.color.set(RX_ACTIVE);
        } else {
            const baseColor = group.userData.baseColor;
            box.material.color.set(baseColor);
            box.material.emissive.set(baseColor);
            box.material.emissiveIntensity = 0.2;
            if (indicator) indicator.material.color.set(baseColor);
        }
    });
}

export function updateSensorAnimations(deltaTime) {
    pulsePhase += deltaTime * 2;
    
    if (!txMesh) return;
    
    // Animate TX pulse rings
    const ring = txMesh.getObjectByName('tx_ring');
    const pulse = txMesh.getObjectByName('tx_pulse');
    
    if (ring) {
        const s = 1.0 + 0.15 * Math.sin(pulsePhase * 2);
        ring.scale.set(s, s, 1);
        ring.material.opacity = 0.2 + 0.1 * Math.sin(pulsePhase * 2);
    }
    
    if (pulse) {
        const s = 1.0 + 0.3 * Math.sin(pulsePhase);
        pulse.scale.set(s, s, 1);
        pulse.material.opacity = 0.1 + 0.05 * Math.sin(pulsePhase);
    }
    
    // Make TX sphere gently bob
    const sphere = txMesh.getObjectByName('tx_sphere');
    if (sphere) {
        sphere.material.emissiveIntensity = 0.4 + 0.2 * Math.sin(pulsePhase * 3);
    }
}

export function getSensorsGroup() {
    return sensorsGroup;
}
