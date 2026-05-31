import logging
import traceback
import time
from multiprocessing import Process, Queue, Semaphore
import numpy as np
import psutil
from mayavi import mlab
from mayavi.core.scene import Scene
from tvtk.pyface.tvtk_scene import TVTKScene
from mayavi.core.module import Module
from tvtk.tvtk_access import tvtk

from forgelab.common.common_funcs import log_error

# The offscreen Engine.
# from mayavi.api import OffScreenEngine

# Usual MayaVi imports
# from mayavi.scripts.util import get_data_dir
# from mayavi.sources.api import VTKXMLFileReader
# from mayavi.modules.api import Outline, ScalarCutPlane, Streamline


LOGGER = logging.getLogger(__name__)


def vector_relative(vector: np.array, basis: np.array) -> np.array:
    # Changes basis of given vector from "absolute" basis {(1, 0, 0), (0, 1, 0), (0, 0, 1)} to given basis
    return np.linalg.solve(np.transpose(basis), vector)


# Changes basis of given from given basis to "absolute" one (see above)
def vector_absolute(rel: np.array, basis: np.array) -> np.array:
    return np.add.reduce([np.multiply(rel[i], basis[i]) for i in range(len(rel))])


def generate_lut(colormap: str, discrete: bool) -> np.array:
    if colormap == 'rainbow':
        if discrete:
            return np.concatenate((
                np.repeat(np.array(((0, 0, 127, 255),)), 16, axis=0),
                np.repeat(np.array(((0, 0, 255, 255),)), 32, axis=0),
                np.repeat(np.array(((133, 206, 235, 255),)), 32, axis=0),
                np.repeat(np.array(((0, 255, 255, 255),)), 32, axis=0),
                np.repeat(np.array(((0, 255, 0, 255),)), 32, axis=0),
                np.repeat(np.array(((255, 255, 0, 255),)), 32, axis=0),
                np.repeat(np.array(((255, 153, 19, 255),)), 32, axis=0),
                np.repeat(np.array(((255, 0, 0, 255),)), 48, axis=0),
            ), axis=0)
        else:
            return np.concatenate((
                np.repeat(np.array(((0, 0, 127, 255),)), 16, axis=0),
                np.linspace((0, 0, 127, 255), (0, 0, 255, 255), 32),
                np.linspace((0, 0, 255, 255), (133, 206, 235, 255), 32),
                np.linspace((133, 206, 235, 255), (0, 255, 255, 255), 32),
                np.linspace((0, 255, 255, 255), (0, 255, 0, 255), 32),
                np.linspace((0, 255, 0, 255), (255, 255, 0, 255), 32),
                np.linspace((255, 255, 0, 255), (255, 153, 19, 255), 32),
                np.linspace((255, 153, 19, 255), (255, 0, 0, 255), 32),
                np.repeat(np.array(((255, 0, 0, 255),)), 16, axis=0)
            ), axis=0)
    elif colormap == 'gray':
        if discrete:
            return np.concatenate((
                np.repeat(np.array(((0, 0, 0, 255),)), 16, axis=0),
                np.repeat(np.array(((32, 32, 32, 255),)), 32, axis=0),
                np.repeat(np.array(((64, 64, 64, 255),)), 32, axis=0),
                np.repeat(np.array(((96, 96, 96, 255),)), 32, axis=0),
                np.repeat(np.array(((128, 128, 128, 255),)), 32, axis=0),
                np.repeat(np.array(((160, 160, 160, 255),)), 32, axis=0),
                np.repeat(np.array(((192, 192, 192, 255),)), 32, axis=0),
                np.repeat(np.array(((224, 224, 224, 255),)), 48, axis=0),
            ), axis=0)
        else:
            return np.linspace((0, 0, 0, 255), (255, 255, 255, 255), 256)


def color_bar(data: dict, obj: Module, discrete: bool, vector: bool = False) -> None:
    if vector:
        lut_mgr = obj.module_manager.vector_lut_manager
    else:
        lut_mgr = obj.module_manager.scalar_lut_manager

    lut_mgr.data_range = data['colorbar']['scale_range']

    lut_mgr.show_scalar_bar = True
    lut_mgr.lut.table = generate_lut(data['colormap'], discrete)

    if vector:
        cb = mlab.vectorbar(obj, orientation=data['colorbar_orientation'], title=data['colormap_title'],
                            nb_labels=9, nb_colors=(8 if discrete else None),
                            label_fmt='%.1f')
    else:
        cb = mlab.scalarbar(obj, orientation=data['colorbar_orientation'], title=data['colormap_title'],
                            nb_labels=9, nb_colors=(8 if discrete else None),
                            label_fmt='%.1f')
    cb.scalar_bar.unconstrained_font_size = True
    cb.title_text_property.font_size = data['colorbar_font_size'] if 'colorbar_font_size' in data else 18
    cb.title_text_property.bold = False
    cb.title_text_property.italic = False
    cb.label_text_property.font_size = data['colorbar_font_size'] if 'colorbar_font_size' in data else 18
    cb.label_text_property.bold = False
    cb.label_text_property.italic = False

    lut_mgr.scalar_bar.bar_ratio = 0.1
    if data['colorbar_orientation'] == 'vertical':
        lut_mgr.scalar_bar_representation.position = (0.8, 0.1)


def main_plot_script(scene, data: dict) -> list:
    actors = []
    try:
        # coordinate_axis = data['coordinate_axis'] if 'coordinate_axis' in data else [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
        coordinate_axis = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]])
        if data['camera_view'] == 'iso':
            scene.camera.position = np.sum(coordinate_axis, axis=0)
            scene.camera.view_up = coordinate_axis[2]
        elif data['camera_view'] == '-iso':
            scene.camera.position = np.negative(np.sum(coordinate_axis, axis=0))
            scene.camera.view_up = coordinate_axis[2]
        elif data['camera_view'] == '+x':
            scene.camera.position = coordinate_axis[0]
            scene.camera.view_up = coordinate_axis[2]
        elif data['camera_view'] == '-x':
            scene.camera.position = np.negative(coordinate_axis[0])
            scene.camera.view_up = coordinate_axis[2]
        elif data['camera_view'] == '+y':
            scene.camera.position = coordinate_axis[1]
            scene.camera.view_up = coordinate_axis[0]
        elif data['camera_view'] == '-y':
            scene.camera.position = np.negative(coordinate_axis[1])
            scene.camera.view_up = coordinate_axis[0]
        elif data['camera_view'] == '+z':
            scene.camera.position = coordinate_axis[2]
            scene.camera.view_up = coordinate_axis[1]
        elif data['camera_view'] == '-z':
            scene.camera.position = np.negative(coordinate_axis[2])
            scene.camera.view_up = coordinate_axis[1]
        else:
            raise ValueError('Unknown camera view: ' + data['camera_view'])

        if 'camera_rotate' in data:
            if 'yaw' in data['camera_rotate']:
                mlab.yaw(data['camera_rotate']['yaw'])
            if 'pitch' in data['camera_rotate']:
                mlab.pitch(data['camera_rotate']['pitch'])
            if 'roll' in data['camera_rotate']:
                mlab.roll(data['camera_rotate']['roll'])

        if data['projection_view'] == 'parallel':
            scene.parallel_projection = True
        elif data['projection_view'] == 'perspective':
            scene.parallel_projection = False
        else:
            raise ValueError('Unknown projection view: ' + data['projection_view'])

        ug = tvtk.UnstructuredGrid(points=data['nodes'])
        ug.set_cells(tvtk.Tetra().cell_type, data['elements'])

        scalars = None
        inp = None
        if data['var_type'] == 'element' and data['data_type'] == 'scalar' and data['colormap_shading'] != 'elemental':
            var_type, data_type = 'nodal', 'scalar'

            scalars = [0] * len(data['nodes'])
            scalars_cnt = [0] * len(data['nodes'])
            for i, el in enumerate(data['elements']):
                for j in range(4):
                    scalars[el[j]] += data['variable'][i]
                    scalars_cnt[el[j]] += 1

            for i in range(len(scalars)):
                scalars[i] /= scalars_cnt[i]

            ug.point_data.scalars = scalars
            ug.point_data.scalars.name = 'value'
        elif data['var_type'] != 'none':
            if data['var_type'] == 'nodal' and data['colormap_shading'] == 'elemental':
                raise ValueError('Can\'t use nodal var type with colormap_shading elemental')

            var_type, data_type = data['var_type'], data['data_type']

            if data_type == 'scalar':
                scalars = data['variable']
                if var_type == 'nodal':
                    ug.point_data.scalars = scalars
                    ug.point_data.scalars.name = 'value'
                elif var_type == 'element':
                    ug.cell_data.scalars = scalars
                    ug.cell_data.scalars.name = 'value'
            elif data_type == 'vector':
                inp = data['variable']
                if var_type == 'nodal':
                    ug.point_data.vectors = inp
                    ug.point_data.vectors.name = 'value'
                elif var_type == 'element':
                    ug.cell_data.vectors = inp
                    ug.cell_data.vectors.name = 'value'
            else:
                raise ValueError('Unknown data_type: ' + data_type)
        else:
            var_type, data_type = 'none', 'none'

        if var_type not in ['nodal', 'element', 'none']:
            raise ValueError('Unknown var type: ' + var_type)

        if data_type not in ['scalar', 'vector', 'none']:
            raise ValueError('Unknown data type: ' + data_type)

        ds = mlab.pipeline.add_dataset(ug)

        if data['mesh_view'] == 'wireframe':
            main_representation = 'wireframe'
        elif data['mesh_view'] in ['surface', 'surface_with_wireframe']:
            main_representation = 'surface'
        elif data['mesh_view'] == 'none':
            main_representation = 'none'
        else:
            raise ValueError('Unknown mesh view: ' + data['mesh_view'])

        if var_type == 'none' or (data_type == 'vector' and main_representation != 'none'):
            if var_type == 'none' and main_representation == 'none':
                raise ValueError('No main representation for var_type none')

            if data['slice_view']['status']:
                plane = mlab.pipeline.scalar_cut_plane(
                    ds, view_controls=False,
                    vmin=data['colorbar']['scale_min'], vmax=data['colorbar']['scale_max']
                )
                plane.implicit_plane.plane.origin = vector_absolute(data['slice_view']['point'], coordinate_axis)
                plane.implicit_plane.plane.normal = vector_absolute(data['slice_view']['vector'], coordinate_axis)
                plane.actor.property.representation = main_representation
                plane.actor.mapper.scalar_visibility = False
                if main_representation == 'surface':
                    plane.actor.property.color = (0.984, 0.847, 0.235)
                elif main_representation == 'wireframe':
                    plane.actor.property.line_width = 0.5
                    plane.actor.property.color = (0.2, 0.2, 0.698)
            else:
                surf = mlab.pipeline.surface(ds, representation=main_representation)
                surf.actor.mapper.scalar_visibility = False
                if main_representation == 'surface':
                    surf.actor.property.color = (0.984, 0.847, 0.235)
                elif main_representation == 'wireframe':
                    surf.actor.property.line_width = 0.5
                    surf.actor.property.color = (0.2, 0.2, 0.698)

        if data_type == 'scalar':
            if main_representation == 'none':
                raise ValueError('No mesh view for scalar plot')

            step_contour = data['colorbar']['scale_division']
            contours = data['colorbar']['scale_marks']

            if data['colormap_shading'] == 'solid_bands':
                colors = set()
                for v in scalars:
                    if v < data['colorbar']['scale_min']:
                        colors.add(0)
                    elif v > data['colorbar']['scale_max']:
                        colors.add(7)
                    else:
                        for i in range(8):
                            cur_min = data['colorbar']['scale_min'] + i * step_contour
                            cur_max = data['colorbar']['scale_min'] + (i + 1) * step_contour

                            if cur_min <= v <= cur_max:
                                colors.add(i)
                                break

                if len(colors) < 2:
                    colormap_shading = 'shaded'
                else:
                    colormap_shading = 'solid_bands'

                discrete_colorbar = True
            else:
                colormap_shading = data['colormap_shading']
                discrete_colorbar = False

            if data['slice_view']['status']:
                slice_point = vector_absolute(data['slice_view']['point'], coordinate_axis)
                slice_vector = vector_absolute(data['slice_view']['vector'], coordinate_axis)

                plane = mlab.pipeline.scalar_cut_plane(
                    ds, view_controls=False,
                    vmin=data['colorbar']['scale_min'], vmax=data['colorbar']['scale_max']
                )
                plane.implicit_plane.plane.origin = slice_point
                plane.implicit_plane.plane.normal = slice_vector
                plane.actor.property.representation = main_representation

                cut_plane = tvtk.Plane()
                cut_plane.origin = slice_point
                cut_plane.normal = slice_vector

                if var_type == 'nodal' and colormap_shading == 'solid_bands':
                    plane.enable_contours = True
                    plane.contour.contours = contours
                    plane.contour.filled_contours = True

                    color_bar(data, plane, discrete=discrete_colorbar)
                elif var_type == 'element' or colormap_shading in ['shaded', 'shaded_with_isolines']:
                    if var_type == 'nodal' and colormap_shading == 'shaded_with_isolines':
                        isolines = mlab.pipeline.scalar_cut_plane(
                            ds, view_controls=False,
                            vmin=data['colorbar']['scale_min'], vmax=data['colorbar']['scale_max']
                        )
                        isolines.implicit_plane.plane.origin = slice_point
                        isolines.implicit_plane.plane.normal = slice_vector

                        isolines.enable_contours = True
                        isolines.contour.contours = contours
                        isolines.contour.filled_contours = False
                        isolines.actor.mapper.scalar_visibility = False
                        isolines.actor.property.color = (0, 0, 0)

                    color_bar(data, plane, discrete=discrete_colorbar)
                else:
                    raise ValueError('Unexpected var_type or colormap_shading (' + var_type + ', ' +
                                     colormap_shading)

                if data['slice_view']['contour']:
                    gf = tvtk.GeometryFilter()
                    gf.set_input_data(ug)
                    gf.update()

                    cut = tvtk.Cutter()
                    cut.set_input_data(gf.output)
                    cut.cut_function = cut_plane
                    cut.update()

                    pdm = tvtk.PolyDataMapper()
                    pdm.set_input_data(cut.output)
                    pdm.scalar_visibility = False
                    pdm.update()

                    outer = tvtk.Actor(mapper=pdm)
                    outer.property.color = (0, 0, 0)
                    outer.property.line_width = 2.0
                    scene.add_actor(outer)

                    actors.append(outer)
            elif var_type != 'none':
                if var_type == 'nodal' and colormap_shading == 'solid_bands':
                    surf = mlab.pipeline.contour_surface(
                        ds, contours=contours,
                        vmin=data['colorbar']['scale_min'], vmax=data['colorbar']['scale_max']
                    )
                    surf.actor.property.representation = main_representation
                    surf.contour.filled_contours = True

                    color_bar(data, surf, discrete=discrete_colorbar)
                elif var_type == 'element' or colormap_shading in ['shaded', 'shaded_with_isolines', 'elemental']:
                    surf = mlab.pipeline.surface(
                        ds, representation=main_representation,
                        vmin=data['colorbar']['scale_min'], vmax=data['colorbar']['scale_max']
                    )

                    if colormap_shading == 'shaded_with_isolines':
                        cf = tvtk.ContourFilter()
                        cf.set_input_data(ug)

                        i = 0
                        cur_contour = data['colorbar']['scale_min'] + step_contour
                        while cur_contour < data['colorbar']['scale_max']:
                            cf.set_value(i, cur_contour)
                            i += 1
                            cur_contour += step_contour

                        cf.update()

                        stp = tvtk.Stripper()
                        stp.set_input_data(cf.output)
                        stp.update()

                        edg = tvtk.FeatureEdges()
                        edg.set_input_data(stp.output)
                        edg.boundary_edges = True
                        edg.manifold_edges = False
                        edg.non_manifold_edges = False
                        edg.feature_edges = False
                        edg.update()

                        pdm = tvtk.PolyDataMapper()
                        pdm.set_input_data(edg.post_config)
                        pdm.scalar_visibility = False
                        pdm.update()

                        isolines = tvtk.Actor(mapper=pdm)
                        isolines.property.color = (0, 0, 0)
                        isolines.property.line_width = 2.0
                        scene.add_actor(isolines)

                        actors.append(isolines)

                    color_bar(data, surf, discrete=discrete_colorbar)
                else:
                    raise ValueError('Unknown colormap_shading: ' + colormap_shading)
        elif data_type == 'vector':
            if data['vector_scale']:
                scale_mode = 'vector'
            else:
                scale_mode = 'none'

            if var_type == 'element':
                points = []
                values = []

                for i, el in enumerate(data['elements']):
                    mid = np.array((0, 0, 0))
                    for j in range(4):
                        mid = np.add(mid, data['nodes'][el[j]])
                    mid = np.divide(mid, 4)

                    points.append(mid)
                    values.append(inp[i])

                points = np.array(points)
                values = np.array(values)

                pd = tvtk.PolyData(points=points)
                pd.point_data.vectors = values
                pd.point_data.vectors.name = 'value'

                if data['slice_view']['status']:
                    d3d = tvtk.Delaunay3D()
                    d3d.set_input_data(pd)
                    d3d.update()

                    vector_input = mlab.pipeline.add_dataset(d3d)
                else:
                    vector_input = mlab.pipeline.add_dataset(pd)
            else:
                vector_input = ds

            if data['slice_view']['status']:
                inp = mlab.pipeline.vector_cut_plane(
                    vector_input, view_controls=False,
                    mode=data['vector_glyph'], scale_mode=scale_mode,
                    scale_factor=100.0,
                    vmin=data['colorbar']['scale_min'], vmax=data['colorbar']['scale_max'],
                )
                inp.implicit_plane.plane.origin = vector_absolute(data['slice_view']['point'], coordinate_axis)
                inp.implicit_plane.plane.normal = vector_absolute(data['slice_view']['vector'], coordinate_axis)
            else:
                inp = mlab.pipeline.vectors(
                    vector_input, mode=data['vector_glyph'], scale_mode=scale_mode,
                    scale_factor=100.0,
                    vmin=data['colorbar']['scale_min'], vmax=data['colorbar']['scale_max']
                )

            inp.actor.property.line_width = 1.0

            color_bar(data, inp, discrete=False, vector=True)

        if data['mesh_view'] == 'surface_with_wireframe':
            cf = tvtk.GeometryFilter()
            cf.set_input_data(ug)
            gs = mlab.pipeline.add_dataset(cf)

            start_x, end_x, yi, yf, zi, zf = ds.data.bounds
            delta = 0.1

            wf = mlab.pipeline.surface(
                gs,
                extent=(start_x - delta, end_x + delta, yi - delta, yf + delta, zi - delta, zf + delta),
                representation='wireframe'
            )
            wf.actor.mapper.scalar_visibility = False
            wf.actor.property.color = (0.2, 0.2, 0.698)
            wf.actor.property.line_width = 0.5

        def always_on_top(mapper: tvtk.PolyDataMapper) -> None:
            mapper.resolve_coincident_topology = 'polygon_offset'

            # noinspection PyProtectedMember
            vtk_obj = mapper._vtk_obj
            vtk_obj.SetRelativeCoincidentTopologyLineOffsetParameters(0, -66000)
            vtk_obj.SetRelativeCoincidentTopologyPolygonOffsetParameters(0, -66000)
            vtk_obj.SetRelativeCoincidentTopologyPointOffsetParameter(-66000)

        def draw_line(point1: tuple,
                      point2: tuple,
                      line_width: float,
                      color: tuple[float, float, float],
                      on_top: bool
                      ) -> None:
            line_src = tvtk.LineSource(
                point1=vector_absolute(point1, coordinate_axis),
                point2=vector_absolute(point2, coordinate_axis)
            )

            line_mp = tvtk.PolyDataMapper()
            line_mp.set_input_data(line_src.output)
            if on_top:
                always_on_top(line_mp)
            line_src.update()

            line = tvtk.Actor(mapper=line_mp)
            line.property.line_width = line_width
            line.property.color = color
            scene.add_actor(line)

            actors.append(line)

        if 'axis_view' in data and data['axis_view']['status']:
            delta = 30.0

            start_x, end_x = data['axis_view']['bounds']
            start_x -= delta
            end_x += delta

            center = vector_relative(data['axis_view']['center'], coordinate_axis)

            x = start_x
            while x < end_x:
                for stroke_width in [50, 10]:

                    draw_line(point1=(x, center[1], center[2]),
                              point2=(x + stroke_width, center[1], center[2]),
                              line_width=8,
                              color=(0.3, 0, 0),
                              on_top=True)

                    x += stroke_width + 10

        if 'slice_contours' in data:
            for slice_contour in data['slice_contours']:
                cut_plane = tvtk.Plane()
                cut_plane.origin = vector_absolute(slice_contour['point'], coordinate_axis)
                cut_plane.normal = vector_absolute(slice_contour['vector'], coordinate_axis)

                gf = tvtk.GeometryFilter()
                gf.set_input_data(ug)
                gf.update()

                cut = tvtk.Cutter()
                cut.set_input_data(gf.output)
                cut.cut_function = cut_plane
                cut.update()

                pdm = tvtk.PolyDataMapper()
                pdm.set_input_data(cut.output)
                pdm.scalar_visibility = False
                pdm.update()

                outer = tvtk.Actor(mapper=pdm)
                outer.property.color = (0, 0, 0)
                outer.property.line_width = 2.0
                scene.add_actor(outer)

                actors.append(outer)

        mlab.title(data['title'], size=0.3, height=0.9)

        # logo start
        if 'logo' in data and data['logo']['file'] is not None:
            reader = tvtk.PNGReader()
            reader.file_name = data['logo']['file']
            reader.update()

            resize = tvtk.ImageResize()
            resize.set_input_data(reader.output)
            resize.output_dimensions = (data['logo']['size'][0], data['logo']['size'][1], 1)
            resize.update()

            img_mp = tvtk.ImageMapper()
            img_mp.set_input_data(resize.output)
            img_mp.color_window = 255
            img_mp.color_level = 127.5

            img = tvtk.Actor2D()
            img.mapper = img_mp
            img.position = tuple(data['logo']['position'])

            scene.add_actor(img)

            actors.append(img)

        # logo end

        # annotations start

        def add_text(coords: tuple) -> None:
            txt = tvtk.TextActor()
            txt.input = ann['text']
            if len(coords) == 3:
                txt.position_coordinate.coordinate_system = 'world'
                txt.position_coordinate.value = vector_absolute(coords, coordinate_axis)
            elif len(coords) == 2:
                txt.position_coordinate.value = (coords[0], coords[1], 0)
            else:
                raise ValueError("Expected 'coords' to be tuple of 2 or 3 coordinates")
            txt.text_property.justification = ann['text_h_align']
            txt.text_property.vertical_justification = ann['text_v_align']
            txt.text_property.color = tuple(ann['text_color'])
            txt.text_property.font_size = ann['font_height']
            txt.text_property.font_family = 'arial'
            if ann['font_style'] == 'bold_italic':
                txt.text_property.bold = True
                txt.text_property.italic = True
            elif ann['font_style'] == 'bold':
                txt.text_property.bold = True
                txt.text_property.italic = False
            elif ann['font_style'] == 'italic':
                txt.text_property.bold = False
                txt.text_property.italic = True
            elif ann['font_style'] == 'normal':
                txt.text_property.bold = False
                txt.text_property.italic = False
            else:
                raise ValueError('Unknown font style for annotation: ' + ann['font_style'])
            txt.text_property.shadow = False
            if ann['border']:
                txt.text_property.frame = True
                txt.text_property.frame_color = ann['border_color']
                txt.text_property.frame_width = 2
                txt.text_property.line_offset = 5
            else:
                txt.text_property.frame = False
            if ann['border_fill']:
                txt.text_property.background_opacity = 1.0
                txt.text_property.background_color = ann['border_fill_color']
            else:
                txt.text_property.background_opacity = 0.0
            scene.add_actor(txt)

            actors.append(txt)

        def add_line(point1: tuple, point2: tuple) -> None:
            draw_line(point1, point2, ann['lines_width'], ann['lines_color'], ann['lines_always_visible'])

        def add_point(coords: tuple) -> None:
            sphere_src = tvtk.SphereSource(center=vector_absolute(coords, coordinate_axis), radius=ann['point_radius'])
            sphere_mp = tvtk.PolyDataMapper()
            sphere_mp.set_input_data(sphere_src.output)
            if ann['point_always_visible']:
                always_on_top(sphere_mp)
            sphere_src.update()

            sphere = tvtk.Actor(mapper=sphere_mp)
            sphere.property.color = ann['point_color']
            scene.add_actor(sphere)

            actors.append(sphere)

        def add_dimension_line(pts_rel: tuple, radius: float) -> None:
            add_line(pts_rel[0], pts_rel[1])

            pts = tuple(vector_absolute(pt, coordinate_axis) for pt in pts_rel)

            vec = np.array([pts[0][cc] - pts[1][cc] for cc in range(3)])
            vc = [[vec[cc], -vec[cc]] for cc in range(3)]

            vec_sph = vec / np.sqrt(np.sum(vec ** 2)) * radius
            vc_sph = [[vec_sph[cc], -vec_sph[cc]] for cc in range(3)]
            pc = [[p[cc] - vc_sph[cc][k] for k, p in enumerate(pts)] for cc in range(3)]

            vinp = mlab.pipeline.vector_scatter(pc[0], pc[1], pc[2], vc[0], vc[1], vc[2])

            if ann['arrow_type'] == '3d':
                glyph_mode = 'arrow'
            elif ann['arrow_type'] == '2d':
                glyph_mode = '2darrow'
            else:
                raise ValueError('Undefined arrow_type: ' + ann['arrow_type'])

            glyphs = mlab.pipeline.vectors(vinp, mode=glyph_mode, scale_mode='none', scale_factor=100.0)
            glyphs.glyph.glyph_source.glyph_position = 'head'
            if glyph_mode == 'arrow':
                glyphs.glyph.glyph_source.glyph_source.shaft_radius = 0.0
                glyphs.glyph.glyph_source.glyph_source.tip_length = ann['arrow_length']
            else:
                glyphs.glyph.glyph_source.glyph_source.scale = ann['arrow_length']
                glyphs.glyph.glyph_source.glyph_source.center = np.array((-ann['arrow_length'] / 2, 0., 0.))
            glyphs.actor.property.line_width = ann['lines_width']
            glyphs.actor.property.color = ann['lines_color']
            glyphs.glyph.color_mode = 'no_coloring'
            if ann['lines_always_visible']:
                always_on_top(glyphs.actor.mapper)

        if 'annotations' in data:
            for ann in data['annotations']:
                if ann['type'] == 'text':
                    add_text(ann['text_2d_coordinates'])
                elif ann['type'] == 'annotation':
                    add_point(ann['point_3d_coordinates'])
                    add_line(ann['point_3d_coordinates'], ann['text_3d_coordinates'])
                    add_text(ann['text_3d_coordinates'])
                elif ann['type'] == 'lines':
                    for i in range(len(ann['points_3d_coordinates']) - 1):
                        add_line(ann['points_3d_coordinates'][i], ann['points_3d_coordinates'][i + 1])

                    if ann['points_show']:
                        for point in ann['points_3d_coordinates']:
                            add_point(point)
                elif ann['type'] == 'dimension_3d':
                    for point in ann['points_3d_coordinates']:
                        add_point(point)

                    add_dimension_line(ann['points_3d_coordinates'], ann['point_radius'])

                    midpoint = tuple(
                        [(ann['points_3d_coordinates'][0][cc] + ann['points_3d_coordinates'][1][cc]) / 2 for cc in
                         range(3)]
                    )
                    add_text(midpoint)
                elif ann['type'] == 'dimension_parallel':
                    p3d = ann['points_3d_coordinates']
                    for point in p3d:
                        add_point(point)

                    t3d = ann['text_3d_coordinates']

                    dim_axis = ['x', 'y', 'z'].index(ann['dimension_line_parallel_to'])
                    ext_axis = ['x', 'y', 'z'].index(ann['extension_lines_parallel_to'])

                    first_axis = -1
                    for i in range(3):
                        if i not in [dim_axis, ext_axis]:
                            first_axis = i
                            break

                    pt1 = list(p3d[0])
                    pt2 = list(p3d[1])

                    margin_coeff = 1.0
                    ext_margin = margin_coeff * ann['font_height']
                    for axis in [first_axis, ext_axis]:
                        opt1, opt2 = pt1.copy(), pt2.copy()
                        pt1[axis] = pt2[axis] = t3d[axis]

                        if axis == ext_axis:
                            ept1 = pt1.copy()
                            if ept1[axis] > opt1[axis]:
                                ept1[axis] += ext_margin
                            elif ept1[axis] < opt1[axis]:
                                ept1[axis] -= ext_margin

                            ept2 = pt2.copy()
                            if ept2[axis] > opt2[axis]:
                                ept2[axis] += ext_margin
                            elif ept2[axis] < opt2[axis]:
                                ept2[axis] -= ext_margin
                            add_line(tuple(opt1), tuple(ept1))
                            add_line(tuple(opt2), tuple(ept2))
                        else:
                            add_line(tuple(opt1), tuple(pt1))
                            add_line(tuple(opt2), tuple(pt2))

                    add_dimension_line((tuple(pt1), tuple(pt2)), 0.0)

                    add_text(ann['text_3d_coordinates'])

                    # add_line(ann['text_3d_coordinates'], tuple(pt1))

                    """
                    vec_diff_half = np.array([p3d[0][cc] - p3d[1][cc] for cc in range(3)]) / 2
                    w1 = np.array(t3d) + vec_diff_half
                    w2 = np.array(t3d) - vec_diff_half
    
                    add_dimension_line((w1, w2), 0.0)
    
                    axis_order = [-1, -1, -1]
                    axis_order[2] = ['x', 'y', 'z'].index(ann['extension_lines_parallel_to'])
                    axis_order[1] = ['x', 'y', 'z'].index(ann['dimension_line_parallel_to'])
                    for i in range(3):
                        if i not in axis_order:
                            axis_order[0] = i
                            break
    
                    pt1 = list(p3d[0])
                    pt2 = list(p3d[1])
                    for i in axis_order:
                        opt1, opt2 = pt1.copy(), pt2.copy()
                        pt1[i] = w1[i]
                        pt2[i] = w2[i]
    
                        add_line(tuple(opt1), tuple(pt1))
                        add_line(tuple(opt2), tuple(pt2))
                    """

        # annotations end

        scene.reset_zoom()
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        mlab.points3d([0], [0], [0]).remove()
        mlab.title(traceback.format_exc(), size=0.1, height=0.0)
    return actors


def mayavi_worker(fig, scene, _view, img_param: dict):
    try:
        mlab.view(azimuth=_view[0], elevation=_view[1], distance=_view[2], focalpoint=_view[3])
        actors = main_plot_script(scene, img_param)
        mlab.savefig(img_param['file_server_abs_file_path'])
        mlab.clf()
        for actor in actors:
            fig.scene.remove_actor(actor)
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise RuntimeError("FAILED Mayavi code")


class MayaviWorker(Process):
    """A thread that runs sequence of simulation utils according to input table of utils"""

    def __init__(self, worker_id: int, task_queue: Queue, status: dict, semaphore: Semaphore):
        """Initialize the thread"""
        super().__init__()

        self.worker_id: int = worker_id
        self.task_queue: Queue = task_queue
        self.status: dict = status
        self.semaphore: Semaphore = semaphore

        self.pvid: int = 0
        self.eo: int = 0
        self.eo_last: int = 0
        
        self.time_start = time.monotonic()

    def run(self):
        LOGGER.info(f"{self.log_id} started.")
        print(f"{self.log_id} started.")

        p = psutil.Process()
        if psutil.LINUX:
            p.nice(10)
            print(f"CPU Priority set to {p.nice()} on Linux")
        elif psutil.WINDOWS:
            p.nice(psutil.IDLE_PRIORITY_CLASS)
            print(f"CPU Priority set to {p.nice()} on Windows")

        fig: Scene
        scene: TVTKScene
        default_view: tuple[float, float, float, list[float, float, float]]

        fig, scene, default_view = self.initialize_mayavi_scene()

        while True:
            try:
                task_id, img_param, self.pvid, self.eo, self.eo_last = "", {}, 0, 0, 0

                task_id, img_param, self.pvid, self.eo, self.eo_last = self.task_queue.get()

                print(f"{self.log_id} Queue feed data")

                if self.pvid == 0:
                    print(f"{self.log_id} received shutdown signal.")
                    break

                print(f"{self.log_id} received a task")

                # Process the task
                try:
                    self.time_start = time.monotonic()
                    mayavi_worker(fig, scene, default_view, img_param)
                    self.status[task_id] = 'completed'
                except RuntimeError:
                    self.status[task_id] = 'error'
                finally:
                    self.semaphore.release()  # Release the semaphore to indicate worker is available
                    LOGGER.info(f"{self.log_id} Released 1 slot in Semaphore")

            except Exception as _err:
                print(f"{self.log_id} {type(_err).__name__}: {_err}")
                break
        LOGGER.info(f"{self.log_id} stopped.")
        print(f"{self.log_id} stopped.")

    def initialize_mayavi_scene(self) -> tuple[Scene, TVTKScene, tuple[float, float, float, list[float, float, float]]]:
        try:
            mlab.options.offscreen = True
            fig = mlab.figure(size=(3000, 3000), bgcolor=(1.0, 1.0, 1.0), fgcolor=(0.0, 0.0, 0.0))
            scene = mlab.gcf().scene
            default_view = mlab.view()
            return fig, scene, default_view
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise
    
    @property
    def log_id(self):
        duration = str(round(time.monotonic() - self.time_start, 2))
        return f"{self.task_id_name} Duration {duration}s"

    @property
    def task_id_name(self) -> str:
        return f"[{self.pvid}][{self.eo}/{self.eo_last}] Mayavi Worker #{self.worker_id}"
