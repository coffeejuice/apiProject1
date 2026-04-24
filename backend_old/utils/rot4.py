import numpy as np

from forgelab.srv_solver.operations.pre_functions import \
    rotation_matrix_to_euler_angles, apply_euler_angles_to_coordinate_system


if __name__ == "__main__":
    # Example usage:
    i_vectors = np.array([
        [1, 0, 0],
        [0, 1, 0],
        [0, 0, 1]
    ])
    t_vectors = np.array([
        [0.5, -0.5, 0],
        [-0.5, -0.5, 0],
        [0, 0, -1]
    ])

    # Convert to Euler angles.
    z_rotation, y_rotation, x_rotation = rotation_matrix_to_euler_angles(i_vectors, t_vectors)

    print(f"Yaw (Z-axis rotation): {z_rotation} degrees")
    print(f"Pitch (Y-axis rotation): {y_rotation} degrees")
    print(f"Roll (X-axis rotation): {x_rotation} degrees")

    # Apply the Euler angles to the initial coordinate system
    resulting_system = apply_euler_angles_to_coordinate_system(t_vectors, z_rotation, y_rotation, x_rotation)

    print("Resulting Coordinate System:")
    print(resulting_system)
