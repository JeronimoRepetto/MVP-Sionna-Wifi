"""
MVP-Sionna-WiFi: SMPL Pose Library
Predefined walking keyframes for realistic human animation.

Each keyframe defines body_pose (69 floats = 23 joints × 3 axis-angle rotations).
Key joints for walking: hips (L/R), knees, ankles, shoulders, elbows, spine.

SMPL Joint indices (body_pose only, excluding root):
  0: L_Hip, 1: R_Hip, 2: Spine1
  3: L_Knee, 4: R_Knee, 5: Spine2
  6: L_Ankle, 7: R_Ankle, 8: Spine3
  9: L_Foot, 10: R_Foot, 11: Neck
  12: L_Collar, 13: R_Collar, 14: Head
  15: L_Shoulder, 16: R_Shoulder, 17: L_Elbow
  18: R_Elbow, 19: L_Wrist, 20: R_Wrist
  21: L_Hand, 22: R_Hand

Coordinate systems:
  SMPL / Three.js (Y-up): X=right, Y=up, Z=forward
  Mitsuba scene  (Z-up):  X=width, Y=depth, Z=height
  
  The OBJ vertices are swapped (Y↔Z) in smpl_manager.save_obj() so Sionna 
  sees Z-up coordinates. The transl values in the animation sequence are in
  Three.js/SMPL coordinates (Y-up).
"""

import numpy as np
import math


# Helper: create a body_pose with specific joint overrides
def _make_pose(**joint_overrides):
    """
    Create a 69-element body_pose array with specified joint rotations.
    joint_overrides: dict mapping joint_name -> [rx, ry, rz] axis-angle.
    """
    pose = np.zeros(69, dtype=np.float64)
    
    JOINT_MAP = {
        'L_Hip': 0, 'R_Hip': 1, 'Spine1': 2,
        'L_Knee': 3, 'R_Knee': 4, 'Spine2': 5,
        'L_Ankle': 6, 'R_Ankle': 7, 'Spine3': 8,
        'L_Foot': 9, 'R_Foot': 10, 'Neck': 11,
        'L_Collar': 12, 'R_Collar': 13, 'Head': 14,
        'L_Shoulder': 15, 'R_Shoulder': 16, 'L_Elbow': 17,
        'R_Elbow': 18, 'L_Wrist': 19, 'R_Wrist': 20,
        'L_Hand': 21, 'R_Hand': 22,
    }
    
    for joint_name, angles in joint_overrides.items():
        if joint_name in JOINT_MAP:
            idx = JOINT_MAP[joint_name] * 3
            pose[idx:idx+3] = angles
    
    return pose.tolist()


# =============================================================================
# Walking Keyframes — One Full Gait Cycle
# =============================================================================

WALK_CYCLE_POSES = [
    # Frame 0: Neutral standing
    _make_pose(
        Spine1=[0.03, 0, 0],
    ),
    
    # Frame 1: Right leg forward (heel strike), left leg back
    _make_pose(
        L_Hip=[-0.35, 0, 0.05],
        R_Hip=[0.45, 0, -0.05],
        L_Knee=[0.15, 0, 0],
        R_Knee=[0.05, 0, 0],
        L_Ankle=[-0.1, 0, 0],
        R_Ankle=[0.15, 0, 0],
        Spine1=[0.05, 0, 0],
        Spine2=[0.02, 0, -0.03],
        L_Shoulder=[0.3, 0, 0.05],
        R_Shoulder=[-0.3, 0, -0.05],
        L_Elbow=[0.15, 0, 0],
        R_Elbow=[0.1, 0, 0],
    ),
    
    # Frame 2: Right leg passing (mid-stance right)
    _make_pose(
        L_Hip=[-0.15, 0, 0.03],
        R_Hip=[0.15, 0, -0.03],
        L_Knee=[0.55, 0, 0],
        R_Knee=[0.1, 0, 0],
        Spine1=[0.04, 0, 0],
        L_Shoulder=[0.1, 0, 0.03],
        R_Shoulder=[-0.1, 0, -0.03],
        L_Elbow=[0.2, 0, 0],
        R_Elbow=[0.15, 0, 0],
    ),
    
    # Frame 3: Left leg forward (heel strike), right leg back
    _make_pose(
        L_Hip=[0.45, 0, -0.05],
        R_Hip=[-0.35, 0, 0.05],
        L_Knee=[0.05, 0, 0],
        R_Knee=[0.15, 0, 0],
        L_Ankle=[0.15, 0, 0],
        R_Ankle=[-0.1, 0, 0],
        Spine1=[0.05, 0, 0],
        Spine2=[0.02, 0, 0.03],
        L_Shoulder=[-0.3, 0, -0.05],
        R_Shoulder=[0.3, 0, 0.05],
        L_Elbow=[0.1, 0, 0],
        R_Elbow=[0.15, 0, 0],
    ),
    
    # Frame 4: Left leg passing (mid-stance left)
    _make_pose(
        L_Hip=[0.15, 0, -0.03],
        R_Hip=[-0.15, 0, 0.03],
        L_Knee=[0.1, 0, 0],
        R_Knee=[0.55, 0, 0],
        Spine1=[0.04, 0, 0],
        L_Shoulder=[-0.1, 0, -0.03],
        R_Shoulder=[0.1, 0, 0.03],
        L_Elbow=[0.15, 0, 0],
        R_Elbow=[0.2, 0, 0],
    ),
    
    # Frame 5: Right leg forward again
    _make_pose(
        L_Hip=[-0.35, 0, 0.05],
        R_Hip=[0.45, 0, -0.05],
        L_Knee=[0.15, 0, 0],
        R_Knee=[0.05, 0, 0],
        L_Ankle=[-0.1, 0, 0],
        R_Ankle=[0.15, 0, 0],
        Spine1=[0.05, 0, 0],
        Spine2=[0.02, 0, -0.03],
        L_Shoulder=[0.3, 0, 0.05],
        R_Shoulder=[-0.3, 0, -0.05],
        L_Elbow=[0.15, 0, 0],
        R_Elbow=[0.1, 0, 0],
    ),
    
    # Frame 6: Neutral standing (ending pose)
    _make_pose(
        Spine1=[0.03, 0, 0],
    ),
]

NUM_WALK_KEYFRAMES = len(WALK_CYCLE_POSES)


def interpolate_poses(pose_a, pose_b, t):
    """Linearly interpolate between two body_pose arrays. t in [0, 1]."""
    a = np.array(pose_a, dtype=np.float64)
    b = np.array(pose_b, dtype=np.float64)
    return (a * (1 - t) + b * t).tolist()


def generate_rectangular_trajectory(num_frames, room_width=2.0, room_depth=3.5,
                                     margin=0.4, pelvis_height=1.0):
    """
    Generate a rectangular loop trajectory inside the room.
    
    The model walks in a rectangle: forward → right → back → left → repeat.
    Coordinates match the Three.js scene Z-up system:
        [0] = X (width)
        [1] = Y (depth/forward)
        [2] = Z (height, constant — pelvis height above floor)
    
    Args:
        num_frames: Total number of frames
        room_width: Room width in meters
        room_depth: Room depth in meters
        margin: Distance from walls
        pelvis_height: Z position (height of pelvis above floor, ~1.0m)
    
    Returns:
        List of [x, y, z] positions, list of Z-rotation angles (facing direction)
    """
    # Rectangle corners (in XY plane, Z=height constant)
    x_min = margin
    x_max = room_width - margin
    y_min = margin
    y_max = room_depth - margin
    
    # Define corners: walk forward (+Y), right (+X), back (-Y), left (-X)
    corners = [
        (x_min, y_min),  # Start: near-left
        (x_min, y_max),  # Walk forward (+Y)
        (x_max, y_max),  # Turn right, walk right (+X)
        (x_max, y_min),  # Turn right, walk back (-Y)
        (x_min, y_min),  # Turn right, walk left (-X) → back to start
    ]
    
    # Facing directions (Z-axis rotation, radians)
    # 0 = facing +Y, π/2 = facing -X, π = facing -Y, -π/2 = facing +X
    facing = [0.0, -math.pi / 2, math.pi, math.pi / 2]
    
    # Calculate total perimeter length
    segments = []
    total_length = 0.0
    for i in range(len(corners) - 1):
        dx = corners[i+1][0] - corners[i][0]
        dy = corners[i+1][1] - corners[i][1]
        seg_len = math.sqrt(dx*dx + dy*dy)
        segments.append(seg_len)
        total_length += seg_len
    
    # Distribute frames along perimeter
    positions = []
    rotations = []
    
    for f in range(num_frames):
        t = f / max(num_frames - 1, 1)
        dist = t * total_length
        
        # Find which segment we're on
        accumulated = 0.0
        for seg_idx, seg_len in enumerate(segments):
            if accumulated + seg_len >= dist or seg_idx == len(segments) - 1:
                # Interpolate within this segment
                local_t = (dist - accumulated) / max(seg_len, 0.001)
                local_t = min(max(local_t, 0.0), 1.0)
                
                x = corners[seg_idx][0] + local_t * (corners[seg_idx+1][0] - corners[seg_idx][0])
                y = corners[seg_idx][1] + local_t * (corners[seg_idx+1][1] - corners[seg_idx][1])
                
                positions.append([x, y, pelvis_height])
                rotations.append(facing[seg_idx])
                break
            accumulated += seg_len
    
    return positions, rotations


# Keep the old function signature for backward compatibility with tests
def generate_walk_trajectory(num_frames, depth_start=0.5, depth_end=3.0,
                             x_pos=1.0, height=0.0):
    """Generate straight-line trajectory (deprecated, use rectangular)."""
    positions, _ = generate_rectangular_trajectory(num_frames)
    return positions


def generate_walk_sequence(num_frames, depth_start=0.5, depth_end=3.0, x_pos=1.0):
    """
    Generate a complete walk animation sequence with rectangular loop.
    
    The human walks in a rectangle inside the room. Each frame contains:
      - body_pose: interpolated walking keyframes
      - transl: [0,0,0] — NO position baked into mesh vertices
      - global_orient: facing direction
      - display_position: Three.js Z-up coords [x, y_depth, z_height]
      - sionna_position: SMPL Y-up coords [x, z_height, y_depth] for Sionna sim
    
    Args:
        num_frames: Total number of animation frames (minimum 2)
    
    Returns:
        List of frame dicts
    """
    num_frames = max(num_frames, 2)
    
    positions, rotations = generate_rectangular_trajectory(num_frames)
    
    cycle_kfs = WALK_CYCLE_POSES
    num_kf = len(cycle_kfs)
    
    sequence = []
    for i in range(num_frames):
        t = i / max(num_frames - 1, 1)
        
        kf_float = t * (num_kf - 1)
        kf_idx = int(kf_float)
        kf_frac = kf_float - kf_idx
        kf_idx = min(kf_idx, num_kf - 2)
        
        body_pose = interpolate_poses(cycle_kfs[kf_idx], cycle_kfs[kf_idx + 1], kf_frac)
        
        pos = positions[i]  # [x, y_depth, z_height] Three.js Z-up
        
        sequence.append({
            'body_pose': body_pose,
            'transl': [0.0, 0.0, 0.0],  # No position in mesh — prevents double-apply
            'global_orient': [0.0, rotations[i], 0.0],
            'display_position': pos,  # Three.js Z-up [x, y_depth, z_height]
            'sionna_position': [pos[0], pos[2], pos[1]],  # SMPL Y-up [x, z_height, y_depth]
        })
    
    return sequence


# =============================================================================
# Self-test
# =============================================================================
if __name__ == "__main__":
    print(f"Walk cycle keyframes: {NUM_WALK_KEYFRAMES}")
    print(f"Each keyframe has {len(WALK_CYCLE_POSES[0])} values (expect 69)")
    
    seq = generate_walk_sequence(16)
    print(f"\nGenerated walk sequence: {len(seq)} frames")
    for i, frame in enumerate(seq):
        pos = frame['transl']
        orient = frame['global_orient'][1]
        print(f"  Frame {i:2d}: X={pos[0]:.2f} Y={pos[1]:.2f} Z={pos[2]:.2f}  "
              f"facing={math.degrees(orient):.0f}°  "
              f"body_pose_nonzero={sum(1 for v in frame['body_pose'] if abs(v) > 0.001)}")
