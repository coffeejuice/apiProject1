import traceback
from multiprocessing import Process, Queue
import matplotlib.pyplot as plt
import numpy as np
import time
# import io
# import trimesh
from trimesh import Trimesh
# import PIL.Image as Image
# from mpl_toolkits.mplot3d import Axes3D
from shapely.geometry import Polygon
# from shapely import ops


# Fixing random state for reproducibility
np.random.seed(19680801)


class PlotWorker(Process):
    def __init__(self, worker_id: int, task_queue: Queue):
        super().__init__()
        self.x = []
        self.y = []
        self.colors = ['b', 'g', 'r', 'c', 'm', 'y', 'k', 'w', 'orange', 'purple']
        self.worker_id = worker_id
        self.task_queue: Queue = task_queue
        self.fig = plt.figure()
        self.ax = self.fig.add_subplot(111)
        self.ln, = self.ax.plot([], [])
        self.fig.canvas.draw()  # draw and show it
        plt.show(block=False)

    def run(self):
        print(f"{self.log_id} started.")
        self.fig.canvas.draw()  # draw and show it
        plt.show(block=False)

        while True:
            try:
                img_param: tuple = self.task_queue.get()

                print(f"{self.log_id} Queue feed data")

                if len(img_param) == 0 or img_param[0] is None:
                    print(f"{self.log_id} received shutdown signal.")
                    break

                print(f"{self.log_id} received a task")

                # Process the task
                self._silent_worker(img_param)

            except Exception as _err:
                plt.close('all')
                print(f"{self.log_id} {type(_err).__name__}: {_err}")
                break
        print(f"{self.log_id} stopped.")


    def _silent_worker(self, img_param: tuple):
        if all([isinstance(_p, Polygon) for _p in img_param]):
            self._plot_multy_polygons(img_param)
        elif len(img_param) == 1 and isinstance(img_param[0], np.ndarray):
            self.plot_numpy_2d(img_param[0])
        else:
            return
        self.fig.canvas.draw()
        plt.show()
        print("...done")

    @staticmethod
    def plot_trimesh_3d(mesh: Trimesh):
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')
        ax.plot_trisurf(mesh.vertices[:, 0], mesh.vertices[:, 1], triangles=mesh.faces, Z=mesh.vertices[:, 2])

    @staticmethod
    def _plot_polygon(_polygon: Polygon):
        # If you want to visualize the 2D line, use matplotlib
        plt.plot(*_polygon.exterior.xy)
        plt.xlabel('Y-axis becomes X-axis in 2D')
        plt.ylabel('Z-axis becomes Y-axis in 2D')
        plt.title('2D projection of 3D intersection contour')

    def _plot_multy_polygons(self, polygons: tuple):
        # Plot multiple Polygon objects given in args list

        # new_shape = ops.unary_union(args)
        # fig, axs = plt.subplots()
        plt.gca().set_aspect('equal', 'datalim')
        # axs.set_aspect('equal', 'datalim')

        for _i, geom in enumerate(polygons):
            geom: Polygon
            xs, ys = geom.exterior.xy
            self.ln.set_xdata(xs)
            self.ln.set_ydata(ys)
            self.ax.relim()

            self.ax.autoscale_view(True, True, True)
            self.fig.canvas.draw()
            # plt.fill(xs, ys, alpha=0.5, fc=self.colors[_i], ec='none')

    @staticmethod
    def plot_numpy_2d(xy: np.ndarray):
        # If you want to visualize the 2D line, use matplotlib
        plt.plot(xy[:, 0], xy[:, 1])
        plt.xlabel('Y-axis becomes X-axis in 2D')
        plt.ylabel('Z-axis becomes Y-axis in 2D')
        plt.title('2D projection of 3D intersection contour')

    @property
    def log_id(self):
        time_str = time.strftime("%H:%M:%S", time.gmtime())
        return f"{time_str} Plot Worker #{self.worker_id} {traceback.format_exc()}"
