"""
MVP-Sionna-WiFi: Animation Pipeline Tests
Validates the SMPLManager walk sequence generation and frame export.

NOTE: These tests require the SMPL model files to be present.
Tests that require SMPL will be gracefully skipped if models are missing.
"""

import sys
import os
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


# Check if SMPL models are available
def _smpl_available():
    try:
        from smpl_manager import SMPLManager
        mgr = SMPLManager()
        mgr.load_model()
        return True
    except Exception:
        return False


SMPL_AVAILABLE = _smpl_available()


def test_pose_library_imported_by_smpl_manager():
    """SMPLManager should import pose_library without errors."""
    from smpl_manager import SMPLManager
    mgr = SMPLManager()
    # Verify the method exists
    assert hasattr(mgr, 'generate_walk_sequence'), \
        "SMPLManager missing generate_walk_sequence method"
    assert hasattr(mgr, 'save_walk_sequence_objs'), \
        "SMPLManager missing save_walk_sequence_objs method"
    print("  ✅ SMPLManager has walk sequence methods")


def test_generate_walk_sequence_returns_correct_count():
    """generate_walk_sequence(N) must return exactly N frames."""
    from smpl_manager import SMPLManager
    mgr = SMPLManager()
    
    for n in [4, 8, 16]:
        seq = mgr.generate_walk_sequence(n)
        assert len(seq) == n, f"Expected {n} frames, got {len(seq)}"
    print("  ✅ Walk sequence returns correct frame counts")


def test_walk_sequence_frame_structure():
    """Each frame must have body_pose, transl, global_orient."""
    from smpl_manager import SMPLManager
    mgr = SMPLManager()
    seq = mgr.generate_walk_sequence(8)
    
    for i, frame in enumerate(seq):
        assert 'body_pose' in frame, f"Frame {i} missing body_pose"
        assert 'transl' in frame, f"Frame {i} missing transl"
        assert 'global_orient' in frame, f"Frame {i} missing global_orient"
    print("  ✅ Frame structure is correct")


def test_walk_sequence_translation_progresses():
    """Translation Y-values should increase monotonically."""
    from smpl_manager import SMPLManager
    mgr = SMPLManager()
    seq = mgr.generate_walk_sequence(16)
    
    for i in range(1, len(seq)):
        assert seq[i]['transl'][1] >= seq[i-1]['transl'][1], \
            f"Frame {i}: Y decreased"
    print("  ✅ Translation progresses along Y-axis")


def test_smpl_manager_generates_obj_for_single_frame():
    """SMPLManager should generate a valid .obj file for one frame."""
    if not SMPL_AVAILABLE:
        print("  ⏭ Skipped (SMPL model files not available)")
        return
    
    from smpl_manager import SMPLManager
    mgr = SMPLManager()
    
    tmp_dir = tempfile.mkdtemp()
    try:
        obj_path = os.path.join(tmp_dir, "test_frame.obj")
        seq = mgr.generate_walk_sequence(1)
        frame = seq[0]
        
        mgr.save_obj(
            obj_path,
            body_pose=frame['body_pose'],
            global_orient=frame['global_orient'],
            transl=frame['transl'],
        )
        
        assert os.path.exists(obj_path), "OBJ file was not created"
        assert os.path.getsize(obj_path) > 100, "OBJ file is too small"
        
        # Verify it's a valid OBJ (has vertices and faces)
        with open(obj_path, 'r') as f:
            content = f.read()
            assert 'v ' in content, "OBJ missing vertex data"
            assert 'f ' in content, "OBJ missing face data"
        
        print(f"  ✅ Generated OBJ: {os.path.getsize(obj_path)} bytes")
    finally:
        shutil.rmtree(tmp_dir)


def test_smpl_manager_generates_walk_sequence_objs():
    """save_walk_sequence_objs should create OBJ files for all frames."""
    if not SMPL_AVAILABLE:
        print("  ⏭ Skipped (SMPL model files not available)")
        return
    
    from smpl_manager import SMPLManager
    mgr = SMPLManager()
    
    tmp_dir = tempfile.mkdtemp()
    try:
        num_frames = 4
        paths, sequence = mgr.save_walk_sequence_objs(
            tmp_dir, num_frames=num_frames
        )
        
        assert len(paths) == num_frames, \
            f"Expected {num_frames} OBJ paths, got {len(paths)}"
        assert len(sequence) == num_frames, \
            f"Expected {num_frames} sequence entries, got {len(sequence)}"
        
        for i, path in enumerate(paths):
            assert os.path.exists(path), f"Frame {i} OBJ not found: {path}"
            assert os.path.getsize(path) > 100, f"Frame {i} OBJ too small"
        
        print(f"  ✅ Generated {num_frames} walk OBJ files")
    finally:
        shutil.rmtree(tmp_dir)


# =============================================================================
# Runner
# =============================================================================
if __name__ == "__main__":
    tests = [
        test_pose_library_imported_by_smpl_manager,
        test_generate_walk_sequence_returns_correct_count,
        test_walk_sequence_frame_structure,
        test_walk_sequence_translation_progresses,
        test_smpl_manager_generates_obj_for_single_frame,
        test_smpl_manager_generates_walk_sequence_objs,
    ]
    
    print("\n🧪 Animation Pipeline Tests")
    print("=" * 50)
    passed = 0
    failed = 0
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
    print("✅ All animation tests passed!\n")
