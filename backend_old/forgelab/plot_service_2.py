from multiprocessing import Process, Pipe
import matplotlib.pyplot as plt
import numpy as np
# import io
# import trimesh
from trimesh import Trimesh
# import PIL.Image as Image
# from mpl_toolkits.mplot3d import Axes3D
from shapely.geometry import Polygon
# from shapely import ops


# Fixing random state for reproducibility
np.random.seed(19680801)


class NBPlot:
    def __init__(self):
        self.plot_pipe, plotter_pipe = Pipe()
        self.plotter = ProcessPlotter()
        self.plot_process = Process(
            target=self.plotter, args=(plotter_pipe,), daemon=True)
        self.plot_process.start()

    def plot(self, data, finished=False):
        send = self.plot_pipe.send
        if finished:
            send(None)
        else:
            send(data)


class ProcessPlotter:
    def __init__(self):
        self.x = []
        self.y = []
        self.colors = ['b', 'g', 'r', 'c', 'm', 'y', 'k', 'w', 'orange', 'purple']

    @staticmethod
    def terminate():
        plt.close('all')

    def call_back(self):
        while self.pipe.poll():
            command = self.pipe.recv()
            if command is None:
                self.terminate()
                return False
            else:
                self.x.append(command[0])
                self.y.append(command[1])
                self.ax.plot(self.x, self.y, 'ro')
        self.ax.fill(self.x, self.y, alpha=0.5, fc=self.colors[0], ec='none')
        self.fig.canvas.draw()
        return True

    def __call__(self, pipe):
        print('starting plotter...')

        self.pipe = pipe
        self.fig, self.ax = plt.subplots()
        timer = self.fig.canvas.new_timer(interval=1000)
        timer.add_callback(self.call_back)
        timer.start()

        print('...done')
        plt.show()

    @staticmethod
    def plot_trimesh_3d(mesh: Trimesh):
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')
        ax.plot_trisurf(mesh.vertices[:, 0], mesh.vertices[:, 1], triangles=mesh.faces, Z=mesh.vertices[:, 2])
        plt.show()

    @staticmethod
    def _plot_polygon(_polygon: Polygon):
        # If you want to visualize the 2D line, use matplotlib
        plt.figure()
        plt.plot(*_polygon.exterior.xy)
        plt.xlabel('Y-axis becomes X-axis in 2D')
        plt.ylabel('Z-axis becomes Y-axis in 2D')
        plt.title('2D projection of 3D intersection contour')
        plt.show()

    def _plot_multy_polygons(self, args):
        # Plot multiple Polygon objects given in args list

        # List of fill colors with 10 different colors
        colors = ['b', 'g', 'r', 'c', 'm', 'y', 'k', 'w', 'orange', 'purple']

        # new_shape = ops.unary_union(args)
        # fig, axs = plt.subplots()
        plt.gca().set_aspect('equal', 'datalim')
        # axs.set_aspect('equal', 'datalim')

        for _i, geom in enumerate(args):
            xs, ys = geom.exterior.xy
            plt.fill(self.x, self.y, alpha=0.5, fc=colors[_i], ec='none')

    @staticmethod
    def plot_numpy_2d(xy):
        # If you want to visualize the 2D line, use matplotlib
        plt.figure()
        plt.plot(xy[:, 0], xy[:, 1])
        plt.xlabel('Y-axis becomes X-axis in 2D')
        plt.ylabel('Z-axis becomes Y-axis in 2D')
        plt.title('2D projection of 3D intersection contour')
        plt.show()
