import os
import warnings
import torch
import numpy as np

# Monkey-patch for chumpy backward compatibility (required by smplx with numpy >= 1.24)
# Suppress FutureWarning noise from these assignments
with warnings.catch_warnings():
    warnings.simplefilter("ignore", FutureWarning)
    if not hasattr(np, 'bool'):
        np.bool = np.bool_
    if not hasattr(np, 'int'):
        np.int = np.int_
    if not hasattr(np, 'float'):
        np.float = np.float64
    if not hasattr(np, 'complex'):
        np.complex = np.complex128
    if not hasattr(np, 'object'):
        np.object = object
    if not hasattr(np, 'unicode'):
        np.unicode = str
    if not hasattr(np, 'str'):
        np.str = str

import smplx
import trimesh

from pose_library import generate_walk_sequence as _generate_walk_seq

class SMPLManager:
    """
    SMPL mesh manager. Uses the smplx library to generate 3D human models
    from pose and shape parameters.
    """
    def __init__(self, model_folder='models'):
        self.model_folder = model_folder
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = None

    def load_model(self, gender='neutral'):
        if self.model is None:
            # Requisito de smplx: la ruta debe ser al directorio que contiene la carpeta 'smpl'
            abs_model_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), self.model_folder))
            smpl_specific_dir = os.path.join(abs_model_dir, 'smpl')
            
            if not os.path.exists(smpl_specific_dir):
                raise RuntimeError(f"🚨 Missing SMPL models. You must create '{smpl_specific_dir}' and place the .pkl files there.")
            
            try:
                # smplx.create expects the parameter 'model_path' as the first positional argument
                self.model = smplx.create(model_path=abs_model_dir, 
                                          model_type='smpl',
                                          gender=gender, 
                                          ext='pkl',
                                          use_pca=False,
                                          batch_size=1)
                self.model.to(self.device)
                print(f"✅ SMPL model loaded successfully on {self.device}")
            except Exception as e:
                print(f"❌ Error loading SMPL model: {e}")
                print(f"⚠️ Make sure you have the SMPL .pkl files in the folder: {abs_model_dir}/smpl/")
                raise e

    def generate_mesh(self, betas=None, body_pose=None, global_orient=None, transl=None):
        """
        Genera vértices y caras de la malla SMPL dadas las posturas y forma.
        betas: (10,) shape parameters
        body_pose: (69,) pose parameters for body joints
        global_orient: (3,) global root orientation
        transl: (3,) global translation
        """
        self.load_model()
        
        # Convert inputs to torch tensors
        kwargs = {}
        if betas is not None:
            kwargs['betas'] = torch.tensor(betas, dtype=torch.float32).unsqueeze(0).to(self.device)
        if body_pose is not None:
            kwargs['body_pose'] = torch.tensor(body_pose, dtype=torch.float32).unsqueeze(0).to(self.device)
        if global_orient is not None:
            kwargs['global_orient'] = torch.tensor(global_orient, dtype=torch.float32).unsqueeze(0).to(self.device)
        if transl is not None:
            kwargs['transl'] = torch.tensor(transl, dtype=torch.float32).unsqueeze(0).to(self.device)

        output = self.model(**kwargs)
        vertices = output.vertices.detach().cpu().numpy().squeeze()
        faces = self.model.faces

        return vertices, faces

    def save_obj(self, filepath, betas=None, body_pose=None, global_orient=None, transl=None, for_sionna=True):
        """
        Generate and save mesh as .obj file.
        
        Args:
            for_sionna: If True, swap Y↔Z so model stands upright in Mitsuba Z-up scene.
                        If False, keep SMPL native Y-up (for Three.js which applies rotation).
        """
        vertices, faces = self.generate_mesh(betas, body_pose, global_orient, transl)
        
        if for_sionna:
            # Swap Y↔Z: SMPL Y-up → Mitsuba Z-up
            vertices_zup = vertices.copy()
            vertices_zup[:, 1] = vertices[:, 2]   # new Y = old Z (depth)
            vertices_zup[:, 2] = vertices[:, 1]   # new Z = old Y (height)
            mesh = trimesh.Trimesh(vertices_zup, faces)
        else:
            mesh = trimesh.Trimesh(vertices, faces)
        
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        mesh.export(filepath)
        return filepath

    def generate_walk_sequence(self, num_frames=16):
        """Generate a walking animation sequence using pose_library keyframes."""
        return _generate_walk_seq(num_frames)

    def save_walk_sequence_objs(self, output_dir, num_frames=16, betas=None):
        """
        Generate and save all walk animation frames as .obj files.
        """
        os.makedirs(output_dir, exist_ok=True)
        sequence = self.generate_walk_sequence(num_frames)
        
        paths = []
        for i, frame in enumerate(sequence):
            filepath = os.path.join(output_dir, f"frame_{i:04d}.obj")
            self.save_obj(
                filepath,
                betas=betas,
                body_pose=frame['body_pose'],
                global_orient=frame['global_orient'],
                transl=frame['transl'],
                for_sionna=False,  # Animation OBJs go to Three.js, not Sionna
            )
            paths.append(filepath)
        
        return paths, sequence


# For standalone tests
if __name__ == "__main__":
    manager = SMPLManager()
    output_path = "output/human_test.obj"
    try:
        manager.save_obj(output_path)
        print(f"Generated mesh saved to {output_path}")
        
        # Test walk sequence
        seq = manager.generate_walk_sequence(4)
        print(f"Walk sequence: {len(seq)} frames")
        for i, frame in enumerate(seq):
            print(f"  Frame {i}: Y={frame['transl'][1]:.2f}m")
    except Exception as e:
        print(f"Could not generate mesh: {e}")
