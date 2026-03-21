"""
MVP-Sionna-WiFi: Pose Library Tests
Validates walking keyframes, interpolation, and trajectory generation.
"""

import sys
import os
import math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from pose_library import (
    WALK_CYCLE_POSES, NUM_WALK_KEYFRAMES,
    interpolate_poses, generate_rectangular_trajectory, generate_walk_sequence,
    _make_pose,
)
import numpy as np


def test_walk_cycle_has_keyframes():
    assert len(WALK_CYCLE_POSES) >= 4
    assert NUM_WALK_KEYFRAMES == len(WALK_CYCLE_POSES)
    print(f"  ✅ Walk cycle has {NUM_WALK_KEYFRAMES} keyframes")


def test_keyframe_shape():
    for i, pose in enumerate(WALK_CYCLE_POSES):
        assert len(pose) == 69, f"Keyframe {i}: expected 69 elements"
    print(f"  ✅ All {NUM_WALK_KEYFRAMES} keyframes have 69 elements")


def test_keyframe_values_finite():
    for i, pose in enumerate(WALK_CYCLE_POSES):
        assert np.all(np.isfinite(np.array(pose))), f"Keyframe {i} has non-finite values"
    print("  ✅ All keyframe values are finite")


def test_keyframe_values_reasonable():
    for i, pose in enumerate(WALK_CYCLE_POSES):
        assert np.max(np.abs(np.array(pose))) < math.pi, f"Keyframe {i}: angle exceeds π"
    print("  ✅ All joint angles are within reasonable bounds")


def test_make_pose_helper():
    pose = _make_pose(L_Hip=[0.5, 0.1, 0.0], R_Knee=[0.3, 0.0, 0.0])
    assert len(pose) == 69
    assert abs(pose[0] - 0.5) < 1e-6
    assert abs(pose[12] - 0.3) < 1e-6
    print("  ✅ _make_pose helper works correctly")


def test_interpolation_basic():
    pose_a = [1.0] * 69
    pose_b = [2.0] * 69
    result_0 = interpolate_poses(pose_a, pose_b, 0.0)
    result_1 = interpolate_poses(pose_a, pose_b, 1.0)
    assert all(abs(a - b) < 1e-6 for a, b in zip(result_0, pose_a))
    assert all(abs(a - b) < 1e-6 for a, b in zip(result_1, pose_b))
    print("  ✅ Interpolation at t=0 and t=1 correct")


def test_interpolation_midpoint():
    pose_a = [0.0] * 69
    pose_b = [2.0] * 69
    result = interpolate_poses(pose_a, pose_b, 0.5)
    assert all(abs(v - 1.0) < 1e-6 for v in result)
    print("  ✅ Interpolation at t=0.5 correct")


def test_interpolation_smooth():
    if len(WALK_CYCLE_POSES) < 2:
        print("  ⏭ Skipped")
        return
    prev = np.array(interpolate_poses(WALK_CYCLE_POSES[0], WALK_CYCLE_POSES[1], 0.0))
    for t in [0.25, 0.5, 0.75, 1.0]:
        curr = np.array(interpolate_poses(WALK_CYCLE_POSES[0], WALK_CYCLE_POSES[1], t))
        assert np.linalg.norm(curr - prev) < 1.0
        prev = curr
    print("  ✅ Interpolation is smooth between keyframes")


def test_rectangular_trajectory():
    """Trajectory should form a rectangle staying inside room bounds."""
    positions, rotations = generate_rectangular_trajectory(16)
    assert len(positions) == 16
    assert len(rotations) == 16
    
    for i, pos in enumerate(positions):
        assert len(pos) == 3
        # XY should be within room (with margin)
        assert 0.0 <= pos[0] <= 2.0, f"Pos {i}: X={pos[0]:.2f} outside room"
        assert 0.0 <= pos[1] <= 3.5, f"Pos {i}: Y={pos[1]:.2f} outside room"
        # Z (height) should be constant at pelvis height
        assert pos[2] == 1.0, f"Pos {i}: Z={pos[2]:.2f} should be 1.0"
    print(f"  ✅ Rectangular trajectory: 16 positions inside room")


def test_trajectory_returns_to_start():
    """Rectangular path should form a closed loop."""
    positions, _ = generate_rectangular_trajectory(32)
    start = positions[0]
    end = positions[-1]
    dist = math.sqrt(sum((a - b)**2 for a, b in zip(start, end)))
    assert dist < 0.5, f"Start-end distance {dist:.2f} too large for a closed loop"
    print("  ✅ Trajectory returns near starting position")


def test_generate_walk_sequence_count():
    for n in [2, 8, 16, 32]:
        seq = generate_walk_sequence(n)
        assert len(seq) == n
    print("  ✅ Walk sequence generates correct frame counts")


def test_walk_sequence_frame_structure():
    seq = generate_walk_sequence(8)
    for i, frame in enumerate(seq):
        assert 'body_pose' in frame
        assert 'transl' in frame
        assert 'global_orient' in frame
        assert 'display_position' in frame
        assert 'sionna_position' in frame
        assert len(frame['body_pose']) == 69
        assert len(frame['transl']) == 3
        assert len(frame['global_orient']) == 3
        assert len(frame['display_position']) == 3
        assert len(frame['sionna_position']) == 3
        # transl should be [0,0,0] — no position baked into mesh
        assert frame['transl'] == [0.0, 0.0, 0.0], f"Frame {i}: transl should be [0,0,0]"
        # display_position Z should be pelvis height
        assert frame['display_position'][2] == 1.0, f"Frame {i}: display Z should be 1.0"
        # sionna_position should be Y-up swap: [x, z_height, y_depth]
        dp = frame['display_position']
        sp = frame['sionna_position']
        assert sp[0] == dp[0], f"Frame {i}: sionna X should match display X"
        assert sp[1] == dp[2], f"Frame {i}: sionna Y should be display Z (height)"
        assert sp[2] == dp[1], f"Frame {i}: sionna Z should be display Y (depth)"
    print("  ✅ All frames have correct structure (transl=[0,0,0], sionna_position matches)")


def test_walk_sequence_stays_in_room():
    """All display positions in the sequence must be inside the room."""
    seq = generate_walk_sequence(16)
    for i, frame in enumerate(seq):
        pos = frame['display_position']
        assert 0.0 <= pos[0] <= 2.0, f"Frame {i}: X={pos[0]:.2f} outside"
        assert 0.0 <= pos[1] <= 3.5, f"Frame {i}: Y={pos[1]:.2f} outside"
    print("  ✅ Walk sequence stays inside room bounds")


# =============================================================================
if __name__ == "__main__":
    tests = [
        test_walk_cycle_has_keyframes, test_keyframe_shape,
        test_keyframe_values_finite, test_keyframe_values_reasonable,
        test_make_pose_helper, test_interpolation_basic,
        test_interpolation_midpoint, test_interpolation_smooth,
        test_rectangular_trajectory, test_trajectory_returns_to_start,
        test_generate_walk_sequence_count, test_walk_sequence_frame_structure,
        test_walk_sequence_stays_in_room,
    ]
    
    print("\n🧪 Pose Library Tests")
    print("=" * 50)
    passed = failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"  ❌ {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  💥 {test.__name__}: {type(e).__name__}: {e}")
            failed += 1
    
    print("=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    if failed > 0:
        sys.exit(1)
    print("✅ All pose library tests passed!\n")
