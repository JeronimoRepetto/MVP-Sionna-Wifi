/**
 * MVP-Sionna-WiFi: Coverage Heatmap
 * Renders a 2D signal strength heatmap at a configurable height.
 */

import * as THREE from 'three';

let heatmapMesh = null;
let heatmapData = null;

// Jet colormap: blue → cyan → green → yellow → red
const JET_COLORS = [
    [0.0, 0, 0, 0.5],      // Dark blue
    [0.1, 0, 0, 1],         // Blue
    [0.25, 0, 0.5, 1],      // Cyan-blue
    [0.35, 0, 1, 1],        // Cyan
    [0.45, 0, 1, 0.5],      // Cyan-green
    [0.5, 0, 1, 0],          // Green
    [0.55, 0.5, 1, 0],      // Yellow-green
    [0.65, 1, 1, 0],        // Yellow
    [0.75, 1, 0.5, 0],      // Orange
    [0.85, 1, 0, 0],        // Red
    [1.0, 0.5, 0, 0],       // Dark red
];

export function createHeatmap(scene, coverageData, roomConfig, offset = { x: 0, y: 0 }) {
    // Remove existing
    clearHeatmap(scene);
    
    heatmapData = coverageData;
    heatmapMesh = new THREE.Group();
    heatmapMesh.name = 'heatmap_volume';
    
    const gridW = coverageData.grid_size[0];
    const gridH = coverageData.grid_size[1];
    
    const roomW = roomConfig.width;
    const roomD = roomConfig.depth;
    
    const minDb = coverageData.min_db;
    const maxDb = coverageData.max_db;
    const range = maxDb - minDb || 1;
    
    const opacitySlider = document.getElementById('heatmap-height');
    const baseOpacity = opacitySlider ? parseFloat(opacitySlider.value) : 0.3;
    
    coverageData.slices.forEach(slice => {
        const data = slice.data;
        const canvas = document.createElement('canvas');
        canvas.width = gridW;
        canvas.height = gridH;
        const ctx = canvas.getContext('2d');
        const imageData = ctx.createImageData(gridW, gridH);
        
        for (let i = 0; i < gridW; i++) {
            for (let j = 0; j < gridH; j++) {
                const value = data[i][j];
                const normalized = Math.max(0, Math.min(1, (value - minDb) / range));
                const [r, g, b] = jetColor(normalized);
                
                const pixelIdx = ((gridH - 1 - j) * gridW + i) * 4;
                imageData.data[pixelIdx] = Math.round(r * 255);
                imageData.data[pixelIdx + 1] = Math.round(g * 255);
                imageData.data[pixelIdx + 2] = Math.round(b * 255);
                imageData.data[pixelIdx + 3] = Math.floor(normalized * 200 + 55); 
            }
        }
        
        ctx.putImageData(imageData, 0, 0);
        
        const texture = new THREE.CanvasTexture(canvas);
        texture.magFilter = THREE.LinearFilter;
        texture.minFilter = THREE.LinearFilter;
        
        const phys_W = coverageData.physical_size ? coverageData.physical_size[0] : roomW;
        const phys_D = coverageData.physical_size ? coverageData.physical_size[1] : roomD;
        
        const geometry = new THREE.PlaneGeometry(phys_W, phys_D);
        const material = new THREE.MeshBasicMaterial({
            map: texture,
            transparent: true,
            opacity: baseOpacity,
            side: THREE.DoubleSide,
            depthWrite: false,
            blending: THREE.NormalBlending
        });
        
        const plane = new THREE.Mesh(geometry, material);
        plane.position.set(
            roomW / 2 + offset.x,
            roomD / 2 + offset.y,
            slice.height
        );
        heatmapMesh.add(plane);
    });
    
    scene.add(heatmapMesh);
    
    return heatmapMesh;
}

function jetColor(t) {
    // Interpolate through jet colormap
    t = Math.max(0, Math.min(1, t));
    
    for (let i = 0; i < JET_COLORS.length - 1; i++) {
        const [t0, r0, g0, b0] = JET_COLORS[i];
        const [t1, r1, g1, b1] = JET_COLORS[i + 1];
        
        if (t >= t0 && t <= t1) {
            const f = (t - t0) / (t1 - t0);
            return [
                r0 + f * (r1 - r0),
                g0 + f * (g1 - g0),
                b0 + f * (b1 - b0),
            ];
        }
    }
    
    const last = JET_COLORS[JET_COLORS.length - 1];
    return [last[1], last[2], last[3]];
}

export function setHeatmapHeight(opacity) {
    if (heatmapMesh) {
        heatmapMesh.children.forEach(plane => {
            plane.material.opacity = opacity;
        });
    }
}

export function setHeatmapVisible(visible) {
    if (heatmapMesh) {
        heatmapMesh.visible = visible;
    }
}

export function clearHeatmap(scene) {
    if (heatmapMesh) {
        scene.remove(heatmapMesh);
        heatmapMesh.children.forEach(plane => {
            if (plane.geometry) plane.geometry.dispose();
            if (plane.material) {
                if (plane.material.map) plane.material.map.dispose();
                plane.material.dispose();
            }
        });
        heatmapMesh = null;
    }
}
