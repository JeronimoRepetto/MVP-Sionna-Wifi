/**
 * MVP-Sionna-WiFi: Ray Path Visualization
 * Renders ray tracing paths with color-coded power levels and animations.
 */

import * as THREE from 'three';

// Color scale: strong signal (red/orange) → weak signal (blue/purple)
const POWER_COLORS = [
    { threshold: -20, color: new THREE.Color(0xff4444) },  // Very strong
    { threshold: -35, color: new THREE.Color(0xff8844) },  // Strong
    { threshold: -50, color: new THREE.Color(0xffcc00) },  // Medium
    { threshold: -65, color: new THREE.Color(0x44cc44) },  // Moderate
    { threshold: -80, color: new THREE.Color(0x4488ff) },  // Weak
    { threshold: -100, color: new THREE.Color(0x8844ff) }, // Very weak
];

const REFLECTION_DOT_SIZE = 0.015;
const RAY_LINE_OPACITY = 0.7;

let raysGroup = null;
let reflectionDots = null;
let pathsData = null;
let animationPhase = 0;
let activeReceiver = 'all';

export function createRays(scene, simulationPaths, offset = { x: 0, y: 0 }) {
    // Remove existing rays
    clearRays(scene);
    
    raysGroup = new THREE.Group();
    raysGroup.name = 'rays';
    reflectionDots = new THREE.Group();
    reflectionDots.name = 'reflection_dots';
    
    pathsData = simulationPaths;
    
    simulationPaths.forEach(rxData => {
        const rxGroup = new THREE.Group();
        rxGroup.name = `rays_${rxData.receiver}`;
        
        rxData.paths.forEach((path, pathIdx) => {
            const vertices = path.vertices;
            if (vertices.length < 2) return;
            
            // Determine color from power
            const color = getPowerColor(path.power_db);
            
            // Create line
            const points = vertices.map(v => new THREE.Vector3(v[0], v[1], v[2]));
            const geometry = new THREE.BufferGeometry().setFromPoints(points);
            
            const material = new THREE.LineBasicMaterial({
                color: color,
                transparent: true,
                opacity: RAY_LINE_OPACITY * Math.min(1, Math.max(0.2, 
                    1 + path.power_db / 100)),
                linewidth: 1,
            });
            
            const line = new THREE.Line(geometry, material);
            line.userData = { pathIdx, power: path.power_db };
            rxGroup.add(line);
            
            // Add reflection dots at intermediate vertices
            for (let i = 1; i < vertices.length - 1; i++) {
                const dotGeo = new THREE.SphereGeometry(REFLECTION_DOT_SIZE, 8, 8);
                const dotMat = new THREE.MeshBasicMaterial({
                    color: color,
                    transparent: true,
                    opacity: 0.8,
                });
                const dot = new THREE.Mesh(dotGeo, dotMat);
                dot.position.set(vertices[i][0], vertices[i][1], vertices[i][2]);
                dot.userData = { receiver: rxData.receiver };
                reflectionDots.add(dot);
            }
        });
        
        raysGroup.add(rxGroup);
    });
    
    // Apply room centering offset
    raysGroup.position.set(offset.x, offset.y, 0);
    reflectionDots.position.set(offset.x, offset.y, 0);
    
    scene.add(raysGroup);
    scene.add(reflectionDots);
    
    // Apply current filter
    filterRaysByReceiver(activeReceiver);
    
    return raysGroup;
}

function getPowerColor(power_db) {
    for (let i = 0; i < POWER_COLORS.length; i++) {
        if (power_db >= POWER_COLORS[i].threshold) {
            return POWER_COLORS[i].color.clone();
        }
    }
    return POWER_COLORS[POWER_COLORS.length - 1].color.clone();
}

export function clearRays(scene) {
    if (raysGroup) {
        scene.remove(raysGroup);
        raysGroup.traverse(c => {
            if (c.geometry) c.geometry.dispose();
            if (c.material) c.material.dispose();
        });
        raysGroup = null;
    }
    if (reflectionDots) {
        scene.remove(reflectionDots);
        reflectionDots.traverse(c => {
            if (c.geometry) c.geometry.dispose();
            if (c.material) c.material.dispose();
        });
        reflectionDots = null;
    }
}

export function filterRaysByReceiver(receiverName) {
    activeReceiver = receiverName;
    if (!raysGroup) return;
    
    raysGroup.children.forEach(rxGroup => {
        const isVisible = receiverName === 'all' || 
                          rxGroup.name === `rays_${receiverName}`;
        rxGroup.visible = isVisible;
    });
    
    // Filter reflection dots too
    if (reflectionDots) {
        reflectionDots.children.forEach(dot => {
            dot.visible = receiverName === 'all' || 
                         dot.userData.receiver === receiverName;
        });
    }
}

export function setRaysVisible(visible) {
    if (raysGroup) raysGroup.visible = visible;
    if (reflectionDots) reflectionDots.visible = visible;
}

export function updateRayAnimations(deltaTime) {
    animationPhase += deltaTime;
    
    if (!raysGroup) return;
    
    // Subtle shimmer animation on ray lines
    raysGroup.traverse(child => {
        if (child.isLine && child.material) {
            const baseOpacity = RAY_LINE_OPACITY * Math.min(1, Math.max(0.2, 
                1 + (child.userData.power || -50) / 100));
            child.material.opacity = baseOpacity * 
                (0.85 + 0.15 * Math.sin(animationPhase * 2 + child.userData.pathIdx * 0.5));
        }
    });
    
    // Pulse reflection dots
    if (reflectionDots) {
        reflectionDots.children.forEach((dot, i) => {
            const s = 1.0 + 0.2 * Math.sin(animationPhase * 3 + i * 0.7);
            dot.scale.set(s, s, s);
        });
    }
}

export function getRaysGroup() {
    return raysGroup;
}
