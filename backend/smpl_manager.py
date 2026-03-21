import os
import torch
import numpy as np

# Monkey-patch para retrocompatibilidad con chumpy (requerido por smplx en numpy >= 1.24)
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

class SMPLManager:
    """
    Gestor de mallas SMPL. Usa la librería smplx para generar modelos humanos
    en 3D a partir de parámetros (pose, shape).
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

    def save_obj(self, filepath, betas=None, body_pose=None, global_orient=None, transl=None):
        """Genera y guarda la malla como archivo .obj"""
        vertices, faces = self.generate_mesh(betas, body_pose, global_orient, transl)
        mesh = trimesh.Trimesh(vertices, faces)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        
        mesh.export(filepath)
        return filepath

# Para pruebas aisladas
if __name__ == "__main__":
    manager = SMPLManager()
    output_path = "output/human_test.obj"
    try:
        manager.save_obj(output_path)
        print(f"Generated mesh saved to {output_path}")
    except Exception as e:
        print("Could not generate mesh because SMPL files are missing.")
