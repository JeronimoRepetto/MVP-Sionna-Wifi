/**
 * MVP-Sionna-WiFi: 3D Scene Renderer
 * Creates the room geometry with Three.js.
 */

import * as THREE from 'three';

// Room config (updated from backend)
let roomWidth = 2.0;
let roomDepth = 3.5;
let roomHeight = 2.0;
let wallThickness = 0.12;

const WALL_OPACITY = 0.15;
const WALL_COLOR = 0x4a6fa5;
const FLOOR_COLOR = 0x2a3a4a;
const GRID_COLOR = 0x1e3048;
const EDGE_COLOR = 0x5a8abf;

let roomGroup = null;

export function createRoom(scene, config = null) {
    if (config) {
        roomWidth = config.width || 2.0;
        roomDepth = config.depth || 3.5;
        roomHeight = config.height || 2.0;
        wallThickness = config.wall_thickness || 0.12;
    }
    
    // Remove existing room
    if (roomGroup) {
        scene.remove(roomGroup);
        roomGroup.traverse(c => {
            if (c.geometry) c.geometry.dispose();
            if (c.material) {
                if (Array.isArray(c.material)) c.material.forEach(m => m.dispose());
                else c.material.dispose();
            }
        });
    }
    
    roomGroup = new THREE.Group();
    roomGroup.name = 'room';
    
    const hw = roomWidth / 2;
    const hd = roomDepth / 2;
    const hh = roomHeight / 2;
    
    // Wall material (semi-transparent)
    const wallMat = new THREE.MeshStandardMaterial({
        color: WALL_COLOR,
        transparent: true,
        opacity: WALL_OPACITY,
        side: THREE.DoubleSide,
        roughness: 0.9,
        metalness: 0.0,
        depthWrite: false,
    });
    
    // Edge material
    const edgeMat = new THREE.LineBasicMaterial({
        color: EDGE_COLOR,
        transparent: true,
        opacity: 0.6,
    });
    
    // Floor material (slightly more opaque)
    const floorMat = new THREE.MeshStandardMaterial({
        color: FLOOR_COLOR,
        transparent: true,
        opacity: 0.3,
        side: THREE.DoubleSide,
        roughness: 1.0,
    });
    
    // Create volumetric walls
    const t = wallThickness;
    const walls = [
        // Front wall (Y=0, thick across Y). Extend X by 2*t to cover corners
        { w: roomWidth + 2*t, h: roomHeight, d: t, pos: [hw, -t/2, hh] },
        // Back wall (Y=depth, thick across Y). Extend X by 2*t to cover corners
        { w: roomWidth + 2*t, h: roomHeight, d: t, pos: [hw, roomDepth + t/2, hh] },
        // Left wall (X=0, thick across X). Length exactly roomDepth
        { w: t, h: roomHeight, d: roomDepth, pos: [-t/2, hd, hh] },
        // Right wall (X=width, thick across X). Length exactly roomDepth
        { w: t, h: roomHeight, d: roomDepth, pos: [roomWidth + t/2, hd, hh] },
    ];
    
    walls.forEach(({ w, h, d, pos }) => {
        // En ThreeJS: BoxGeometry(width, height, depth) -> (X, Y, Z)
        // Pero nuestro mundo es (X, Y, Z) -> (width, depth, height)
        // Así que pasamos: w, d, h. No necesitamos rotar.
        const tGeo = new THREE.BoxGeometry(w, d, h);
        const mesh = new THREE.Mesh(tGeo, wallMat.clone());
        mesh.position.set(pos[0], pos[1], pos[2]);
        mesh.rotation.set(0, 0, 0); 
        roomGroup.add(mesh);
        
        // Add edges
        const edges = new THREE.EdgesGeometry(tGeo);
        const line = new THREE.LineSegments(edges, edgeMat.clone());
        line.position.copy(mesh.position);
        line.rotation.copy(mesh.rotation);
        roomGroup.add(line);
    });
    
    // Floor
    const floorGeo = new THREE.PlaneGeometry(roomWidth, roomDepth);
    const floor = new THREE.Mesh(floorGeo, floorMat);
    floor.position.set(hw, hd, 0);
    floor.rotation.set(0, 0, 0);
    floor.receiveShadow = true;
    roomGroup.add(floor);
    
    // Floor edges
    const floorEdges = new THREE.EdgesGeometry(floorGeo);
    const floorLine = new THREE.LineSegments(floorEdges, edgeMat.clone());
    floorLine.position.set(hw, hd, 0);
    roomGroup.add(floorLine);
    
    // Ceiling
    const ceilGeo = new THREE.PlaneGeometry(roomWidth, roomDepth);
    const ceil = new THREE.Mesh(ceilGeo, wallMat.clone());
    ceil.material.opacity = 0.08;
    ceil.position.set(hw, hd, roomHeight);
    roomGroup.add(ceil);
    
    // Floor grid
    const gridHelper = createFloorGrid();
    roomGroup.add(gridHelper);
    
    // Ambient axis indicators (subtle)
    addAxisIndicators(roomGroup);
    
    // Lighting  
    addLighting(scene);
    
    // Center the group so the room center is at origin for better orbit
    roomGroup.position.set(-hw, -hd, 0);
    
    scene.add(roomGroup);
    return roomGroup;
}

function createFloorGrid() {
    const group = new THREE.Group();
    const gridMat = new THREE.LineBasicMaterial({
        color: GRID_COLOR,
        transparent: true,
        opacity: 0.4,
    });
    
    const step = 0.5; // 50cm grid
    
    // X lines
    for (let x = 0; x <= roomWidth; x += step) {
        const points = [
            new THREE.Vector3(x, 0, 0.001),
            new THREE.Vector3(x, roomDepth, 0.001),
        ];
        const geo = new THREE.BufferGeometry().setFromPoints(points);
        group.add(new THREE.Line(geo, gridMat));
    }
    
    // Y lines
    for (let y = 0; y <= roomDepth; y += step) {
        const points = [
            new THREE.Vector3(0, y, 0.001),
            new THREE.Vector3(roomWidth, y, 0.001),
        ];
        const geo = new THREE.BufferGeometry().setFromPoints(points);
        group.add(new THREE.Line(geo, gridMat));
    }
    
    return group;
}

function addAxisIndicators(group) {
    const len = 0.3;
    const origin = new THREE.Vector3(0, 0, 0.002);
    
    // X axis (red)
    const xGeo = new THREE.BufferGeometry().setFromPoints([
        origin, new THREE.Vector3(len, 0, 0.002)
    ]);
    group.add(new THREE.Line(xGeo, new THREE.LineBasicMaterial({ color: 0xff4444 })));
    
    // Y axis (green)
    const yGeo = new THREE.BufferGeometry().setFromPoints([
        origin, new THREE.Vector3(0, len, 0.002)
    ]);
    group.add(new THREE.Line(yGeo, new THREE.LineBasicMaterial({ color: 0x44ff44 })));
    
    // Z axis (blue)
    const zGeo = new THREE.BufferGeometry().setFromPoints([
        origin, new THREE.Vector3(0, 0, len)
    ]);
    group.add(new THREE.Line(zGeo, new THREE.LineBasicMaterial({ color: 0x4444ff })));
}

function addLighting(scene) {
    // Remove existing lights
    scene.children
        .filter(c => c.isLight)
        .forEach(c => scene.remove(c));
    
    // Ambient
    const ambient = new THREE.AmbientLight(0x404060, 0.6);
    scene.add(ambient);
    
    // Directional (simulates top-down)
    const dir = new THREE.DirectionalLight(0xffffff, 0.4);
    dir.position.set(2, 3, 5);
    scene.add(dir);
    
    // Point light inside room for soft fill
    const point = new THREE.PointLight(0x5577aa, 0.3, 10);
    point.position.set(roomWidth / 2, roomDepth / 2, roomHeight * 0.8);
    scene.add(point);
}

export function getRoomDimensions() {
    return { width: roomWidth, depth: roomDepth, height: roomHeight };
}

export function getRoomGroup() {
    return roomGroup;
}
