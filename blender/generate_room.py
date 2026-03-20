"""
MVP-Sionna-WiFi: Blender Room Generator
Run inside Blender: blender --background --python blender/generate_room.py

Generates a concrete room with ITU-standard materials following the
Single-Sheet Modeling approach (each wall is a single flat plane).
Creates two collections:
  - Collection_Visual_Render: pretty materials for visual inspection
  - Collection_Sionna_XML: clean meshes with ITU naming for export
"""

import bpy
import bmesh
import math
import os
import sys

# Add parent dir to path so we can import config
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'backend'))
from config import ROOM_WIDTH, ROOM_DEPTH, ROOM_HEIGHT, WALL_THICKNESS


# =============================================================================
# Configuration
# =============================================================================
ROOM_W = ROOM_WIDTH    # 2.0 m (X-axis)
ROOM_D = ROOM_DEPTH    # 3.5 m (Y-axis)
ROOM_H = ROOM_HEIGHT   # 2.0 m (Z-axis)
WALL_T = WALL_THICKNESS  # 0.12 m

OUTPUT_BLEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scenes', 'room_simple.blend')
OUTPUT_XML = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scenes', 'room_simple.xml')


def clear_scene():
    """Remove all existing objects from the scene."""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    # Remove orphan data
    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)
    for block in bpy.data.materials:
        if block.users == 0:
            bpy.data.materials.remove(block)


def create_collection(name):
    """Create a new collection and link it to the scene."""
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    return col


def create_itu_material(name="itu_concrete"):
    """Create a material slot with ITU-standard naming for Sionna export."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    # Simple gray for visual reference
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs['Base Color'].default_value = (0.5, 0.5, 0.5, 1.0)
        bsdf.inputs['Roughness'].default_value = 0.9
    return mat


def create_visual_material(name="Visual_Concrete", color=(0.6, 0.58, 0.55, 1.0)):
    """Create a visually appealing concrete material for rendering."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs['Base Color'].default_value = color
        bsdf.inputs['Roughness'].default_value = 0.85
        bsdf.inputs['Specular IOR Level'].default_value = 0.1
    return mat


def create_wall_plane(name, location, rotation, scale, collection, material):
    """
    Create a single-sheet wall (flat plane) following the Single-Sheet Modeling
    approach required by Sionna RT. Normals point inward.
    
    Args:
        name: Object name
        location: (x, y, z) center position  
        rotation: (rx, ry, rz) rotation in radians
        scale: (sx, sy, sz) scale factors
        collection: Blender collection to link to
        material: Material to assign
    """
    bpy.ops.mesh.primitive_plane_add(
        size=1.0,
        enter_editmode=False,
        location=location,
        rotation=rotation,
        scale=(1, 1, 1)
    )
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    
    # Assign material
    obj.data.materials.append(material)
    
    # Unlink from default collection and link to target
    for col in obj.users_collection:
        col.objects.unlink(obj)
    collection.objects.link(obj)
    
    # Clean mesh
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.001)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    
    return obj


def flip_normals(obj):
    """Flip normals to point inward (into the room)."""
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.flip_normals()
    bpy.ops.object.mode_set(mode='OBJECT')


def generate_room():
    """
    Generate the complete room with 4 walls + floor + ceiling.
    
    Room layout (top-down view, Y-axis going up):
    
        ┌─────────────┐   Y = ROOM_D (3.5m)
        │             │
        │     Room    │
        │             │
        └─────────────┘   Y = 0
        X=0          X=ROOM_W (2.0m)
    
    Each wall is a single flat plane at the center of the wall's thickness.
    """
    print("=" * 60)
    print("MVP-Sionna-WiFi: Generating Room")
    print(f"  Dimensions: {ROOM_W} x {ROOM_D} x {ROOM_H} m")
    print(f"  Wall thickness: {WALL_T} m")
    print("=" * 60)
    
    clear_scene()
    
    # Create collections
    col_visual = create_collection("Collection_Visual_Render")
    col_sionna = create_collection("Collection_Sionna_XML")
    
    # Create materials
    mat_itu_concrete = create_itu_material("itu_concrete")
    mat_itu_brick = create_itu_material("itu_brick")
    mat_visual_concrete = create_visual_material("Visual_Concrete")
    mat_visual_floor = create_visual_material("Visual_Floor", color=(0.45, 0.43, 0.4, 1.0))
    
    # Half dimensions for center positioning
    hw = ROOM_W / 2.0
    hd = ROOM_D / 2.0
    hh = ROOM_H / 2.0
    
    # =========================================================================
    # Sionna XML Collection — Single-sheet planes with ITU materials
    # =========================================================================
    
    # Front wall (Y=0 plane, facing +Y into room)
    create_wall_plane(
        name="Wall_Front_Sionna",
        location=(hw, 0, hh),
        rotation=(math.pi / 2, 0, 0),
        scale=(ROOM_W, ROOM_H, 1),
        collection=col_sionna,
        material=mat_itu_concrete
    )
    
    # Back wall (Y=ROOM_D plane, facing -Y into room)
    wall_back = create_wall_plane(
        name="Wall_Back_Sionna",
        location=(hw, ROOM_D, hh),
        rotation=(math.pi / 2, 0, 0),
        scale=(ROOM_W, ROOM_H, 1),
        collection=col_sionna,
        material=mat_itu_concrete
    )
    flip_normals(wall_back)
    
    # Left wall (X=0 plane, facing +X into room)
    create_wall_plane(
        name="Wall_Left_Sionna",
        location=(0, hd, hh),
        rotation=(math.pi / 2, 0, math.pi / 2),
        scale=(ROOM_D, ROOM_H, 1),
        collection=col_sionna,
        material=mat_itu_concrete
    )
    
    # Right wall (X=ROOM_W plane, facing -X into room)
    wall_right = create_wall_plane(
        name="Wall_Right_Sionna",
        location=(ROOM_W, hd, hh),
        rotation=(math.pi / 2, 0, math.pi / 2),
        scale=(ROOM_D, ROOM_H, 1),
        collection=col_sionna,
        material=mat_itu_concrete
    )
    flip_normals(wall_right)
    
    # Floor (Z=0 plane, facing +Z up into room)
    create_wall_plane(
        name="Floor_Sionna",
        location=(hw, hd, 0),
        rotation=(0, 0, 0),
        scale=(ROOM_W, ROOM_D, 1),
        collection=col_sionna,
        material=mat_itu_concrete
    )
    
    # Ceiling (Z=ROOM_H plane, facing -Z down into room)
    ceiling = create_wall_plane(
        name="Ceiling_Sionna",
        location=(hw, hd, ROOM_H),
        rotation=(0, 0, 0),
        scale=(ROOM_W, ROOM_D, 1),
        collection=col_sionna,
        material=mat_itu_concrete
    )
    flip_normals(ceiling)
    
    # =========================================================================
    # Visual Render Collection — Pretty materials
    # =========================================================================
    
    # Front wall visual
    create_wall_plane(
        name="Wall_Front_Visual",
        location=(hw, 0, hh),
        rotation=(math.pi / 2, 0, 0),
        scale=(ROOM_W, ROOM_H, 1),
        collection=col_visual,
        material=mat_visual_concrete
    )
    
    # Back wall visual
    create_wall_plane(
        name="Wall_Back_Visual",
        location=(hw, ROOM_D, hh),
        rotation=(math.pi / 2, 0, 0),
        scale=(ROOM_W, ROOM_H, 1),
        collection=col_visual,
        material=mat_visual_concrete
    )
    
    # Left wall visual
    create_wall_plane(
        name="Wall_Left_Visual",
        location=(0, hd, hh),
        rotation=(math.pi / 2, 0, math.pi / 2),
        scale=(ROOM_D, ROOM_H, 1),
        collection=col_visual,
        material=mat_visual_concrete
    )
    
    # Right wall visual
    create_wall_plane(
        name="Wall_Right_Visual",
        location=(ROOM_W, hd, hh),
        rotation=(math.pi / 2, 0, math.pi / 2),
        scale=(ROOM_D, ROOM_H, 1),
        collection=col_visual,
        material=mat_visual_concrete
    )
    
    # Floor visual
    create_wall_plane(
        name="Floor_Visual",
        location=(hw, hd, 0),
        rotation=(0, 0, 0),
        scale=(ROOM_W, ROOM_D, 1),
        collection=col_visual,
        material=mat_visual_floor
    )
    
    # Ceiling visual
    create_wall_plane(
        name="Ceiling_Visual",
        location=(hw, hd, ROOM_H),
        rotation=(0, 0, 0),
        scale=(ROOM_W, ROOM_D, 1),
        collection=col_visual,
        material=mat_visual_concrete
    )
    
    # =========================================================================
    # Save
    # =========================================================================
    os.makedirs(os.path.dirname(OUTPUT_BLEND), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(OUTPUT_BLEND))
    print(f"\n✅ Blender file saved: {OUTPUT_BLEND}")
    print(f"   Sionna collection: {len(col_sionna.objects)} objects")
    print(f"   Visual collection: {len(col_visual.objects)} objects")
    
    return col_sionna, col_visual


def export_to_xml():
    """
    Export the Sionna collection to Mitsuba XML format.
    Disables the Visual collection and exports only the Sionna meshes.
    
    Requires the mitsuba-blender addon to be installed.
    """
    print("\n" + "=" * 60)
    print("Exporting to Mitsuba XML...")
    print("=" * 60)
    
    # Disable visual collection for export
    visual_col = bpy.data.collections.get("Collection_Visual_Render")
    sionna_col = bpy.data.collections.get("Collection_Sionna_XML")
    
    if visual_col:
        visual_col.hide_render = True
        visual_col.hide_viewport = True
    
    if sionna_col:
        sionna_col.hide_render = False
        sionna_col.hide_viewport = False
    
    # Try to export using mitsuba-blender
    try:
        os.makedirs(os.path.dirname(OUTPUT_XML), exist_ok=True)
        bpy.ops.export_scene.mitsuba(filepath=os.path.abspath(OUTPUT_XML))
        print(f"✅ Mitsuba XML exported: {OUTPUT_XML}")
    except Exception as e:
        print(f"⚠️  Mitsuba export failed: {e}")
        print("   Make sure the mitsuba-blender addon is installed.")
        print("   You can install it from: https://github.com/mitsuba-renderer/mitsuba-blender")
        print("   Proceeding without XML export — you can export manually from Blender.")


# =============================================================================
# Main
# =============================================================================
if __name__ == "__main__":
    generate_room()
    export_to_xml()
    print("\n🏠 Room generation complete!")
