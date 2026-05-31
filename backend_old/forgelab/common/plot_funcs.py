import matplotlib.pyplot as plt
from shapely.geometry import Polygon


def plot_trimesh_3d(mesh):
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    ax.plot_trisurf(mesh.vertices[:, 0], mesh.vertices[:, 1], triangles=mesh.faces, Z=mesh.vertices[:, 2])
    plt.show()


def _plot_polygon(_polygon: Polygon):
    # If you want to visualize the 2D line, use matplotlib
    plt.figure()
    plt.plot(*_polygon.exterior.xy)
    plt.xlabel('Y-axis becomes X-axis in 2D')
    plt.ylabel('Z-axis becomes Y-axis in 2D')
    plt.title('2D projection of 3D intersection contour')
    plt.show()


def _plot_multy_polygons(args):
    # Plot multiple Polygon objects given in args list

    plt.figure()

    # List of fill colors with 10 different colors
    colors = ['b', 'g', 'r', 'c', 'm', 'y', 'k', 'w', 'orange', 'purple']

    # new_shape = ops.unary_union(args)
    # fig, axs = plt.subplots()
    plt.gca().set_aspect('equal', 'datalim')
    # axs.set_aspect('equal', 'datalim')

    for _i, geom in enumerate(args):
        xs, ys = geom.exterior.xy
        plt.fill(xs, ys, alpha=0.5, fc=colors[_i], ec='none')

    plt.show()


def plot_numpy_2d(xy):
    # If you want to visualize the 2D line, use matplotlib
    plt.figure()
    plt.plot(xy[:, 0], xy[:, 1])
    plt.xlabel('Y-axis becomes X-axis in 2D')
    plt.ylabel('Z-axis becomes Y-axis in 2D')
    plt.title('2D projection of 3D intersection contour')
    plt.show()


# def save_image(section_2d):
#     scene = section_2d.scene()
#     bytes_ = scene.save_image()
#     image = Image.open(io.BytesIO(bytes_))
#     image.save(r"path\image.png")
