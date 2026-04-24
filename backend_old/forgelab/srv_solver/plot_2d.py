import logging
import os
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import cm


LOGGER = logging.getLogger(__name__)


# def save_2d_plot_billet_edges(coordinates, __edges, path, name: str):
#     thread = Thread(target=__save_2d, args=(coordinates, __edges, path, name), daemon=True)
#     # set the daemon attribute
#
#     thread.start()
#     thread.join()


def save_2d_plot_billet_edges(coordinates, __edges, path, name: str):
    try:
        filename = f'{name}.png'
        path_save_fig = os.path.join(path, 'images')
        os.makedirs(path_save_fig, exist_ok=True)
        pathfile_save_fig = os.path.join(path_save_fig, filename)
    except KeyError as _err:
        raise KeyError(f"FAILED func 'save_2d_plot_billet_edges' with KeyError: {str(_err)}")
    except Exception as _err:
        raise Exception(f"FAILED func 'save_2d_plot_billet_edges' with Exception: {str(_err)}")

    case_msg = f"FAILED func 'save_2d_plot_billet_edges' when saving file: {pathfile_save_fig}"

    try:
        edges = np.array([list(i) for i in __edges.copy()]) if isinstance(__edges, set) else __edges

        fig, ax = plt.subplots(2, 2)
        fig.set_figheight(10)
        fig.set_figwidth(15)

        node_numbers_of_edges = np.unique(edges.ravel())

        _x = coordinates[:, 0]
        _y = coordinates[:, 1]
        _n = np.arange(len(_x))

        ax[0, 0].scatter(_x, _y)
        ax[0, 0].set_title('All nodes')
        for i, txt in enumerate(_n):
            ax[0, 0].annotate(txt, (_x[i], _y[i]))

        _x_edge = np.take(_x, node_numbers_of_edges)
        _y_edge = np.take(_y, node_numbers_of_edges)
        _n_edge = np.take(_n, node_numbers_of_edges)
        ax[0, 1].scatter(_x_edge, _y_edge, marker='x', color='red')
        ax[0, 1].set_title('Edge nodes')
        for i, txt in enumerate(_n_edge):
            ax[0, 1].annotate(txt, (_x_edge[i], _y_edge[i]))

        len_edges = len(edges)
        _color_value = np.arange(len_edges) / len_edges
        ax[1, 0].set_title('Edges in original order')
        for i, edge in enumerate(edges):
            _x_line = np.take(_x, edge)
            _y_line = np.take(_y, edge)
            ax[1, 0].plot_3d(_x_line, _y_line, c=cm.cool(_color_value[i]))

        plt.savefig(pathfile_save_fig, dpi=200)
        # plt.show()
        plt.close(fig)
    except KeyError as _err:
        raise KeyError(f"{case_msg} with KeyError: {str(_err)}")
    except Exception as _err:
        raise Exception(f"{case_msg} with Exception: {str(_err)}")


# def plot_nodes_and_numbers(coordinates, numbers, path, name: str):
#     thread = Thread(target=__plot_nodes_and_numbers, args=(coordinates, numbers, path, name), daemon=True)
#     thread.start()
#     thread.join()


def plot_nodes_and_numbers(coordinates, numbers: list, path, name: str):
    try:
        filename = f'{name}.png'
        path_save_fig = os.path.join(path, 'images')
        os.makedirs(path_save_fig, exist_ok=True)
        pathfile_save_fig = os.path.join(path_save_fig, filename)
    except KeyError as _err:
        raise KeyError(f"FAILED func 'plot_nodes_and_numbers' with KeyError: {str(_err)}")
    except Exception as _err:
        raise Exception(f"FAILED func 'plot_nodes_and_numbers' with Exception: {str(_err)}")

    case_msg = f"FAILED func 'plot_nodes_and_numbers' when saving file: {pathfile_save_fig}"

    try:
        fig, ax = plt.subplots(2, 2)
        fig.set_figheight(10)
        fig.set_figwidth(15)

        dim = [[0, 1], [0, 2], [1, 2]]
        plot_num = [(0, 0), (0, 1), (1, 0)]
        title = ['Top view: XY-projection', 'Operator\'s view: XZ-projection', 'Axial view: YZ-projection']
        for i in range(3):
            _dim = dim[i]
            _plot_num = plot_num[i]
            _title = title[i]

            _x = coordinates[:, _dim[0]]
            _y = coordinates[:, _dim[1]]
            _n = np.arange(len(_x))

            ax[_plot_num].scatter(_x, _y)
            ax[_plot_num].set_title(_title)
            for j, txt in enumerate(_n):
                if j in numbers:
                    ax[_plot_num].annotate(txt, (_x[j], _y[j]))

        plt.savefig(pathfile_save_fig, dpi=200)
        plt.close(fig)
    except KeyError as _err:
        raise KeyError(f"{case_msg} with KeyError: {str(_err)}")
    except Exception as _err:
        raise Exception(f"{case_msg} with Exception: {str(_err)}")
