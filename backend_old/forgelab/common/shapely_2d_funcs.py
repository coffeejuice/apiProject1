import logging
import warnings
import math
import os
import struct

import numpy as np
import random
from scipy import optimize
from scipy.spatial.transform import Rotation
from scipy.linalg import norm
from shapely.affinity import translate, rotate, scale
from shapely.geometry import LineString, Polygon, Point, GeometryCollection, box
from shapely.geometry.multipolygon import MultiPolygon
from shapely.ops import split
import trimesh
from trimesh import Trimesh, Geometry, transformations
from trimesh.path import Path3D
import tripy
from io import BytesIO
from matplotlib.patches import FancyArrowPatch

from forgelab.common.read_deform_keyfile import gram_schmidt_1

# create logger
LOGGER = logging.getLogger(__name__)


def polygon_to_equivalent_diameter(_polygon) -> float:
    """Receives a list of point coordinates and length. Returns surface area."""
    assert isinstance(_polygon, Polygon)
    if _polygon.is_empty:
        return 0.0
    return math.sqrt(4 * _polygon.area / math.pi)


def get_cross_section_area(_polygon: Polygon) -> float:
    """Receives a list of point coordinates and length. Returns surface area."""
    assert isinstance(_polygon, Polygon)
    if _polygon.is_empty:
        return 0.0
    return _polygon.area


def get_surface_area(_polygon: Polygon, _length: float) -> float:
    """Receives a list of point coordinates and length. Returns surface area."""
    assert isinstance(_polygon, Polygon)
    if _polygon.is_empty:
        return 0.0
    face_area = _polygon.area
    curved_surface_area = _length * _polygon.length
    return 2 * face_area + curved_surface_area


def get_volume(_polygon: Polygon, _length: float) -> float:
    """Receives a list of point coordinates and length. Returns volume."""
    assert isinstance(_polygon, Polygon)
    if _polygon.is_empty:
        return 0.0
    return _polygon.area * _length


# def rotate_and_center_mesh(mesh_stl: mesh.Mesh, rotations: list[tuple[str, np.float64]]) -> mesh.Mesh:
    # try:
        # Rotate mesh
    #     axes = {'x': [0.5, 0.0, 0.0],
    #             'y': [0.0, 0.5, 0.0],
    #             'z': [0.0, 0.0, 0.5]}
    #     for (axis, angle) in rotations:
    #         mesh_stl.rotate(axis=axes[axis], theta=math.radians(angle))
    #     # Get properties
    #     volume, center_of_gravity, inertia = mesh_stl.get_mass_properties()
    #     # Translate center of gravity to (0,0,0)
    #     mesh_stl.translate(-1 * center_of_gravity)
    #     return mesh_stl
    # except Exception as _err:
    #     LOGGER.error(f"{type(_err).__name__}: {_err}")
    #     raise RuntimeError("FAILED to rotate or intersect STL")


def rotate_trimesh_object(trimesh_obj: Trimesh, rotations: list[tuple[str, np.float64 | float]], eo: int = 0) -> Trimesh:
    try:
        _t = trimesh_obj.copy()
        # Rotate mesh
        axes = {'x': [1, 0, 0],
                'y': [0, 1, 0],
                'z': [0, 0, 1]}
        for i, (axis_name, angle) in enumerate(rotations):
            # plot_trimesh_object(_t, name=f'mesh_ROTATE_TRIMESH_OBJECT_BEFORE_#{i}_{axis_name}_{angle:0.2f}', eo=eo)
            if angle == 0.0:
                continue
            rot_matrix = transformations.rotation_matrix(angle=math.radians(angle), direction=axes[axis_name], point=[0, 0, 0])
            _t.apply_transform(rot_matrix)
            # plot_trimesh_object(_t, name=f'mesh_ROTATE_TRIMESH_OBJECT_AFTER_#{i}_{axis_name}_{angle:0.2f}', eo=eo)
        _t: Trimesh
        return _t
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise RuntimeError("FAILED to rotate mesh (using trimesh methods)")


# def polygon_to_3d_stl(polygon: Polygon, length: np.float64) -> mesh.Mesh:
#     try:
#         _contour_2d_list: list = polygon_to_list(polygon)
#         _tessellated_two_faces: list = _tessellate_polygon(_contour_2d_list, length)
#         _tessellated_tube: list = _extrude_and_tessellate(_contour_2d_list, length)
#         _stl: mesh.Mesh = _combine_and_convert_to_stl(_tessellated_two_faces, _tessellated_tube)
        # _show_stl(_stl)
        # _save_trimesh_object_to_stl_file(_stl)
    #     return _stl
    # except Exception as _err:
    #     LOGGER.error(f"{type(_err).__name__}: {_err}")
    #     raise


def polygon_to_3d_trimesh_object(polygon: Polygon, length: float | np.float64, eo: int = 0) -> Trimesh:
    try:
        vertices, faces = trimesh.creation.triangulate_polygon(polygon=polygon, force_vertices=True)
        mesh_obj = trimesh.creation.extrude_triangulation(vertices=vertices, faces=faces, height=length)
        mesh_obj.apply_translation([0.0, 0.0, -0.5 * length])
        # plot_trimesh_object(mesh_obj)
        rotated_mesh_obj = rotate_trimesh_object(trimesh_obj=mesh_obj, rotations=[('x', 90.0), ('z', 90.0)], eo=eo)
        rotated_mesh_obj: Trimesh
        # plot_trimesh_object(rotated_mesh_obj)
        return rotated_mesh_obj
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def trimesh_object_to_stl_file(trimesh_obj: Geometry):
    try:
        _dir = os.path.normpath('C://Users//admin//Downloads')
        _file_path = os.path.join(_dir, f'combined_{str(random.randint(0, 99999999))}.stl')
        with open(_file_path, 'w+b') as f:
            trimesh_obj: Trimesh
            trimesh_obj.export(file_obj=f, file_type='stl')
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def import_3d_stl_intersect_by_xy_plane_return_2d_polygon(die_abs_path: str, eo: int = 0) -> Polygon:
    try:
        assert os.path.isfile(die_abs_path), f"Die-file not found: {die_abs_path}"
        die_abs_path: str
        _mesh: Geometry = trimesh.load_mesh(file_obj=die_abs_path, file_type='stl')
        _mesh: Trimesh
        return intersect_3d_mesh_by_2d_plane(mesh_stl=_mesh,  plane_normal=[1, 0, 0], output_polygon_y_axis=[0, 1, 0], eo=eo)
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise RuntimeError("Intersection of STL by plane failed.")


def find_rotation_matrix(initial_vectors: list | np.ndarray, target_vectors: list | np.ndarray):
    """
    Find the rotation matrix that aligns the initial coordinate system to the target coordinate system.

    Parameters:
    initial_vectors (list | np.ndarray): Vectors defining the initial coordinate system.
    target_vectors (list | np.ndarray): Vectors defining the target coordinate system.

    Returns:
    np.array: The rotation matrix.
    """
    try:
        # Normalize the input vectors to ensure they are unit vectors.
        initial_vectors = initial_vectors / np.linalg.norm(initial_vectors, axis=0, keepdims=True)
        target_vectors = target_vectors / np.linalg.norm(target_vectors, axis=0, keepdims=True)

        # Calculate the rotation matrix. R = Target * Initial^-1
        return np.dot(target_vectors, np.linalg.inv(initial_vectors))
    except np.linalg.LinAlgError as _err:  # Handle the case where the input vectors are linearly dependent.
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise ValueError("The input vectors are linearly dependent.")
    except ValueError as _err:  # Handle the case where the input vectors are not of the same shape.
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise ValueError("The input vectors must have the same shape.")
    except Exception as _err:
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise


def basis_to_basis_transformation_as_euler_angles_zyx(initial_basis, target_basis, is_degrees: bool = True) -> np.ndarray:
    """
    Convert a rotation matrix to Euler angles (yaw, pitch, roll).

    Parameters:
    rotation_matrix (np.array): The rotation matrix.

    Returns:
    tuple: Euler angles in radians or degrees.
    """
    try:
        # -------------------------- ROTATION MATRIX ----------------------------------------
        # Normalize the input vectors to ensure they are unit vectors.

        def _get_relative_rotation(_initial_basis, _target_basis):
            initial_vectors_norm = _initial_basis / np.linalg.norm(_initial_basis, axis=0, keepdims=True)
            target_vectors_norm = _target_basis / np.linalg.norm(_target_basis, axis=0, keepdims=True)
            #
            initial_rotation = Rotation.from_matrix(initial_vectors_norm)
            target_rotation = Rotation.from_matrix(target_vectors_norm)
            #
            return target_rotation.inv() * initial_rotation

        is_gimbal_lock = False
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")  # Cause all warnings to always be triggered.
            zyx_angles = _get_relative_rotation(initial_basis, target_basis).as_euler(seq='zyx', degrees=is_degrees)
            # Verify some things
            if len(w) == 1:
                if issubclass(w[-1].category, DeprecationWarning):
                    if "Gimbal lock detected" in str(w[-1].message):
                        is_gimbal_lock = True

        if is_gimbal_lock:
            possible_angles = np.array([0.001, -0.001])  # Define possible rotation angles in degrees
            angle_x, angle_y, angle_z = np.random.choice(possible_angles, size=3)  # Randomly select a rotation angle for each axis

            # Create rotation objects for each axis
            rot_x = Rotation.from_euler(seq='x', angles=angle_x, degrees=True)
            rot_y = Rotation.from_euler(seq='y', angles=angle_y, degrees=True)
            rot_z = Rotation.from_euler(seq='z', angles=angle_z, degrees=True)
            combined_rotation = rot_z * rot_y * rot_x  # Combine the rotations: first X, then Y, then Z

            # Apply the combined rotation to the basis
            randomized_target_basis = combined_rotation.apply(target_basis.copy)
            zyx_angles = _get_relative_rotation(initial_basis, randomized_target_basis).as_euler(seq='zyx', degrees=is_degrees)

        return zyx_angles
    except np.linalg.LinAlgError as _err:  # Handle the case where the input vectors are linearly dependent.
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise ValueError("The input vectors are linearly dependent.")
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def trimesh_basis_to_basis_transformation_matrix(from_basis: np.ndarray, to_basis: np.ndarray) -> np.ndarray:
    """
    Returns a transformation matrix in 'trimesh' format for rotations between basis.

    Parameters:
    from_basis (np.array): 3x3 numpy array of three unit vectors (rows), representing X, Y, Z axes
    to_basis (np.array): 3x3 numpy array of three unit vectors (rows), representing X, Y, Z axes

    Returns:
    tuple: Euler angles in radians.
    """
    try:
        # Normalize the input vectors to ensure they are unit vectors.
        initial_vectors_norm = from_basis / np.linalg.norm(from_basis, axis=0, keepdims=True)
        target_vectors_norm = to_basis / np.linalg.norm(to_basis, axis=0, keepdims=True)

        initial_rotation = Rotation.from_matrix(initial_vectors_norm)
        target_rotation = Rotation.from_matrix(target_vectors_norm)
        relative_rotation = target_rotation.inv() * initial_rotation

        scipy_quaternions: np.ndarray = relative_rotation.as_quat(scalar_first=True)

        trimesh_transformation_matrix: np.ndarray = transformations.quaternion_matrix(scipy_quaternions)

        return trimesh_transformation_matrix
    except np.linalg.LinAlgError as _err:  # Handle the case where the input vectors are linearly dependent.
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise ValueError("The input vectors are linearly dependent.")
    except Exception as _err:
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise


def rotate_basis(input_cs: np.ndarray, list_of_rotations_xyz: list[tuple], randomize_deviation: float = 0.0) -> np.ndarray:
    output_cs = input_cs.copy()
    for (axis_name, rotation_angle) in list_of_rotations_xyz:

        if randomize_deviation != 0.0:
            deviations = [randomize_deviation, -randomize_deviation]
            rotation_angle += random.choice(deviations)

        rotation_angle = rotation_angle % 360.0
        if rotation_angle == 0.0:
            continue

        rotation = Rotation.from_euler(seq=axis_name, angles=rotation_angle, degrees=True)
        output_cs = rotation.apply(output_cs)

        # output_cs = apply_euler_angles_to_coordinate_system(output_cs, r_xyz).copy()

    return output_cs


def apply_euler_angles_to_coordinate_system(initial_system: np.ndarray,
                                            euler_angles_degrees: tuple[float | int]
                                            ) -> np.ndarray:
    """
    Apply Euler angles (in degrees) to an initial coordinate system to get the resulting system.

    Parameters:
    initial_system (np.ndarray): A 2-D array where each column is a vector of the initial local coordinate system.
    euler_angles_degrees (tuple): A tuple of Euler angles (yaw, pitch, roll) in degrees.

    Returns:
    np.array: The resulting local coordinate system as a 2-D array where each column is a vector.
    """
    try:
        rotation = Rotation.from_euler(seq='xyz', angles=euler_angles_degrees, degrees=True)
        return rotation.apply(initial_system)
    except Exception as _err:
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise


def correct_orientation_from_nearly_horizontal_to_ideal_horizontal(cs1):
    try:
        # Global coordinate system unit vectors
        i_hat = np.array([1, 0, 0])
        # j_hat = np.array([0, 1, 0])
        # k_hat = np.array([0, 0, 1])

        # Extract the x-axis and y-axis from cs1
        x1 = cs1[:, 0]
        y1 = cs1[:, 1]

        # Step 1: Project x1 onto the global x-axis and normalize
        x2 = np.dot(x1, i_hat) * i_hat
        x2 = x2 / norm(x2)

        # Step 2: Project y1 onto the global YZ-plane and normalize
        # Remove the x-component (project onto YZ-plane)
        y2 = y1 - np.dot(y1, i_hat) * i_hat
        y2 = y2 / norm(y2)

        # Step 3: Compute z-axis using the right-hand rule
        z2 = np.cross(x2, y2)
        z2 = z2 / norm(z2)  # Normalize, although it should already be a unit vector

        # Form the new coordinate system matrix
        return np.column_stack((x2, y2, z2))
    except Exception as _err:
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise


def randomize_vector(input_vector: list):
    factor = 0
    output_vector = []
    for item in input_vector:
        output_vector.append(item - factor * (1 - 2 * random.random()))
    return output_vector


def intersect_3d_mesh_by_2d_plane(mesh_stl: Geometry, plane_origin: list | None = None, plane_normal: list | None = None, output_polygon_y_axis: list | None = None, eo: int = 0) -> Polygon:
    try:
        mesh_stl: Trimesh

        if plane_origin is None:
            plane_origin = [0, 0, 0]
        if plane_normal is None:
            plane_normal = [1, 0, 0]
        if output_polygon_y_axis is None:
            output_polygon_y_axis = [0, 1, 0]

        if plane_normal != [1, 0, 0] and output_polygon_y_axis != [0, 1, 0]:
            section_x, section_y = gram_schmidt_1(np.array((plane_normal, output_polygon_y_axis))).tolist()
            section_z = np.cross(section_x, section_y)
            section_basis = np.vstack((section_x, section_y, section_z))

            section_basis_normalized = section_basis / np.linalg.norm(section_basis, axis=0, keepdims=True)
            section_basis_as_quaternion = Rotation.from_matrix(section_basis_normalized).as_quat()
            section_basis_as_rotation_matrix = transformations.quaternion_matrix(section_basis_as_quaternion)

            mesh_in_global_basis: Trimesh = mesh_stl.copy()
            mesh_in_global_basis.apply_transform(section_basis_as_rotation_matrix)
        else:
            mesh_in_global_basis = mesh_stl

        # plot_trimesh_object(mesh_in_global_basis, name=f"mesh_INTERSECT_IN_GLOBAL_BASIS_NORM[{','.join([f'{_axis:.2f}' for _axis in plane_normal])}]_POL_Y[{','.join([f'{_axis:.2f}' for _axis in output_polygon_y_axis])}]", eo=eo)

        global_normal = [1, 0, 0]
        intersection_by_yz_plane: Path3D = mesh_in_global_basis.section(plane_origin=plane_origin, plane_normal=global_normal)
        slice_2d, _ = intersection_by_yz_plane.to_planar(normal=global_normal)
        _yx = np.transpose(np.array(np.sum(slice_2d.polygons_full).boundary.xy))
        _xy = _yx[:, [1, 0]]
        _polygon = Polygon(_xy)

        # plot_polygon(_polygon, 'polygon_INTERSECT')

        return _polygon
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise RuntimeError("FAILED intersection of Trimesh Obj by plane")


# def convert_stl_numpy_object_to_memory_buffer_object(_stl: mesh.Mesh):
#     try:
#         with BytesIO() as myio:
#             _stl.save('temporary.stl', fh=myio, mode=Mode.BINARY, update_normals=True)
#             myio.seek(0)
#             _stl_binary = myio.read()
#         return _stl_binary
#     except Exception as _err:
#         LOGGER.error(f"{type(_err).__name__}: {_err}")
#         raise


def convert_trimesh_object_to_memory_buffer_object(mesh_obj: Geometry) -> bytes:
    try:
        with BytesIO() as myio:
            mesh_obj: Trimesh
            mesh_obj.export(file_obj=myio, file_type='stl')
            myio.seek(0)
            _stl_binary = myio.read()
        return _stl_binary
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


# def _convert_memory_buffer_object_to_numpy_stl_object(stl_bytes: bytes) -> mesh.Mesh:
#     try:
#         with BytesIO() as myio:
#             myio.write(stl_bytes)
#             myio.seek(0)
#             _mesh = mesh.Mesh.from_file(filename='temporary.stl', fh=myio)
#         return _mesh
#     except Exception as _err:
#         LOGGER.error(f"{type(_err).__name__}: {_err}")
#         raise


def convert_stl_binary_object_to_trimesh_object(stl_bytes: bytes) -> Trimesh:
    try:
        with BytesIO() as myio:
            myio.write(stl_bytes)
            myio.seek(0)
            _trimesh_mesh: Geometry = trimesh.load_mesh(file_obj=myio, file_type='stl')
            _trimesh_mesh: Trimesh
        return _trimesh_mesh
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def _show_stl(meshes):
    # Optionally render the rotated cube faces
    from matplotlib import pyplot
    from mpl_toolkits import mplot3d

    # Create a new plot
    figure = pyplot.figure()
    axes = figure.add_subplot(projection='3d')

    # Render the cube faces
    # for m in meshes:
    axes.add_collection3d(mplot3d.art3d.Poly3DCollection(meshes.vectors))

    # Auto-scale to the mesh size
    _scale = meshes.points.flatten()
    axes.auto_scale_xyz(_scale, _scale, _scale)

    # Show the plot to the screen
    pyplot.show()
    LOGGER.info('done')
    pass


def _tessellate_polygon(contour_2d: list, _l: np.float64) -> list:
    # Convert Polygon points to list
    try:
        # Tessellate the polygon using tripy.earclip method
        tessellated_2d = tripy.earclip(contour_2d)

        tessellated_3d = []
        for _t in tessellated_2d:
            new_t_first_tail = [
                [0.0, _t[0][0], _t[0][1]],
                [0.0, _t[1][0], _t[1][1]],
                [0.0, _t[2][0], _t[2][1]]
            ]
            new_t_second_tail = [
                [_l, _t[0][0], _t[0][1]],
                [_l, _t[2][0], _t[2][1]],
                [_l, _t[1][0], _t[1][1]]
            ]
            tessellated_3d.append(new_t_first_tail)
            tessellated_3d.append(new_t_second_tail)

        return tessellated_3d
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def _tessellate_polygon_vertices_and_faces(contour_2d: list, _l: np.float64) -> list:
    # Convert Polygon points to list
    try:
        # Tessellate the polygon using tripy.earclip method
        tessellated_2d = tripy.earclip(contour_2d)

        tessellated_3d = []
        for _t in tessellated_2d:
            new_t_first_tail = [
                [0.0, _t[0][0], _t[0][1]],
                [0.0, _t[1][0], _t[1][1]],
                [0.0, _t[2][0], _t[2][1]]
            ]
            new_t_second_tail = [
                [_l, _t[0][0], _t[0][1]],
                [_l, _t[2][0], _t[2][1]],
                [_l, _t[1][0], _t[1][1]]
            ]
            tessellated_3d.append(new_t_first_tail)
            tessellated_3d.append(new_t_second_tail)

        return tessellated_3d
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


# def _combine_and_convert_to_stl(_t1: list, _t2: list) -> mesh.Mesh:
#     try:
#         total_tessellated = []
#         total_tessellated.extend(_t1)
#         total_tessellated.extend(_t2)
#
#         triangles_count = len(total_tessellated)
#         data = np.zeros(triangles_count, dtype=mesh.Mesh.dtype)
#
#         for i, _t in enumerate(total_tessellated):
#             data['vectors'][i] = np.array(_t)
#
#         # Create the mesh (STL) object
#         _stl = mesh.Mesh(data)
#
#         return _stl
#     except Exception as _err:
#         LOGGER.error(f"{type(_err).__name__}: {_err}")
#         raise

def _extrude_and_tessellate(contour_2d: list, _l: np.float64) -> list:
    # Converting Polygon points to numpy array
    try:
        _p1 = [*contour_2d, contour_2d[-1]]
        _p2 = [contour_2d[0], *contour_2d]

        tessellation = []
        for _c1, _c2 in zip(_p1, _p2):
            _t1 = [
                [0.0, _c1[0], _c1[1]],
                [_l, _c1[0], _c1[1]],
                [0.0, _c2[0], _c2[1]]
            ]
            _t2 = [
                [0.0, _c2[0], _c2[1]],
                [_l, _c1[0], _c1[1]],
                [_l, _c2[0], _c2[1]]
            ]
            tessellation.append(_t1)
            tessellation.append(_t2)

        return tessellation
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def plot_polygon(_input_p, name: str | None = None, eo: int = 0):
    import datetime
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
    from matplotlib.collections import PatchCollection

    try:
        if name is None:
            name = "polygon"
        name: str

        # List of colors. The length must match the length of the polygons list.
        colors = ['blue', 'red', 'green']  # Add more colors as needed...

        # Create a figure and axes.
        fig, ax = plt.subplots()

        if isinstance(_input_p, Polygon):
            _p_list = [_input_p]
            # LOGGER.info(f"Prolongation: object type is Polygon.")
        elif isinstance(_input_p, MultiPolygon):
            _p_list = list(_input_p.geoms)
            # LOGGER.info(f"Prolongation: object type is {type(_p_list)} and has {len(_p_list)} items.")
        else:
            _p_list = _input_p
            # LOGGER.info(f"Prolongation: object type is NOT Polygon or MultiPolygon,"
            #             "but {type(_p_list)} and has {len(_p_list)} items.")

        _p_list: list[Polygon]

        # Create an empty list to store the Polygon objects.
        polygon_patches = []
        polygon_bounds = []

        for _p in _p_list:

            # # Let's say we have a list of (x, y) tuples representing the vertices of the polygon.
            vertices = list(_p.exterior.coords)
            #
            # # Create a Polygon object from the vertices. The asterisk (*) unpacks the list into arguments.
            polygon = patches.Polygon(vertices, closed=True)
            polygon_patches.append(polygon)
            _b = _p.bounds
            if polygon_bounds:
                polygon_bounds[0] = min(polygon_bounds[0], _b[0])
                polygon_bounds[1] = min(polygon_bounds[1], _b[1])
                polygon_bounds[2] = max(polygon_bounds[2], _b[2])
                polygon_bounds[3] = max(polygon_bounds[3], _b[3])
            else:
                polygon_bounds = list(_b).copy()

        # Create a single-item list of the polygon for use in the PatchCollection.
        # polygons = [polygon]

        # Create a PatchCollection and specify the color.
        p = PatchCollection(polygon_patches, edgecolor='black')

        # Set the facecolor of the patches.
        p.set_facecolor(colors)

        # Add the PatchCollection to the axes.
        ax.add_collection(p)

        # Set the limits of the plot.
        polygon_bounds = np.multiply(np.array(polygon_bounds), 1.1).tolist()
        ax.set_xlim(polygon_bounds[0], polygon_bounds[2])
        ax.set_ylim(polygon_bounds[1], polygon_bounds[3])

        ax.set_aspect('equal')

        # Show the plot.
        # plt.show()

        # Create a timestamp string
        now = datetime.datetime.now()
        micro_sec = now.microsecond

        # Create filename
        filename = f"C://Users//alext//Downloads//forgelab_pictures//{eo}_{now.strftime('%H%M%S')}{micro_sec:04d}_{name}.png"

        # Save the figure
        plt.savefig(filename)
        # figure.max_open_warning
        plt.close()
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


class Arrow3D(FancyArrowPatch):
    def __init__(self, xs, ys, zs, *args, **kwargs):
        super().__init__((0,0), (0,0), *args, **kwargs)
        self._verts3d = xs, ys, zs

    def do_3d_projection(self, renderer=None):
        try:
            from mpl_toolkits.mplot3d import proj3d
            xs3d, ys3d, zs3d = self._verts3d
            xs, ys, zs = proj3d.proj_transform(xs3d, ys3d, zs3d, self.axes.M)
            self.set_positions((xs[0], ys[0]), (xs[1], ys[1]))

            return np.min(zs)
        except Exception as _err:
            LOGGER.error(f"{type(_err).__name__}: {_err}")
            raise

    # def draw(self, renderer):
    #     try:
    #         from mpl_toolkits.mplot3d import proj3d
    #         xs3d, ys3d, zs3d = self._verts3d
    #         xs, ys, zs = proj3d.proj_transform(xs3d, ys3d, zs3d, renderer.M)
    #         self.set_positions((xs[0], ys[0]), (xs[1], ys[1]))
    #         FancyArrowPatch.draw(self, renderer)
    #     except Exception as _err:
    #         LOGGER.error(f"{type(_err).__name__}: {_err}")
    #         raise


def cuboid_data(center, size):
    try:
        # suppose axis direction: x: to left; y: to inside; z: to upper
        # get the (left, outside, bottom) point
        o = [a - b / 2 for a, b in zip(center, size)]
        # get the length, width, and height
        l, w, h = size
        x = np.array([[o[0], o[0] + l, o[0] + l, o[0], o[0]],  # x coordinate of points in bottom surface
             [o[0], o[0] + l, o[0] + l, o[0], o[0]],  # x coordinate of points in upper surface
             [o[0], o[0] + l, o[0] + l, o[0], o[0]],  # x coordinate of points in outside surface
             [o[0], o[0] + l, o[0] + l, o[0], o[0]]])  # x coordinate of points in inside surface
        y = np.array([[o[1], o[1], o[1] + w, o[1] + w, o[1]],  # y coordinate of points in bottom surface
             [o[1], o[1], o[1] + w, o[1] + w, o[1]],  # y coordinate of points in upper surface
             [o[1], o[1], o[1], o[1], o[1]],          # y coordinate of points in outside surface
             [o[1] + w, o[1] + w, o[1] + w, o[1] + w, o[1] + w]])    # y coordinate of points in inside surface
        z = np.array([[o[2], o[2], o[2], o[2], o[2]],                        # z coordinate of points in bottom surface
             [o[2] + h, o[2] + h, o[2] + h, o[2] + h, o[2] + h],    # z coordinate of points in upper surface
             [o[2], o[2], o[2] + h, o[2] + h, o[2]],                # z coordinate of points in outside surface
             [o[2], o[2], o[2] + h, o[2] + h, o[2]]])                # z coordinate of points in inside surface
        return x, y, z
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def plot_trimesh_object(trimesh_obj: Trimesh, name: str | None = None, eo: int = 0):
    import datetime
    import matplotlib as mpl

    mpl.use('Agg')

    import matplotlib.pyplot as plt

    if name is None:
        name = "mesh"
    name: str

    try:
        assert isinstance(trimesh_obj, (Geometry, Trimesh))

        _bounds = trimesh_obj.bounds
        lim = np.multiply(1.2, _bounds[1, :]).tolist()

        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')

        # Here we create the arrows:
        arrow_prop_dict = dict(mutation_scale=20, arrowstyle='-|>', shrinkA=0, shrinkB=0)

        a = Arrow3D([0, lim[0]], [0, 0], [0, 0], **arrow_prop_dict, color='r')
        ax.add_artist(a)
        a = Arrow3D([0, 0], [0, lim[1]], [0, 0], **arrow_prop_dict, color='y')
        ax.add_artist(a)
        a = Arrow3D([0, 0], [0, 0], [0, lim[2]], **arrow_prop_dict, color='g')
        ax.add_artist(a)

        # Give them a name:
        ax.text(x=0.0, y=0.0, z=-0.1, s=r'$0$')
        ax.text(x=lim[0], y=0, z=0, s=r'$x$')
        ax.text(x=0, y=lim[1], z=0, s=r'$y$')
        ax.text(x=0, y=0, z=lim[2], s=r'$z$')

        ax.plot_trisurf(trimesh_obj.vertices[:, 0],
                        trimesh_obj.vertices[:, 1],
                        triangles=trimesh_obj.faces,
                        Z=trimesh_obj.vertices[:, 2])
        ax.set_xlabel('X')
        ax.set_ylabel('Y')
        ax.set_zlabel('Z')

        ax.set_aspect('equal')

        # Create a timestamp string
        now = datetime.datetime.now()
        micro_sec = now.microsecond

        # Create filename
        filename = f"C://Users//alext//Downloads//forgelab_pictures//{eo}_{now.strftime('%H%M%S')}{micro_sec:04d}_{name}.png"

        # Save the figure
        plt.savefig(filename)
        # figure.max_open_warning
        plt.close()
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def create_dies(_distance: float, _polygon: Polygon) -> (LineString, LineString):
    """Receives open die height between dies and a polygon as deformed object. Returns two lines."""
    try:
        # Find the width of the polygon
        _width = _polygon.bounds[2] - _polygon.bounds[0]

        # Create lines
        _line_top = LineString([(-_width, _distance / 2), (_width, _distance / 2)])
        _line_bottom = LineString([(-_width, -_distance / 2), (_width, -_distance / 2)])

        for _line in [_line_bottom, _line_top]:
            assert isinstance(_line, LineString), "Die creation is failed. Object must be a LineString type."
            assert not _line.is_empty, "Die creation is failed. Line is empty."

        return _line_top, _line_bottom
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def initial_width_of_contact(_polygon: Polygon, _initial_height: float, _final_height: float) -> float:
    """Receives a Polygon and two lines. Return average of lengths of two intersections."""
    try:
        _starting_proportion = 0.2
        _starting_height = _initial_height - _starting_proportion * (_initial_height - _final_height)
        _die_top, _die_bottom = create_dies(_starting_height, _polygon)
        return 0.5 * (_die_top.intersection(_polygon).length + _die_bottom.intersection(_polygon).length)
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def is_intersection(moved_polygon: Polygon, reference_polygon: Polygon) -> bool:
    """
    Local function to calculate intersection area between two polygons.
    Return True if they intersect within intersection error, otherwise return False.
    """

    # Relative and absolute error of Intersection area
    relative_area_error = 5e-7
    absolute_area_error = 0.1  # mm^2

    try:
        if moved_polygon.intersects(reference_polygon):
            absolute_intersection_area = moved_polygon.intersection(reference_polygon).area
            if absolute_intersection_area >= absolute_area_error:
                return True
            relative_intersection_area = absolute_intersection_area / reference_polygon.area
            if relative_intersection_area >= relative_area_error:
                return True
        return False
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise

def position_polygon_till_contact(moved_polygon: Polygon, reference_polygon: Polygon, direction: str) -> Polygon:
    """Return moved_polygon from the previous iteration just before intersection error met requirements"""

    # Initial increment value for translation along Y-axis and X-axis
    _dy = 5.0

    try:
        # Convert direction string to coefficient
        if direction == 'up':
            _dir_coef = 1
        elif direction == 'down':
            _dir_coef = -1
        else:
            raise ValueError("Direction must be either 'up' or 'down'.")

        while _dy > 1e-2:
            # Recursively translate moved_polygon along Y-axis by _dy increment value per iteration
            # until intersection error meet requirements
            while True:
                _mp = translate(moved_polygon, yoff=(_dir_coef * _dy))
                if is_intersection(_mp, reference_polygon):
                    break
                else:
                    moved_polygon = _mp
            _dy *= 0.1
        return moved_polygon
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def gap_between_dies(p0: Polygon, dies_polygons: list[Polygon]) -> (float, list[Polygon]):
    """
    Find initial gap between dies when dies initially clamp the billet.
    Returns gap height and translated polygons
    """
    try:
        pt: Polygon = dies_polygons[0]
        pb: Polygon = dies_polygons[1]

        # Bounds of p0 polygon
        p0_bounds = p0.bounds

        # Initial height and width of the p0 polygon
        _initial_height = p0_bounds[3] - p0_bounds[1]
        _initial_width = p0_bounds[2] - p0_bounds[0]

        # Move pt along +Y-axis above p0
        pt = translate(pt, yoff=p0_bounds[3] - pt.bounds[1])

        # Move pb along +Y-axis below p0
        pb = translate(pb, yoff=p0_bounds[1] - pb.bounds[3])

        # Translate Top Polygon down along Y-axis until intersection error meet requirements
        pt = position_polygon_till_contact(pt, p0, direction='down')

        # Translate Bottom Polygon up along Y-axis until intersection error meet requirements
        pb = position_polygon_till_contact(pb, p0, direction='up')

        # Minimum gap between pt and pb polygons along Y-axis
        _min_gap = pt.bounds[1] - pb.bounds[3]

        # Return minimum gap and a list of polygons [pt, pb]
        return _min_gap, [pt, pb]
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def shift_polygon_and_split_by_line_return_one_piece(_p: Polygon, _l: LineString, is_return_left: bool):
    # Split the polygon into two parts using difference operation
    try:
        _s = split(_p, _l)
        if len(_s.geoms) < 2:
            return None
        _x = sorted(list(_s.geoms), key=lambda _li: _li.centroid.x, reverse=is_return_left)
        return _x[0]
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def intersection_with_dies(_p: Polygon,
                           _top_l: LineString | Polygon,
                           _bottom_l: LineString | Polygon
                           ) -> (tuple[Point], tuple[Point]):
    """Returns intersection points between Polygon exterior and two lines"""
    try:
        _intersection_points_list = []
        for _i, _l in enumerate((_top_l, _bottom_l,)):
            if not isinstance(_l, (LineString, Polygon)):
                if _i == 0:
                    die_side = 'Top'
                elif _i == 1:
                    die_side = 'Bottom'
                else:
                    die_side = 'Side'
                raise TypeError(f"{die_side} die has '{str(type(_l))} type, "
                                f"but it must be either a LineString or a Polygon type.")

            if isinstance(_l, Polygon):
                _points = _l.exterior.intersection(_p.exterior)
            else:
                _points = _l.intersection(_p.exterior)
            assert not _l.is_empty
            sorted_points = sorted(_points.geoms, key=lambda _point: _point.x, reverse=False)
            assert len(sorted_points) >= 2, "There must be at least two intersections of a die with a polygon."
            _extreme_points = (sorted_points[0], sorted_points[-1])
            _intersection_points_list.append(_extreme_points)
            assert all([isinstance(_p, Point) for _p in _extreme_points]), "Object must be a Point type."
            assert all([not _p.is_empty for _p in _extreme_points]), "Point must not be empty."

        return _intersection_points_list[0], _intersection_points_list[1]
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise RuntimeError("Intersection with dies failed at func 'intersection_with_dies'.")


def splitting_lines(top_intersection_points, bottom_intersection_points) -> list[list[LineString]]:
    try:
        left_boundary = LineString((bottom_intersection_points[0], top_intersection_points[0]))
        right_boundary = LineString((bottom_intersection_points[1], top_intersection_points[1]))

        _output = [[left_boundary], [right_boundary]]

        for _line in _output:
            assert isinstance(_line[0], LineString), "Split line must be a LineString type."
            assert not _line[0].is_empty, "Split line must not be empty."

        return _output
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def translate_geoms_increase_gap(_gap: float, _geom_list: list[list]) -> list[list]:
    try:
        assert len(_geom_list) == 2, "Input shall have list of two lists of geometries"
        _factors = [1, -1]
        _output_list = []
        for _side_index, _side_list in enumerate(_geom_list):
            _side_output_list = []
            for _geom_index, _input_geom in enumerate(_side_list):
                x_off = _factors[_side_index] * 0.5 * _gap
                _side_output_list.append(translate(_input_geom, xoff=x_off))
            _output_list.append(_side_output_list)
        return _output_list
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def delta_area_trapezoid_minus_parallelogram(_h: float, _gaps: list[float]) -> float:
    """
    Gap has the shape of a Trapezoid with area 0.5 * Height * (MIN_base + MAX_base)
    After translation of left and right polygons by MIN_base distance
    the area of the Trapezoid is decreased as 0.5 * Height * (MIN_base + MAX_base - 2 * MIN_base) =
    = 0.5 * Height * (MAX_base - MIN_base)
    """
    try:
        _area = 0.5 * _h * (_gaps[1] - _gaps[0])
        return _area
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def print_areas(_polygons: list[list[Polygon]], area_of_gap: float, area_except_middle: float):
    _title_str = []
    _area_str = []
    _side_names = ('left', 'right')
    try:
        for side_index, _side in enumerate(_polygons):
            for _p_index, _p in enumerate(_side):
                _title_str.append(f"area_{_side_names[side_index]}_{_p_index + 1}")
                _area_str.append(f"{_p.area:.1f}")

        LOGGER.info(
            f"{'/'.join(_title_str)}/area_gap/area_except_middle: "
            f"{'/'.join(_area_str)}/{area_of_gap:.1f}/{area_except_middle:.1f}")
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def print_optimization_step(
        area_initial, area_actual, _elong_coef, _rigid_zone_factor,
        _output_strain_based_on_contact_and_rigid_zone, _output_strain_based_on_area, _strain_error_value):
    LOGGER.info(
        f"area_ini/area_opt - elong_coef/rigid_factor - e_cont/e_area/error: "
        f"{area_initial:.0f}/"
        f"{area_actual:.0f} - "
        f"{_elong_coef:.3f}/"
        f"{_rigid_zone_factor:.3f} - "
        f"{_output_strain_based_on_contact_and_rigid_zone:.3f}/"
        f"{_output_strain_based_on_area:.3f}/"
        f"{_strain_error_value:.3f}")


def _upsetting_like_vertical_scale_factor(_input_width, _initial_width, _initial_height, _penetration):
    try:
        _relative_contact_width = _input_width / _initial_width
        _max_upsetting_factor = 0.5
        _upsetting_penetration_factor = _relative_contact_width * _max_upsetting_factor

        _upset_penetration = _penetration * _upsetting_penetration_factor
        _upset_height = _initial_height - _upset_penetration
        _upsetting_factor = _upset_height / _initial_height

        assert isinstance(_upsetting_factor, float), "Upsetting factor must be a float type."
        assert 1.0 >= _upsetting_factor > 0.0, "Upsetting factor value must be between 0 and 1."

        return _upsetting_factor
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise RuntimeError("Upsetting like vertical scale factor failed.")


def polygon_y_scale_factor(_input_polygon, _die_top, _die_bottom, _ini_w, _ini_h, _penetration):
    try:
        input_top_intersection_points, input_bottom_intersection_points = intersection_with_dies(_input_polygon, _die_top, _die_bottom)

        _gaps = gap_width_after_split(input_top_intersection_points, input_bottom_intersection_points)

        _upset_factor = _upsetting_like_vertical_scale_factor(_gaps[1], _ini_w, _ini_h, _penetration)

        return _upset_factor
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise RuntimeError("Scaling of polygon vertically failed.")


def trim_middle_return_residual_area(_p: Polygon, _die_top: LineString | Polygon, _die_bottom: LineString | Polygon,
                                     fin_h: float):
    try:
        top_intersection_points, bottom_intersection_points = intersection_with_dies(_p, _die_top, _die_bottom)

        _split_lines = splitting_lines(top_intersection_points, bottom_intersection_points)

        _split_polygons = [
            _split_polygon_by_line(_p, _split_lines[0][0], is_return_left=True),
            _split_polygon_by_line(_p, _split_lines[1][0], is_return_left=False)
        ]

        _gaps = gap_width_after_split(top_intersection_points, bottom_intersection_points)

        area_of_trapezoid = delta_area_trapezoid_minus_parallelogram(fin_h, _gaps)

        area_except_middle = sum([sum([_p.area for _p in _side]) for _side in _split_polygons]) + area_of_trapezoid

        # print_areas(_split_polygons, area_of_trapezoid, area_except_middle)

        return area_except_middle, _split_lines, _split_polygons, _gaps
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def strain_error(_width_of_contact_numpy: np.ndarray, _area_except_middle: float, _length_of_contact: float, _strain_height: float, initial_width: float, initial_height: float, _final_h: float, _area_initial: float, iteration: list, eo: int):
    try:
        _width_of_contact = _width_of_contact_numpy.item(0)
        _elong_coef, _strain_length_contact = strain_length_based_on_contact_shape(_width_of_contact, _length_of_contact, initial_width, initial_height, _strain_height)

        _rigid_zone_factor = _rigid_zone_weighting_factor(_area_initial, _width_of_contact, _final_h)

        _output_strain_based_on_contact_and_rigid_zone = _strain_length_contact / _rigid_zone_factor
        area_actual = _area_except_middle + _final_h * _width_of_contact
        _output_strain_based_on_area = math.log(_area_initial / area_actual)
        _strain_error_relative = abs(1 - _strain_length_contact / _output_strain_based_on_area)

        iteration[0] = iteration[0] + 1
        if eo == 12:
            if iteration[0] == 2:
                print("")
        return _strain_error_relative
    except Exception:
        return 1e6


def gap_width_after_split(_top_points, _bottom_points) -> list[float]:
    """Returns maximum and minimum gap width between two lines"""
    try:
        distance_between_upper_points = abs(_top_points[0].x - _top_points[1].x)
        distance_between_bottom_points = abs(_bottom_points[0].x - _bottom_points[1].x)

        _max_gap_width = max((distance_between_upper_points, distance_between_bottom_points))
        _min_gap_width = min((distance_between_upper_points, distance_between_bottom_points))

        for _gap in [_min_gap_width, _max_gap_width]:
            assert isinstance(_gap, float), "Distance between intersection points must be a float type."
            assert _gap >= 0.0, "Distance between intersection points must be zero or positive."

        return [_min_gap_width, _max_gap_width]
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise RuntimeError("Gap width after split failed.")


def strain_length_based_on_contact_shape(_contact_w, _contact_l, initial_width: float, initial_height: float, _strain_vertical):
    """Returns coefficient, negative means narrow contact shape, positive means wide."""
    try:


        _contact_area_actual = _contact_l * _contact_w
        _contact_area = max(0.1, _contact_area_actual)
        _contact_size_of_equiv_square = math.sqrt(_contact_area)  # Contact length of ideal square initial
        _contact_area_shape_factor_with_sign = _contact_w / _contact_size_of_equiv_square - 1
        _elongation_coef_in_manip_axis = 0.5 + math.atan(_contact_area_shape_factor_with_sign) / math.pi
        _strain_horizontal_in_manip_axis = -1 * _elongation_coef_in_manip_axis * _strain_vertical
        return _elongation_coef_in_manip_axis, _strain_horizontal_in_manip_axis
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def _rigid_zone_weighting_factor(_cross_section_area: float, _width: float, _final_height: float) -> float:
    try:
        _localization_zone_height = 0.5 * _width
        _limited_height = 0.5 * _final_height
        if _localization_zone_height <= _limited_height:
            _half_localization_zone_area = 0.5 * _localization_zone_height * _width
        else:
            _small_trapezoid_base = _width - 2 * _limited_height
            _half_localization_zone_area = 0.5 * _limited_height * (_width + _small_trapezoid_base)
        _full_localization_zone_area = 2 * _half_localization_zone_area
        _rigid_zone_weighting_factor_output = _cross_section_area / _full_localization_zone_area - 1
        return _rigid_zone_weighting_factor_output
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def _split_polygon_by_line(_input_polygon: Polygon, _l: LineString, is_return_left: bool):
    try:
        # Split the polygon into two parts using difference operation
        _limited_area = 1e-5 * _input_polygon.area
        _extended_line = scale(_l, xfact=2, yfact=2, origin=_l.centroid)
        _s = split(_input_polygon, _extended_line)
        _f_polygons = _filter_by_centroid(_s, _l, is_return_left)
        _a_polygons = [_a for _a in _f_polygons if not _a.is_empty and _a.area > _limited_area]
        return _f_polygons
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def _filter_by_centroid(_polygons: GeometryCollection, _l: LineString, is_return_left: bool) -> list[Polygon]:
    # Calculate intersection of the line with X-axis
    _valid_polygons = []
    try:
        for _p in _polygons.geoms:
            _point = _p.centroid
            _is_left = is_left(_point, _l)
            _is_valid = is_return_left == _is_left
            if _is_valid:
                _valid_polygons.append(_p)
        return _valid_polygons
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def is_left(point: Point, _line_string: LineString):
    """
    This function takes a point and a line, both specified by two-point coordinates,
    and returns a boolean indicating whether the point is to the left of the line.

    Parameters:
        point (tuple): The point coordinates as a tuple (x, y).
        _line_string (tuple): The line specified by two points, each point being a tuple (x, y).

    Returns:
        bool: True if the point is to the left of the line, False otherwise.
    """
    try:
        px, py = point.x, point.y
        x1, y1, x2, y2 = _line_string.bounds
        # x1, y1, x2, y2 = line
        cross_product = (x2 - x1) * (py - y1) - (y2 - y1) * (px - x1)
        return cross_product > 0
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def middle_polygon_fill_gap(boundary_list: list[list[LineString]], _optimal_width_of_contact: float) -> Polygon:
    try:
        _middle_polygon_shift_x = 0.5 * _optimal_width_of_contact
        _left_middle: LineString = translate(boundary_list[0][0], xoff=-_middle_polygon_shift_x)
        _right_middle: LineString = translate(boundary_list[1][0], xoff=_middle_polygon_shift_x)
        _left_points = sorted(_left_middle.coords, key=lambda _point: _point[1], reverse=False)
        _right_points = sorted(_right_middle.coords, key=lambda _point: _point[1], reverse=True)
        _middle_points = (*_left_points, *_right_points)
        _middle_polygon = Polygon(_middle_points)
        return _middle_polygon
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def translate_polygons_after_optimization(polygon_list: list[list[Polygon]], _optimal_width_of_contact: float) -> (Polygon, Polygon):
    try:
        _factors = [-1, 1]
        _output_list = []
        for _side_index, _side_list in enumerate(polygon_list):
            _output_side_list = []
            for _polygon_index, _polygon in enumerate(_side_list):
                _offset = _factors[_side_index] * 0.5 * _optimal_width_of_contact
                _output_side_list.append(translate(_polygon, xoff=_offset))
            _output_list.append(_output_side_list)
        return _output_list
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def assert_area_error(_area_1: float, _area_2: float):
    try:
        _area_error = (_area_1 / _area_2 - 1)
        _limiting_error = 1e-5
        assert _area_error < _limiting_error, \
            f"Area error {100.0 * _area_error:.6f}% exceeds limiting error ({100.0 * _limiting_error:.6f}%)."
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def center_regarding_dies(_polygon: Polygon, _line_1: LineString, _line_2: LineString) -> Polygon:

    def length_difference(_delta_y_numpy: np.ndarray) -> float:
        _delta_y: float = _delta_y_numpy.item(0)
        # noinspection PyBroadException
        try:
            _translated = translate(_polygon, yoff=_delta_y)
            return abs(_line_1.intersection(_translated).length - _line_2.intersection(_translated).length)
        except Exception:
            return 1e6

    try:
        _result = optimize.minimize(length_difference, np.array([0.0]), tol=1e-3)
        _optimal_y_offset = _result.x.item(0)
        return translate(_polygon, yoff=_optimal_y_offset)
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def polygon_to_list(_polygon: Polygon) -> list:
    """Converts a Polygon to a list of lists."""
    try:
        assert isinstance(_polygon, Polygon), \
            f"Can't convert polygon to list of coordinates. Type must be Polygon, but {type(_polygon)} received."
        if _polygon.is_empty:
            return []
        return [list(_tuple) for _tuple in list(_polygon.exterior.coords)]
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def polygon_to_binary(_polygon: Polygon):
    """Converts a Polygon to a list of lists."""
    try:
        assert isinstance(_polygon, Polygon), \
            f"Can't convert polygon to list of coordinates. Type must be Polygon, but {type(_polygon)} received."
        if _polygon.is_empty:
            return []
        list_of_tuples = [list(_tuple) for _tuple in list(_polygon.exterior.coords)]
        _binary = b''.join(struct.pack('dd', *tup) for tup in list_of_tuples)
        return _binary
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def binary_to_list_of_tuples(_binary) -> list[tuple]:
    try:
        return list(struct.iter_unpack('dd', _binary))
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise RuntimeError("FAILED convert binary string into list of tuples (list of 2D coordinates).")


def prolongation_rotate_polygon(input_polygon: Polygon, angle: float) -> Polygon:
    """
    Takes '_final_Polygon' from 'previous'.
    Rotates it by 'angle' and translates its Centroid to axis origin.
    Returns a dict with 'initial_height', 'initial_width' and 'initial_polygon'."""
    try:
        assert isinstance(input_polygon, Polygon) and not input_polygon.is_empty
        assert angle is not None and isinstance(angle, float)

        if angle != 0.0:
            _rotated = rotate(input_polygon, angle, origin=(.0, .0))
        else:
            _rotated = input_polygon

        centroid = _rotated.centroid
        _centered_by_centroid = translate(_rotated, xoff=-centroid.x, yoff=-centroid.y)

        return _centered_by_centroid
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def height_of_polygon(_p: Polygon) -> float | None:
    try:
        if isinstance(_p, Polygon):
            return _p.bounds[3] - _p.bounds[1]
        return None
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def width_of_polygon(_p: Polygon) -> float | None:
    try:
        if isinstance(_p, Polygon):
            return _p.bounds[2] - _p.bounds[0]
        return None
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def final_dies_polygons(input_polygons: list[Polygon], penetration) -> list[Polygon]:
    try:
        _die_top = translate(input_polygons[0], yoff=-penetration / 2)
        _die_bottom = translate(input_polygons[1], yoff=+penetration / 2)
        return [_die_top, _die_bottom]
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def __radial_prolongation_height_vs_cross_section_area(p: Polygon, billet_length: np.float64) -> list[tuple[float, float]]:
    """
    Computes the coefficients 'a' and 'b' for the linear equation ra = a*w + b,
    where 'ra' is the relative area of the intersection between the input polygon 'p'
    and a box of width 'w', iterated from 99% to 1% of 'p's width.

    Parameters:
    - p (Polygon): Input Shapely Polygon object.

    Returns:
    - a (float): Coefficient for width 'w'.
    - b (float): Constant term.
    """
    if not isinstance(p, Polygon):
        raise TypeError("Input 'p' must be a Shapely Polygon object.")

    try:
        min_x, min_y, max_x, max_y = p.bounds
        polygon_width = max_x - min_x
        polygon_height = max_y - min_y

        if polygon_width == 0 or polygon_height == 0:
            raise ValueError("Input polygon must have non-zero width and height.")

        p_area = p.area
        if p_area == 0:
            raise ValueError("Input polygon must have area")

        volume = p_area * billet_length
        ini_billet_side_projection_area = polygon_width * billet_length

        center_x = (min_x + max_x) / 2
        min_y_b = min_y - 1.0
        max_y_b = max_y + 1.0

        result = []

        for percent in range(100, 0, -10):
            w = (percent / 100) * polygon_width
            l = (percent / 100) * billet_length

            min_x_b = center_x - w / 2
            max_x_b = center_x + w / 2

            # Create the box with the current width 'w' and the same height as 'p'
            b_box = box(min_x_b, min_y_b, max_x_b, max_y_b)

            # Compute the intersection of 'p' and 'b_box'
            ip = p.intersection(b_box)

            # Delta volume
            dv = volume - ip.area * l

            # Cross-section area
            final_cross_section_area = ini_billet_side_projection_area * (percent / 100) ** 2

            # Delta height
            dh = dv / final_cross_section_area

            # Final height
            final_height = polygon_height + dh

            result.append((final_cross_section_area, final_height,))

        # Perform linear regression to find coefficients 'a' and 'b'
        # ra = a * w + b
        # Using numpy polyfit with degree 1 for linear fit
        # a, b = np.polyfit(result, fh_values, 1)

        return result
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise
