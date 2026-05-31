import logging
import math
import numpy as np
from scipy.spatial import Delaunay
from shapely.geometry import Polygon, box

from forgelab.srv_solver.plot_2d import save_2d_plot_billet_edges
from forgelab.common.file_operations import sub_operation_abs_path

LOGGER = logging.getLogger(__name__)


def get_billet_measurements_with_contour(mesh_dict, max_element_size, parameters):
    case_msg = "FAILED func 'get_billet_measurements_with_contour'"
    try:
        edges_xy, contour_xy = get_2d_projection_contour(mesh_dict['nodes'][:, [0, 1]], max_element_size)
        edges_xz, contour_xz = get_2d_projection_contour(mesh_dict['nodes'][:, [0, 2]], max_element_size)
        save_2d_plot_billet_edges(mesh_dict['nodes'][:, [0, 1]],
                                  edges_xy,
                                  sub_operation_abs_path(parameters),
                                  'edges_01_xy')
        save_2d_plot_billet_edges(mesh_dict['nodes'][:, [0, 2]],
                                  edges_xy,
                                  sub_operation_abs_path(parameters),
                                  'edges_01_xy')
        polygon_parameters = __get_billet_measurements(contour_xy, contour_xz)
        parameters['operation']['imported_keyfile']['objects'][1]['measurements']['contour'] = polygon_parameters
    except KeyError as _err:
        raise KeyError(f"{case_msg} with KeyError: {str(_err)}")
    except Exception as _err:
        raise RuntimeError(f"{case_msg} with Exception: {str(_err)}")


def get_2d_projection_contour(node_coordinates, min_element_size):
    case_msg = "FAILED func 'get_2d_projection_contour'"
    try:
        set_of_edges = alpha_shape(node_coordinates, min_element_size, only_outer=True)
        lines = convert_set_of_edges_to_line(node_coordinates, set_of_edges)
    except KeyError as _err:
        LOGGER.error(f"{case_msg} with KeyError: {str(_err)}")
    except Exception as _err:
        LOGGER.error(f"{case_msg} with Exception: {str(_err)}")
    else:
        return set_of_edges, lines
    raise RuntimeError(case_msg)


def alpha_shape(points, alpha, only_outer=True):
    """
    https://stackoverflow.com/questions/50549128/boundary-enclosing-a-given-set-of-points/50714300#50714300
    Compute the alpha shape (concave hull) of a set of points.
    :param points: np.ndarray of shape (n,2) points.
    :param alpha: alpha value.
    :param only_outer: boolean value to specify if we keep only the outer border
    or also inner edges.
    :return: set of (i,j) pairs representing edges of the alpha-shape. (i,j) are
    the indices in the points array.
    """
    case_msg = "FAILED func 'alpha_shape'"

    assert points.shape[0] > 3, f"{case_msg} with AssertionError: Need at least four points"

    def add_edge(list_of_edges, i, j):
        """
        Add an edge between the i-th and j-th points,
        if not in the list already
        """
        if (i, j) in list_of_edges or (j, i) in list_of_edges:
            # already added
            assert (j, i) in list_of_edges, "Can't go twice over same directed edge right?"
            if only_outer:
                # if both neighboring triangles are in shape, it's not a boundary edge
                list_of_edges.remove((j, i))
            return
        list_of_edges.add((i, j))

    try:
        tri = Delaunay(points)
        edges = set()
        # Loop over triangles:
        # ia, ib, ic = indices of corner points of the triangle
        for ia, ib, ic in tri.vertices:
            pa = points[ia]
            pb = points[ib]
            pc = points[ic]
            # Computing radius of triangle circumcircle
            # www.mathalino.com/reviewer/derivation-of-formulas/derivation-of-formula-for-radius-of-circumcircle
            a = np.sqrt((pa[0] - pb[0]) ** 2 + (pa[1] - pb[1]) ** 2)
            b = np.sqrt((pb[0] - pc[0]) ** 2 + (pb[1] - pc[1]) ** 2)
            c = np.sqrt((pc[0] - pa[0]) ** 2 + (pc[1] - pa[1]) ** 2)
            s = (a + b + c) / 2.0
            area = np.sqrt(s * (s - a) * (s - b) * (s - c))
            circum_r = a * b * c / (4.0 * area)
            if circum_r < alpha:
                add_edge(edges, ia, ib)
                add_edge(edges, ib, ic)
                add_edge(edges, ic, ia)
    except KeyError as _err:
        LOGGER.error(f"{case_msg} with KeyError: {str(_err)}")
    except Exception as _err:
        LOGGER.error(f"{case_msg} with Exception: {str(_err)}")
    else:
        return edges
    raise RuntimeError(case_msg)


# def shapely_examples():
# billet_xz_polygon = Polygon([(0, 0), (1, 1), (1, 0)])
# billet_xz_projection_area = billet_xz_polygon.area
# billet_length = billet_xz_polygon.length
# billet_bounds = billet_xz_polygon.bounds
# b = box(0.0, 0.0, 1.0, 1.0)
# box_edges = list(b.exterior.coords)
# pprint(box_edges)
# a = LineString([(0, 0), (1, 1), (1, 2), (2, 2)])
# c = LineString([(0, 0), (1, 1), (2, 1), (2, 2)])
# x = a.intersection(c)
# pprint(list(x))
# polygons = MultiPolygon([billet_xz_polygon, b])
# number_of_polygons = len(polygons.geoms)
# billet_centroid = billet_xz_polygon.centroid
# billet_box_intersection = billet_xz_polygon.intersection(b)
# billet_envelope = billet_xz_polygon.envelope
# billet_rotated_envelope = billet_xz_polygon.minimum_rotated_rectangle
# pass


def __get_billet_measurements(contour_01_xy, contour_02_xz):
    case_msg = "FAILED func '__get_billet_measurements'"
    try:
        polygon_xy = Polygon(contour_01_xy)
        polygon_xz = Polygon(contour_02_xz)
        # polygon_yz = Polygon(contour_12_yz)

        bounds_3d = get_bounds_3d(polygon_xy, polygon_xz)
        bounds_center_3d = np.average(bounds_3d, axis=0)

        billet_bounds = polygon_xz.bounds  # Returns a (minx, miny, maxx, maxy) tuple (float values)
        billet_centroid = polygon_xz.centroid
        billet_length = billet_bounds[2] - billet_bounds[0]
        billet_height = billet_bounds[3] - billet_bounds[1]
        billet_xz_projection_area = polygon_xz.area
        (
            bounds_excluding_tail_barrels,
            billet_height_histogram,
            length_excluding_tail_barrels,
            left_tail_barrel_length,
            right_tail_barrel_length
        ) = get_tail_barrel(
            billet_bounds,
            billet_centroid,
            billet_length,
            billet_xz_projection_area,
            polygon_xz)

        # return measurements
        result = {
            'billet_intersection_area': billet_height_histogram,
            'billet_length': billet_length,
            'billet_height': billet_height,
            'billet_bounds': billet_bounds,
            'billet_contour_coordinates': contour_02_xz,
            'billet_centroid': [billet_centroid.x, billet_centroid.y],
            'billet_xz_projection_area': billet_xz_projection_area,
            'left_tail_barrel_length': left_tail_barrel_length,
            'right_tail_barrel_length': right_tail_barrel_length,
            'length_excluding_tail_barrels': length_excluding_tail_barrels,
            'bounds_excluding_tail_barrels': bounds_excluding_tail_barrels,
            'bounds': bounds_3d,
            'billet_center_point_3d': bounds_center_3d}
    except KeyError as _err:
        LOGGER.error(f"{case_msg} with KeyError: {str(_err)}")
    except Exception as _err:
        LOGGER.error(f"{case_msg} with Exception: {str(_err)}")
    else:
        return result
    raise RuntimeError(case_msg)


def get_tail_barrel(billet_bounds, billet_centroid, billet_length, billet_xz_projection_area, polygon_xz):
    case_msg = "FAILED func 'get_tail_barrel'"
    try:
        x_increment = 0.5
        number_of_measurements = math.ceil(billet_length / x_increment)
        billet_height_histogram = []

        for i in range(number_of_measurements):
            # shapely.geometry.box(minx, miny, maxx, maxy, ccw=True)
            box_min_x = billet_bounds[0] + i * x_increment
            if i == number_of_measurements - 1:
                box_max_x = billet_bounds[2]
            else:
                box_max_x = box_min_x + x_increment
            measurement_box = box(box_min_x, billet_bounds[1] * 1.1, box_max_x, billet_bounds[3] * 1.1)
            billet_box_intersection = polygon_xz.intersection(measurement_box)
            increment_area = billet_box_intersection.area
            increment_average_height = increment_area / (box_max_x - box_min_x)
            increment_average_x_coordinate = (box_min_x + box_max_x) * 0.5
            billet_height_histogram.append((increment_average_x_coordinate, increment_average_height))

        billet_average_height = billet_xz_projection_area / billet_length
        relative_tail_barrel_evaluation_height = 0.75

        # shapely.geometry.box(minx, miny, maxx, maxy, ccw=True)
        slicing_box_min_y = relative_tail_barrel_evaluation_height * billet_average_height
        slicing_box_max_y = 1.1 * max(coordinates[1] for coordinates in billet_height_histogram)
        slicing_box_min_x = (billet_bounds[0] - billet_centroid.x) * 1.1 + billet_centroid.x
        slicing_box_max_x = (billet_bounds[2] - billet_centroid.x) * 1.1 + billet_centroid.x
        intersecting_box = box(slicing_box_min_x, slicing_box_min_y, slicing_box_max_x, slicing_box_max_y)
        height_histogram_contour = [
            [billet_height_histogram[0][0], 0.0],
            *billet_height_histogram,
            [billet_height_histogram[-1][0], 0.0],
            [billet_height_histogram[0][0], 0.0]]
        height_histogram_polygon = Polygon(height_histogram_contour)
        area_polygon_excluding_tail_barrels = height_histogram_polygon.intersection(intersecting_box)
        bounds_excluding_tail_barrels = area_polygon_excluding_tail_barrels.bounds
        length_excluding_tail_barrels = \
            bounds_excluding_tail_barrels[2] - bounds_excluding_tail_barrels[0]
        left_tail_barrel_length = bounds_excluding_tail_barrels[0] - billet_bounds[0]
        right_tail_barrel_length = billet_bounds[2] - bounds_excluding_tail_barrels[2]
    except KeyError as _err:
        LOGGER.error(f"{case_msg} with KeyError: {str(_err)}")
    except Exception as _err:
        LOGGER.error(f"{case_msg} with Exception: {str(_err)}")
    else:
        return (
            bounds_excluding_tail_barrels,
            billet_height_histogram,
            length_excluding_tail_barrels,
            left_tail_barrel_length,
            right_tail_barrel_length)
    raise RuntimeError(case_msg)


def get_bounds_3d(polygon_xy, polygon_xz):
    case_msg = "FAILED func 'get_bounds_3d'"
    try:
        bounds_xy = polygon_xy.bounds  # Returns a (minx, miny, maxx, maxy) tuple (float values)
        bounds_xz = polygon_xz.bounds  # Returns a (minx, minz, maxx, maxz) tuple (float values)
        result = np.array([
            [bounds_xy[0], bounds_xy[1], bounds_xz[1]],
            [bounds_xy[2], bounds_xy[3], bounds_xz[3]]])
    except KeyError as _err:
        LOGGER.error(f"{case_msg} with KeyError: {str(_err)}")
    except Exception as _err:
        LOGGER.error(f"{case_msg} with Exception: {str(_err)}")
    else:
        return result
    raise RuntimeError(case_msg)


def convert_set_of_edges_to_line(coordinates_array, set_of_edges):
    try:
        random_edges = list(set_of_edges)
        #
        arranged_edges = [random_edges.pop(0)]
        for _ in range(len(random_edges)):
            last_arranged_point = arranged_edges[-1][-1]
            for index, edge_tuple in enumerate(random_edges):
                first_point_of_edge_tuple = edge_tuple[0]
                if first_point_of_edge_tuple == last_arranged_point:
                    line = random_edges.pop(index)
                    arranged_edges.append(line)
                    break
        #
        arranged_points = [edge_tuple[0] for edge_tuple in arranged_edges]
        arranged_points.append(arranged_edges[-1][-1])
        #
        return [tuple(coordinates_array[point_number, :]) for point_number in arranged_points]
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise
