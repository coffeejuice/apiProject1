import logging
import traceback
import json
import locale
import math
from multiprocessing import Queue, Semaphore, Manager
from threading import Thread
import os
import time
from contextlib import contextmanager
from datetime import datetime

import numpy as np
import pandas as pd
import smbclient
import win32com.client
from scipy import stats
from scipy.stats._mstats_basic import DescribeResult
from smbclient import shutil as smb_shutil

from forgelab.common.common_funcs import is_samba_path, log_error
from forgelab.common.file_operations import remove_content_of_local_dir
from forgelab.common.queries import query_process_versions, query_server_pre_main, query_post_operations, \
    query_type_id_nnn, query_processes
from forgelab.common.read_deform_keyfile import read_deform_keyfile, VARIABLES
from forgelab.config import config
from forgelab.srv_post.gen_ppt import DocumentPPT


LOGGER = logging.getLogger(__name__)


@contextmanager
def locale_block(local_name: str):
    lc_var: int = locale.LC_ALL
    org_local = locale.getlocale()
    try:
        yield locale.setlocale(lc_var, local_name)
    finally:
        locale.setlocale(lc_var, org_local)


class PostWorker(Thread):
    """A thread that runs sequence of simulation utils according to input table of utils"""

    def __init__(self, worker_id: int,
                 task_queue: Queue, semaphore: Semaphore,
                 mayavi_queue: Queue, mayavi_manager: Manager, mayavi_status: dict, mayavi_semaphore: Semaphore):
        """Initialize the thread"""
        super().__init__()

        self.worker_id: int = worker_id
        self.input_queue: Queue = task_queue
        self.semaphore: Semaphore = semaphore

        self.mayavi_queue: Queue = mayavi_queue
        self.mayavi_manager: Manager = mayavi_manager
        self.mayavi_status: dict = mayavi_status
        self.mayavi_semaphore: Semaphore = mayavi_semaphore

        self.pvid: int = 0
        self.eo: int = 0
        self.eo_last: int = 0
        self.eid: int = 0

        self.variable_names: list = [
            'surface',
            'nodal_scalar_temperature',
            'max_temperature_operation',
            'temperature_change_operation',
            'strain_operation',
            'strain_heat',
            'strain_total_x_scalar',
            'strain_total_y_scalar',
            'strain_total_z_scalar',
            'ingot_axis_x',
            'ingot_axis_z',
        ]

        self.variants: list = list(range(12))

        self.param: dict = {}

        self.post_param: dict = {}

        self.time_start: float = time.monotonic()

    def run(self):
        LOGGER.info(f"{self.log_id} started.")
        while True:
            try:
                self.pvid, self.eo, self.eid = 0, 0, 0
                self.pvid, self.eo, self.eid = self.input_queue.get()

                if self.pvid == 0:
                    LOGGER.info(f"{self.log_id} received shutdown signal.")
                    break

                LOGGER.info(f"{self.log_id} received a task")

                self._silent_worker()
                self.semaphore.release()

                LOGGER.info(f"{self.log_id} Released 1 slot in Post Semaphore")

            except Exception as _err:
                log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
                break
        LOGGER.info(f"{self.log_id} stopped.")


    def _silent_worker(self):
        """Run the thread"""
        self.time_start = time.monotonic()

        self.assert_output_variable_names()

        try:
            self.param = {
                'project': query_process_versions(self.pvid),
                'table': query_server_pre_main(self.pvid),
                'post': query_post_operations(self.pvid)}

            type_id = self.param['table'][self.eo]['type_id']
            operation_id = self.param['table'][self.eo]['operation_id']

            self.param['type_id_nnn'] = query_type_id_nnn(type_id, operation_id)
            self.param['process'] = query_processes(self.param['project']['process_id'])

            self.param['operation'] = self._import_parameters_json_from_nas()

            self.post_param = self.generate_post_param()

            # ----------------------------------------------------

            assert self.post_param['material_btt'] > 20.0

            # ----------------------------------------------------

            self.log_start()

            # ----------------------------------------------------

            if not os.path.exists(self.post_param['local_operation_dir']):
                os.makedirs(self.post_param['local_operation_dir'])

            self.create_new_dir_or_clean_existing_dir(self.post_param['local_ppt_dir'])
            self.create_new_dir_or_clean_existing_dir(self.post_param['local_images_dir'])

            # --------------------- GENERATE IMAGES ------------------------------------

            key_file_data = read_deform_keyfile(self.post_param['remote_input_file_path'])
            ppt_param = self.ppt_parameters(key_file_data)

            LOGGER.debug(f"{self.log_id} Start generating Images")

            target_task_ids: list = self.mayavi_manager.list()  # Shared list to track target tasks
            for variable_name in self.variable_names:

                variable_param = self.variable_parameters(ppt_param.copy(), key_file_data, variable_name)

                for variant_index in self.variants:

                    task_id = f"{self.pvid}_{self.eo}_{variable_name}_{variant_index}"
                    img_param = self.img_parameters(variable_param.copy(), variable_name, variant_index)

                    self.mayavi_semaphore.acquire()

                    self.mayavi_queue.put((task_id, img_param, self.pvid, self.eo, self.eo_last))
                    self.mayavi_status[task_id] = 'pending'
                    target_task_ids.append(task_id)

            # Wait for all Images
            while target_task_ids:
                finished_tasks: set = {task_id for task_id in target_task_ids
                                       if self.mayavi_status.get(task_id) == 'completed'}
                if finished_tasks:
                    for task_id in finished_tasks:
                        target_task_ids.remove(task_id)
                        self.mayavi_status.pop(task_id, None)
                time.sleep(1)  # Check every second

            # -------------------- GENERATE IMAGES, PPT, PDF ---------------------------

            self.generate_ppt()
            self.generate_pdf()

            # ------------------------------------- CLEAN REMOTE DIR ------------------------------------------

            self.create_new_dir_or_clean_existing_dir(self.post_param['remote_images_dir'])
            self.create_new_dir_or_clean_existing_dir(self.post_param['remote_ppt_dir'])

            self.copy_images_to_remote_file_server()
            self.copy_ppt_to_remote_file_server()
            self.copy_pdf_to_remote_file_server()

            # ------------------------------------- LOGGER & QUERY FINISH POST --------------------------------

            self._query_set_post_status_finished()

            LOGGER.info(
                f"{self.log_id} PPT Finished"
                f" Duration {self._duration_str()}"
                f" Output dir '{self.post_param['remote_operation_dir']}'")

        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            self._silent_query_set_post_status_error()

    def generate_post_param(self):
        material_btt = self.param['process']['material_btt']
        local_operation_dir = self._local_operation_path()
        remote_operation_dir = self._remote_operation_path()
        ppt_filename = self._ppt_file_name()
        local_ppt_dir = os.path.join(local_operation_dir, 'pptx')
        remote_ppt_dir = os.path.join(remote_operation_dir, 'pptx')
        local_ppt_file_path = os.path.join(local_ppt_dir, ppt_filename)
        remote_ppt_file_path = os.path.join(remote_ppt_dir, ppt_filename)
        local_images_dir = os.path.join(local_operation_dir, 'images')
        remote_images_dir = os.path.join(remote_operation_dir, 'images')
        local_images_file_paths = self.local_abs_image_file_paths(local_images_dir)
        remote_input_file_path = self._remote_input_deform_keyfile_path()
        return {
            'is_error': False,

            'execution_id': self.eid,
            'execution_order': self.eo,
            'process_version_id': self.pvid,

            'local_operation_dir': local_operation_dir,
            'remote_operation_dir': remote_operation_dir,

            'local_images_dir': local_images_dir,
            'remote_images_dir': remote_images_dir,

            'img_filenames': local_images_file_paths,

            'local_ppt_dir': local_ppt_dir,
            'remote_ppt_dir': remote_ppt_dir,

            'ppt_file_name': ppt_filename,
            'local_ppt_abs_file_path': local_ppt_file_path,
            'remote_ppt_abs_file_path': remote_ppt_file_path,

            'time_start': self.time_start,

            'remote_input_file_path': remote_input_file_path,

            'ppt_template_abs_file_path': self._input_ppt_template_abs_file_path(),

            'ppt_title': f"模拟报告文件: {ppt_filename}",
            'ppt_report_number': self._ppt_title(),
            'ppt_report_name': '',
            'material_btt': material_btt
        }

    def copy_pdf_to_remote_file_server(self):
        try:
            old_extension = self.post_param['local_ppt_abs_file_path'].split('.')[-1]
            new_extension = 'pdf'
            len_old_extension = len(old_extension)
            pdf_src = self.post_param['local_ppt_abs_file_path'][:-len_old_extension] + new_extension
            pdf_dst = self.post_param['remote_ppt_abs_file_path'][0:-len_old_extension] + new_extension
            smb_shutil.copyfile(pdf_src, pdf_dst)
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def copy_ppt_to_remote_file_server(self):
        try:
            ppt_src = self.post_param['local_ppt_abs_file_path']
            ppt_dst = self.post_param['remote_ppt_abs_file_path']
            smb_shutil.copyfile(ppt_src, ppt_dst)
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def copy_images_to_remote_file_server(self):
        try:
            for image_paths in self.post_param['img_filenames'].values():
                for image_src in image_paths:
                    image_filename = os.path.basename(image_src)
                    image_dst = os.path.join(self.post_param['remote_images_dir'], image_filename)
                    smb_shutil.copyfile(image_src, image_dst)
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def generate_ppt(self):
        try:
            with locale_block('zh'):
                date_str = datetime.now().strftime(u"%Y年 %m月 %d日 %H时%M分")

            self.post_param['ppt_report_name'] = (f"工艺记录编号{self.pvid}。\n操作顺序号{self.eo}。"
                                                   f"\n日期和时间：{date_str}")

            ppt = DocumentPPT(self.param, self.post_param)

            ppt.add_new_slide(slide_type='title')

            for variable_name in self.variable_names:
                img_filenames: list[int] = self.post_param['img_filenames'][variable_name]
                title = VARIABLES[variable_name]['title']
                slide_config = [title, [img_filenames[0:3]], [img_filenames[3:8], img_filenames[8:12]]]

                ppt.add_new_slide(slide_type='images', slide_config=slide_config)
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def local_abs_image_file_paths(self, local_images_dir: str) -> dict:
        try:
            def img_abs_path(_name, _index):
                nonlocal local_images_dir
                file_name = self.img_filename(_name, _index)
                abs_file_path = os.path.join(local_images_dir, file_name)
                return abs_file_path
            return {_n: [img_abs_path(_n, _i) for _i in self.variants] for _n in self.variable_names}
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _remote_input_deform_keyfile_path(self) -> str:
        try:
            nas_dir: str = config.nas['absolute_path']
            operation_relative_path: str = self.param['table'][self.eo]['sub_operation_relative_path']
            path = os.path.join(nas_dir, operation_relative_path, 'EXPORT_LAST_STEP.KEY')
            return path
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _local_operation_path(self) -> str:
        try:
            local_dir: str = config.server['local_dir']
            operation_relative_path: str = self.param['operation']['operation_relative_path']
            local_operation_path = os.path.join(local_dir, operation_relative_path)
            return local_operation_path
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _remote_operation_path(self) -> str:
        try:
            nas_dir: str = config.nas['absolute_path']
            operation_relative_path: str = self.param['operation']['operation_relative_path']
            remote_operation_path = os.path.join(nas_dir, operation_relative_path)
            return remote_operation_path
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _input_ppt_template_abs_file_path(self) -> str:
        try:
            data_files_ppt: str = config.server['data_files_ppt']
            pptx_template = os.path.join(data_files_ppt, 'template.pptx')

            assert os.path.isfile(pptx_template), f"PPT template file '{pptx_template}' does not exist"
            return pptx_template
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _ppt_file_name(self) -> str:
        try:
            operation_name: str = self.param['operation']['operation_name']
            project_dir_name: str = self.param['project']['project_dir_name']

            file_name = f"{project_dir_name}_{operation_name}.pptx"
            return file_name
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _operation_name(self) -> str:
        try:
            row: pd.DataFrame = self.param['table'][self.eo]
            type_id: int = row['type_id']

            _ol: pd.DataFrame = config.lib['operations_library']
            db_column_names: str = _ol.loc[type_id, 'db_column_names']
            process_name: str = _ol.loc[type_id, 'process_name']

            if not db_column_names:
                operation_name = process_name

            else:

                type_id_nnn_column_names, type_id_nnn_values = self.param['type_id_nnn']

                assert len(db_column_names) == len(type_id_nnn_column_names), (
                    f"Columns count mismatch: "
                    f"'type_id_{type_id}' SQL table has {len(type_id_nnn_column_names)} columns, "
                    f"but 'operations_library.db_column_names' SQL table has {len(db_column_names)} columns")

                assert set(db_column_names) == set(type_id_nnn_column_names), (
                    f"Column names mismatch: "
                    f"'type_id_{type_id}' SQL table has columns with names: {type_id_nnn_column_names}, "
                    f"but 'operations_library.db_column_names' SQL table "
                    f"has columns with other names: {db_column_names}")

                operation_name = process_name.format(*type_id_nnn_values)

            return operation_name
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _ppt_title(self) -> str:
        try:
            operation_name: str = self._operation_name()
            title = f"操作名称：{operation_name}"
            return title
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def log_start(self):
        try:
            LOGGER.info(f"{self.log_id} PPT START: "
                        f"Input KEY-file '{self.post_param['remote_input_file_path']}' "
                        f"Local dir '{self.post_param['local_operation_dir']}'")
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _duration_str(self):
        try:
            duration_sec = time.monotonic() - self.post_param['time_start']
            _h = int(duration_sec // 3600.0)
            _m = int(duration_sec % 3600.0 // 60.0)
            _s = int(duration_sec - _h * 3600 - _m * 60)
            return f"{_h}:{_m}:{_s}"
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def ppt_parameters(self, key_file_data: dict) -> dict:
        try:
            keyfile_object_1_variables = key_file_data['objects'][1]
            _m = key_file_data['objects'][1]['measurements']

            cs = np.array(_m['principal_coordinate_system'])

            # LOGGER.info(f"Angles between x-axis and first vector of principal axis and transposed principal axis: "
            #             f"{self.angle_between_vectors(cs[:, 0], [1, 0, 0]):.2f} degrees, "
            #             f"{self.angle_between_vectors(cs[0, :], [1, 0, 0]):.2f} degrees")

            slice_list = [
                {'status': False},
                {'status': True, 'point': [0., 0., 0.], 'vector': [1., 0., 0.], 'contour': True},
                {'status': True, 'point': [0., 0., 0.], 'vector': [1., 0., 0.], 'contour': False},
                {'status': True, 'point': [0., 0., 0.], 'vector': [0., 1., 0.], 'contour': True},
                {'status': True, 'point': [0., 0., 0.], 'vector': [0., 1., 0.], 'contour': False},
                {'status': True, 'point': [0., 0., 0.], 'vector': [0., 0., 1.], 'contour': True},
                {'status': True, 'point': [0., 0., 0.], 'vector': [0., 0., 1.], 'contour': False},
                {'status': True, 'point': [100., 0., 0.], 'vector': [1., 0., 0.], 'contour': True},
                {'status': True, 'point': [100., 0., 0.], 'vector': [1., 0., 0.], 'contour': False},
                {'status': True, 'point': [0., 100., 0.], 'vector': [0., 1., 0.], 'contour': True},
                {'status': True, 'point': [0., 100., 0.], 'vector': [0., 1., 0.], 'contour': False},
                {'status': True, 'point': [0., 0., 100.], 'vector': [0., 0., 1.], 'contour': True},
                {'status': True, 'point': [0., 0., 100.], 'vector': [0., 0., 1.], 'contour': False},
                {'status': True, 'point': [10000., 0., 0.], 'vector': [1., 0., 0.], 'contour': True},
                {'status': True, 'point': [10000., 0., 0.], 'vector': [1., 0., 0.], 'contour': False},
                {'status': True, 'point': [0., 10000., 0.], 'vector': [0., 1., 0.], 'contour': True},
                {'status': True, 'point': [0., 10000., 0.], 'vector': [0., 1., 0.], 'contour': False},
                {'status': True, 'point': [0., 0., 10000.], 'vector': [0., 0., 1.], 'contour': True},
                {'status': True, 'point': [0., 0., 10000.], 'vector': [0., 0., 1.], 'contour': False}
            ]

            default_param = {
                'camera_view': 'iso',  # 'iso', '+x', '-x', '+y', '-y', '+z', '-z'
                'slice_view': slice_list[0],  # {'status': False}
                'projection_view': 'parallel',  # 'parallel', 'perspective'
                'mesh_view': 'surface',  # 'surface', 'wireframe', 'surface_with_wireframe', 'none'
                'colormap': 'rainbow',  # 'gray', 'rainbow'
                'colormap_shading': 'shaded',  # 'shaded', 'shaded_with_isolines', 'solid_bands', 'elemental'
                'colormap_range': [0., 0.3],  # [0., 1.], [0., 10.], [0., 100.], [0., 1000.]
                # 'resolution': (3000, 3000),
                # (100, 100), (100, 1000), (1000, 100), (1000, 1000), (2000, 2000), (5000, 5000)
                'colormap_title': 'Colormap test title',
                # 'image_file_extension': 'png',
                'vector_glyph': '2darrow',
                'vector_scale': False,
                'colorbar_orientation': 'horizontal',
                'colorbar_font_size': 72,
                'annotations': [],

                'center_of_mass': _m['center_of_mass'],
                'coordinate_axis': cs,
                'nodes': keyfile_object_1_variables['nodes'],
                'elements': keyfile_object_1_variables['elements']
            }
            return default_param
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def variable_parameters(self, variable_param: dict, key_file_data: dict, variable_name: str) -> dict:
        try:
            data_type = VARIABLES[variable_name]['data_type']

            keyfile_object_1_variables = key_file_data['objects'][1]

            variable_value = keyfile_object_1_variables[variable_name]

            variable_param |= VARIABLES[variable_name].copy()

            variable_param |= {
                'variable': variable_value,
                'data_type': data_type,
                'data_statistics': self.get_data_statistics(variable_value, data_type),
            }
            return variable_param
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def img_parameters(self, img_param: dict, variable_name: str, variant: int) -> dict:
        try:
            # nodes_relative = self.vector_relative(img_param['nodes'], img_param['coordinate_axis'])

            nodes_relative = img_param['nodes']

            min_corner = np.min(nodes_relative, axis=0)
            max_corner = np.max(nodes_relative, axis=0)

            mid_point = (min_corner + max_corner) / 2
            size = max_corner - min_corner

            main_view_annotations = [
                self.get_main_view_annotations_1(max_corner, mid_point, min_corner, size),
                self.get_main_view_annotations_2(max_corner, mid_point, min_corner, size),
                self.get_main_view_annotations_3(max_corner, mid_point, min_corner, size)]

            side_view_annotations = [
                self.get_side_view_annotations(max_corner, mid_point, min_corner, size)]

            slices = []
            for slice_num in range(1, 10):
                if slice_num <= 5:
                    _slice, annotation = self.slices_1_to_5(img_param['center_of_mass'],
                                                            max_corner,
                                                            min_corner,
                                                            size,
                                                            slice_num)
                    side_view_annotations.append(annotation)
                else:  # slice_num <= 9
                    _slice, annotation = self.slices_6_to_9(img_param['center_of_mass'],
                                                            max_corner,
                                                            mid_point,
                                                            size,
                                                            slice_num)
                slices.append(_slice)
                main_view_annotations.append(annotation)

            for part in range(1, 7):
                sv_annotation = self.side_vew_annotation(max_corner, min_corner, part, size)
                side_view_annotations.append(sv_annotation)

            # --------------------------- IMAGE PARAM --------------------------------

            img_param['file_server_abs_file_path'] = self.post_param['img_filenames'][variable_name][variant]
            img_param['local_abs_file_path'] = self.post_param['img_filenames'][variable_name][variant]

            img_param['variant'] = variant

            if variant <= 1:
                if variant == 0:
                    img_param['title'] = 'Front Isometric View'
                    img_param['camera_view'] = 'iso'
                else:
                    img_param['title'] = 'Back Isometric View'
                    img_param['camera_view'] = '-iso'
                img_param['annotations'] = main_view_annotations
                img_param['slice_contours'] = slices
                img_param['axis_view'] = {'status': True,
                                          'center': img_param['center_of_mass'],
                                          'bounds': [min_corner[0], max_corner[0]]}
            elif variant == 2:
                img_param['title'] = 'Side View'
                img_param['annotations'] = side_view_annotations
                img_param['slice_contours'] = slices[0:5]
                img_param['camera_view'] = '+y'
                img_param['camera_rotate'] = {'roll': 180}
                img_param['axis_view'] = {'status': True,
                                          'center': img_param['center_of_mass'],
                                          'bounds': [min_corner[0], max_corner[0]]}
            else:
                slice_num = variant - 3

                img_param['title'] = f'Slice {slice_num + 1}'

                img_param['annotations'] = []
                if slice_num <= 4:
                    img_param['title'] += ' (Axial View)'
                    img_param['slice_contours'] = slices[5:9]
                    img_param['camera_view'] = '-x'
                    img_param['camera_rotate'] = {'roll': 90}
                elif slice_num in [5, 7]:
                    img_param['slice_contours'] = slices[0:5]
                    img_param['camera_view'] = '+y'
                    img_param['camera_rotate'] = {'roll': 180 if slice_num == 5 else 0,
                                                  'yaw': 45 if slice_num == 5 else -45}
                    img_param['axis_view'] = {'status': True,
                                              'center': img_param['center_of_mass'],
                                              'bounds': [min_corner[0], max_corner[0]]}
                elif slice_num == 6:
                    img_param['title'] += ' (Top View)'
                    img_param['slice_contours'] = slices[0:5]
                    img_param['camera_view'] = '-z'
                    img_param['camera_rotate'] = {}
                    img_param['axis_view'] = {'status': True,
                                              'center': img_param['center_of_mass'],
                                              'bounds': [min_corner[0], max_corner[0]]}
                elif slice_num == 8:
                    img_param['title'] += ' (Side View)'
                    img_param['slice_contours'] = slices[0:5]
                    img_param['camera_view'] = '+y'
                    img_param['camera_rotate'] = {'roll': 180}
                    img_param['axis_view'] = {'status': True,
                                              'center': img_param['center_of_mass'],
                                              'bounds': [min_corner[0], max_corner[0]]}

                img_param['slice_view'] = {'status': True, 'contour': True} | slices[slice_num]

            img_param['colorbar'] = self.calculate_colorbar_scale_range(img_param['variable'],
                                                                        img_param['data_type'],
                                                                        variable_name,
                                                                        variant)
            return img_param
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def img_filename(self, variable_name: str, variant: int) -> str:
        try:
            project_dir_name: str = self.param['project']['project_dir_name']
            operation_dir_name: str = self.param['table'][self.eo]['operation_dir_name']
            fn = f"{project_dir_name}_{operation_dir_name}_{variable_name}_{variant}.png"
            return fn
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def angle_between_vectors(self, v1, v2) -> float:
        try:
            # Extract the X-axis unit vector from the coordinate system
            np_v1 = np.array(v1)

            # Vector [1, 0, 0] for comparison
            np_v2 = np.array(v2)

            # Calculate the cosine of the angle using dot product and magnitudes
            cos_angle = np.dot(np_v1, np_v2) / (np.linalg.norm(np_v1) * np.linalg.norm(np_v2))

            # Calculate the angle in radians
            angle_radians = np.arccos(np.clip(cos_angle, -1.0, 1.0))  # Clipping for numerical stability

            # Convert the angle to degrees
            angle_degrees = np.degrees(angle_radians)
            return angle_degrees
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def vector_relative(self, vector: np.array, basis: np.array) -> np.array:
        try:
            # Changes basis of given vector from "absolute" basis {(1, 0, 0), (0, 1, 0), (0, 0, 1)} to given basis
            result = np.linalg.solve(np.transpose(basis), vector.T).T
            return result
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def get_main_view_annotations_3(self, max_corner, mid_point, min_corner, size):
        try:
            result = {
                'type': 'dimension_parallel',  # text, annotation, dimension, total dimensions
                'text': f'{size[2]:.2f}',
                'text_3d_coordinates': (max_corner[0], min_corner[1] - 200., mid_point[2]),
                'text_h_align': 'center',  # left, right, center
                'text_v_align': 'center',  # top, bottom, center
                'text_color': (0., 0., 0.),  # RGB [0.0; 1.0]^3
                'font_height': 64,
                'font_style': 'normal',  # normal, bold, italic, bold_italic
                'border': True,
                'border_color': (0., 0., 0.),  # RGB [0.0; 1.0]^3
                'border_fill': True,
                'border_fill_color': (1., 1., 1.),  # RGB [0.0; 1.0]^3
                #
                'dimension_line_parallel_to': 'z',  # 'x', 'y', 'z'
                'extension_lines_parallel_to': 'y',  # 'x', 'y', 'z'
                #
                'lines_width': 2,
                'lines_color': (0., 0., 0.),  # RGB [0.0; 1.0]^3
                'lines_always_visible': True,
                'points_show': True,
                'points_3d_coordinates': (
                    (max_corner[0], min_corner[1], min_corner[2]),
                    (max_corner[0], min_corner[1], max_corner[2]),
                ),

                'point_radius': 8.0,
                'point_color': (0., 0., 0.),  # RGB [0.0; 1.0]^3
                'point_always_visible': True,

                'arrow_length': 0.5,
                'arrow_type': '3d'
            }
            return result
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def get_main_view_annotations_2(self, max_corner, mid_point, min_corner, size):
        try:
            result = {
                'type': 'dimension_parallel',  # text, annotation, dimension, total dimensions
                'text': f'{size[1]:.2f}',
                'text_3d_coordinates': (max_corner[0], mid_point[1], min_corner[2] - 200.),
                'text_h_align': 'center',  # left, right, center
                'text_v_align': 'center',  # top, bottom, center
                'text_color': (0., 0., 0.),  # RGB [0.0; 1.0]^3
                'font_height': 64,
                'font_style': 'normal',  # normal, bold, italic, bold_italic
                'border': True,
                'border_color': (0., 0., 0.),  # RGB [0.0; 1.0]^3
                'border_fill': True,
                'border_fill_color': (1., 1., 1.),  # RGB [0.0; 1.0]^3
                #
                'dimension_line_parallel_to': 'y',  # 'x', 'y', 'z'
                'extension_lines_parallel_to': 'x',  # 'x', 'y', 'z'
                #
                'lines_width': 2,
                'lines_color': (0., 0., 0.),  # RGB [0.0; 1.0]^3
                'lines_always_visible': True,
                'points_show': True,
                'points_3d_coordinates': (
                    (max_corner[0], min_corner[1], min_corner[2]),
                    (max_corner[0], max_corner[1], min_corner[2]),
                ),

                'point_radius': 8.0,
                'point_color': (0., 0., 0.),  # RGB [0.0; 1.0]^3
                'point_always_visible': True,

                'arrow_length': 0.5,
                'arrow_type': '3d'
            }
            return result
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def get_main_view_annotations_1(self, max_corner, mid_point, min_corner, size):
        try:
            result = {
                'type': 'dimension_parallel',  # text, annotation, dimension, total dimensions
                'text': f'{size[0]:.2f}',
                'text_3d_coordinates': (mid_point[0], min_corner[1] - 200., max_corner[2]),
                'text_h_align': 'center',  # left, right, center
                'text_v_align': 'center',  # top, bottom, center
                'text_color': (0., 0., 0.),  # RGB [0.0; 1.0]^3
                'font_height': 64,
                'font_style': 'normal',  # normal, bold, italic, bold_italic
                'border': True,
                'border_color': (0., 0., 0.),  # RGB [0.0; 1.0]^3
                'border_fill': True,
                'border_fill_color': (1., 1., 1.),  # RGB [0.0; 1.0]^3
                #
                'dimension_line_parallel_to': 'x',  # 'x', 'y', 'z'
                'extension_lines_parallel_to': 'y',  # 'x', 'y', 'z'
                #
                'lines_width': 2,
                'lines_color': (0., 0., 0.),  # RGB [0.0; 1.0]^3
                'lines_always_visible': True,
                'points_show': True,
                'points_3d_coordinates': (
                    (min_corner[0], min_corner[1], max_corner[2]),
                    (max_corner[0], min_corner[1], max_corner[2]),
                ),

                'point_radius': 8.0,
                'point_color': (0., 0., 0.),  # RGB [0.0; 1.0]^3
                'point_always_visible': True,

                'arrow_length': 0.5,
                'arrow_type': '3d'
            }
            return result
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def get_side_view_annotations(self, max_corner, mid_point, min_corner, size) -> dict:
        try:
            result = {
                'type': 'dimension_parallel',  # text, annotation, dimension, total dimensions
                'text': f'{size[0]:.2f}',
                'text_3d_coordinates': (mid_point[0], min_corner[1], max_corner[2] + 200.),
                'text_h_align': 'center',  # left, right, center
                'text_v_align': 'center',  # top, bottom, center
                'text_color': (0., 0., 0.),  # RGB [0.0; 1.0]^3
                'font_height': 64,
                'font_style': 'normal',  # normal, bold, italic, bold_italic
                'border': True,
                'border_color': (0., 0., 0.),  # RGB [0.0; 1.0]^3
                'border_fill': True,
                'border_fill_color': (1., 1., 1.),  # RGB [0.0; 1.0]^3
                #
                'dimension_line_parallel_to': 'x',  # 'x', 'y', 'z'
                'extension_lines_parallel_to': 'y',  # 'x', 'y', 'z'
                #
                'lines_width': 2,
                'lines_color': (0., 0., 0.),  # RGB [0.0; 1.0]^3
                'lines_always_visible': True,
                'points_show': True,
                'points_3d_coordinates': (
                    (min_corner[0], min_corner[1], max_corner[2]),
                    (max_corner[0], min_corner[1], max_corner[2]),
                ),

                'point_radius': 8.0,
                'point_color': (0., 0., 0.),  # RGB [0.0; 1.0]^3
                'point_always_visible': True,

                'arrow_length': 0.5,
                'arrow_type': '3d'
            }
            return result
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def slices_1_to_5(self, center_of_mass, max_corner, min_corner, size, slice_num) -> tuple[dict, dict]:
        try:
            point = (max_corner[0] - size[0] / 6 * slice_num, max_corner[1], min_corner[2])
            _slice = {
                'point': [point[0], center_of_mass[1], center_of_mass[2]],
                'vector': [1., 0., 0.]}
            annotation = {
                'type': 'annotation',  # text, annotation, dimension, total dimensions
                'text': f'{slice_num}',
                'text_3d_coordinates': (point[0], point[1] + 100., point[2] - 100.),
                'text_h_align': 'center',  # left, right, center
                'text_v_align': 'center',  # above, below, center
                'text_color': (0., 0., 0.),  # RGB [0.0; 1.0]^3
                'font_height': 64,
                'font_style': 'normal',  # normal, bold, italic, bold_italic
                'border': True,
                'border_color': (0., 0., 0.),  # RGB [0.0; 1.0]^3
                'border_fill': True,
                'border_fill_color': (1., 1., 1.),  # RGB [0.0; 1.0]^3
                #
                'lines_width': 2,
                'lines_color': (0., 0., 0.),  # RGB [0.0; 1.0]^3
                'lines_always_visible': True,

                'point_3d_coordinates': point,

                'point_radius': 8.0,
                'point_color': (0., 0., 0.),  # RGB [0.0; 1.0]^3
                'point_always_visible': True
            }
            return _slice, annotation
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def slices_6_to_9(self, center_of_mass, max_corner, mid_point, size, slice_num) -> tuple[dict, dict]:
        try:
            if slice_num == 6:
                _slice = {
                    'point': center_of_mass,
                    'vector': [0., 1., 1.]}
                point = (max_corner[0], mid_point[1] - size[1] / 4, mid_point[2] + size[1] / 4)
            elif slice_num == 7:
                _slice = {
                    'point': center_of_mass,
                    'vector': [0., 0., 1.]}
                point = (max_corner[0], mid_point[1] - size[1] / 4, mid_point[2])
            elif slice_num == 8:
                _slice = {
                    'point': center_of_mass,
                    'vector': [0., 1., -1.]}
                point = (max_corner[0], mid_point[1] - size[1] / 4, mid_point[2] - size[1] / 4)
            else:
                _slice = {
                    'point': center_of_mass,
                    'vector': [0., 1., 0.]}
                point = (max_corner[0], mid_point[1], mid_point[2] - size[2] / 4)

            annotation = {
                'type': 'annotation',  # text, annotation, dimension, total dimensions
                'text': f'{slice_num}',
                'text_3d_coordinates': (point[0] + 300., point[1], point[2]),
                'text_h_align': 'center',  # left, right, center
                'text_v_align': 'center',  # above, below, center
                'text_color': (0., 0., 0.),  # RGB [0.0; 1.0]^3
                'font_height': 64,
                'font_style': 'normal',  # normal, bold, italic, bold_italic
                'border': True,
                'border_color': (0., 0., 0.),  # RGB [0.0; 1.0]^3
                'border_fill': True,
                'border_fill_color': (1., 1., 1.),  # RGB [0.0; 1.0]^3
                #
                'lines_width': 2,
                'lines_color': (0., 0., 0.),  # RGB [0.0; 1.0]^3
                'lines_always_visible': True,

                'point_3d_coordinates': point,

                'point_radius': 8.0,
                'point_color': (0., 0., 0.),  # RGB [0.0; 1.0]^3
                'point_always_visible': True
            }
            return _slice, annotation
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def side_vew_annotation(self, max_corner, min_corner, part, size):
        try:
            left = (max_corner[0] - size[0] / 6 * (part - 1), min_corner[1], max_corner[2])
            right = (max_corner[0] - size[0] / 6 * part, min_corner[1], max_corner[2])
            sv_annotation = {
                'type': 'dimension_parallel',  # text, annotation, dimension, total dimensions
                'text': f'{size[0] / 6:.2f}',
                'text_3d_coordinates': ((left[0] + right[0]) / 2, min_corner[1], max_corner[2] + 100.),
                'text_h_align': 'center',  # left, right, center
                'text_v_align': 'center',  # top, bottom, center
                'text_color': (0., 0., 0.),  # RGB [0.0; 1.0]^3
                'font_height': 48,
                'font_style': 'normal',  # normal, bold, italic, bold_italic
                'border': True,
                'border_color': (0., 0., 0.),  # RGB [0.0; 1.0]^3
                'border_fill': True,
                'border_fill_color': (1., 1., 1.),  # RGB [0.0; 1.0]^3
                #
                'dimension_line_parallel_to': 'x',  # 'x', 'y', 'z'
                'extension_lines_parallel_to': 'y',  # 'x', 'y', 'z'
                #
                'lines_width': 2,
                'lines_color': (0., 0., 0.),  # RGB [0.0; 1.0]^3
                'lines_always_visible': True,
                'points_show': True,
                'points_3d_coordinates': (left, right),

                'point_radius': 8.0,
                'point_color': (0., 0., 0.),  # RGB [0.0; 1.0]^3
                'point_always_visible': True,

                'arrow_length': 0.5,
                'arrow_type': '3d'
            }
            return sv_annotation
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def assert_output_variable_names(self):
        try:
            allowed_variable_names = [
                _key for _key, _val in VARIABLES.items()
                if
                (
                        _val['var_type'] in ('nodal', 'element')
                        and _val['data_type'] in ('vector', 'scalar')
                        and _key not in ('user_element', 'user_nodal')
                )
                or
                _key == 'surface'
            ]

            wrong_variable_names = [variable_name for variable_name in self.variable_names
                                    if variable_name not in allowed_variable_names]

            assert len(wrong_variable_names) == 0, f"Variable(s) name(s) {wrong_variable_names} is(are) not valid"
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def get_data_statistics(self, var_value: np.ndarray, data_type: str):
        # Validate inputs
        if data_type not in ['vector', 'scalar']:
            LOGGER.error("data_type must be 'vector' or 'scalar'")
            raise ValueError("data_type must be 'vector' or 'scalar'")

        if var_value.ndim > 2 or (var_value.ndim == 2 and var_value.shape[1] not in (1, 3)):
            LOGGER.error("var_value must be a 1D or 2D array with 1 or 3 columns")
            raise ValueError("var_value must be a 1D or 2D array with 1 or 3 columns")

        try:
            # Calculate statistics
            if data_type == 'scalar':
                scalar_data = var_value.ravel()  # Flatten the array to 1D if needed
            elif data_type == 'vector':
                scalar_data = np.linalg.norm(var_value, axis=1)
            else:
                raise ValueError("Unexpected data_type")

            desc: DescribeResult
            # TODO: Fix error RuntimeWarning: Precision loss occurred in moment calculation due to catastrophic cancellation. This occurs when the data are nearly identical. Results may be unreliable.
            desc = stats.describe(scalar_data)

            results = {
                'mean': desc.mean,
                'variance': desc.variance,
                'standard_deviation': math.sqrt(desc.variance),
                'min': desc.minmax[0],
                'max': desc.minmax[1],
            }
            return results
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def calculate_colorbar_scale_range(self,
                                       var_value: np.ndarray,
                                       data_type: str,
                                       variable_name: str,
                                       variant_index: int):
        # Validate inputs

        if data_type not in ['vector', 'scalar']:
            LOGGER.error("data_type must be 'vector' or 'scalar'")
            raise ValueError("data_type must be 'vector' or 'scalar'")

        if var_value.ndim > 2 or (var_value.ndim == 2 and var_value.shape[1] not in (1, 3)):
            LOGGER.error("var_value must be a 1D or 2D array with 1 or 3 columns")
            raise ValueError("var_value must be a 1D or 2D array with 1 or 3 columns")

        # Initialize results dictionary
        colorbar_scale_marks_count = 9

        try:

            # Calculate statistics
            if data_type == 'scalar':
                scalar_data = var_value.ravel()  # Flatten the array to 1D if needed
            elif data_type == 'vector':
                scalar_data = np.linalg.norm(var_value, axis=1)
            else:
                raise ValueError("Unexpected data_type")

            filtered_data = self._remove_outliers(scalar_data)

            min_e = np.min(filtered_data) if filtered_data.size > 0 else np.array([])
            max_e = np.max(filtered_data) if filtered_data.size > 0 else np.array([])

            # variable_names = ['surface',
            #                   'nodal_scalar_temperature',
            #                   'max_temperature_operation',
            #                   'temperature_change_operation',
            #                   'strain_operation',
            #                   'strain_heat']

            if variable_name in ('nodal_scalar_temperature', 'max_temperature_operation'):
                if variant_index <= 2:  # Surface
                    _min, _max = min_e, max_e
                    scale_division = (_min - _max) / colorbar_scale_marks_count
                else:  # Sections
                    _min = max(min_e, self.param['table'][self.eo].get('max_temperature', 0))
                    _max = min(max_e, self.post_param['material_btt'])
                    scale_division = (_min - _max) / colorbar_scale_marks_count
            else:  # Rounded
                _min, _max = min_e, max_e
                scale_division = (_min - _max) / colorbar_scale_marks_count
                # _min, _max, scale_division = self._scale_round_step(min_e, max_e, colorbar_scale_marks_count)

            marks = np.linspace(_min, _max, colorbar_scale_marks_count)

            results = {
                'scale_marks_count': colorbar_scale_marks_count,
                'scale_division': scale_division,
                'scale_min': _min,
                'scale_max': _max,
                'scale_range': (_min, _max),
                'scale_marks': marks,
            }

            # min_val, max_val = desc.minmax
            # min_rn, max_rn, step_rn = scale_round_step(min_val, max_val, colorbar_scale_marks_count)  # Get step size

            # results['min_r'] = dynamic_rounding(desc.minmax[0])
            # results['max_r'] = dynamic_rounding(desc.minmax[1])
            # results['step_size_rn'] = step_rn
            # results['min_rn'] = min_rn
            # results['max_rn'] = max_rn
            # results['min_e'] = min_e
            # results['max_e'] = max_e
            # results['min_e_r'] = dynamic_rounding(min_e)
            # results['max_e_r'] = dynamic_rounding(max_e)

            return results
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def dynamic_rounding(self, value):
        try:
            if value == 0:
                results = 0  # Avoid log10 of zero
            else:
                # Calculate the order of magnitude of the mean of the data
                order_of_magnitude = np.floor(np.log10(np.abs(value)))
                # Define the rounding precision based on the magnitude
                precision = int(-order_of_magnitude) if order_of_magnitude < 0 else 0
                results = round(value, precision)
            return results
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _scale_round_step(self, _min_val, _max_val, _n_pieces) -> tuple[float, float, float]:
        try:
            if _max_val == _min_val:
                return 0, 0, 0  # Avoid division by zero
            step = (_max_val - _min_val) / _n_pieces
            bases_list = [[10, 5],
                          [7.5, 2.5, 2],
                          [9, 8, 7, 6, 4, 3],
                          [9.5, 8.5, 6.5, 5.5, 4.5, 3.5, 2.5, 1.5]]
            round_step = step
            for bases in bases_list:
                # noinspection PyBroadException
                try:
                    round_step = self.scale_round_value(step, bases)
                except Exception:
                    continue
                else:
                    break

            range_delta = round_step * _n_pieces
            input_range = _max_val - _min_val
            half_delta = (range_delta - input_range) / 2
            output_range = (_min_val - half_delta, _max_val + half_delta)
            for bases in bases_list:
                # noinspection PyBroadException
                try:
                    output_range = self.scale_round_range(_min_val, _max_val, range_delta, bases)
                except Exception:
                    continue
                else:
                    break

            return output_range[0], output_range[1], round_step
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def scale_round_range(self, _min_val, _max_val, _range, bases):
        try:
            min_values = []
            for base in bases:
                precision_range = int(np.ceil(-np.log10(_min_val / base)))
                for _add in [-2, -1, 0, 1, 2]:
                    min_values.append(base * round(_min_val / base, precision_range + _add))
            max_values = [(mv + _range) for mv in min_values]

            ranges = []
            ranges_deltas = []
            for _i in range(len(min_values)):
                _min_v = min_values[_i]
                _max_v = max_values[_i]
                if _min_v <= _min_val and _max_v >= _max_val:
                    ranges.append((_min_v, _max_v))
                    max_delta = max(abs(_max_val - _max_v), abs(_min_val - _min_v))
                    ranges_deltas.append(max_delta)

            _index = int(np.argmin(ranges_deltas))
            output_range = ranges[_index]

            return output_range
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def scale_round_value(self, _val, bases):
        try:
            values = []
            for base in bases:
                precision_up = int(np.ceil(-np.log10(_val / base)))
                precision_down = int(np.floor(-np.log10(_val / base)))
                round_up_val = base * round(_val / base, precision_up)
                round_down_val = base * round(_val / base, precision_down)
                values.append(round_up_val)
                values.append(round_down_val)
            _deltas = [(_v - _val) for _v in values]
            _ind_deltas = [(_i, _d) for _i, _d in enumerate(_deltas) if _d >= 0]
            _indices, _deltas_filtered = zip(*_ind_deltas)
            round_val = values[_indices[int(np.argmin(_deltas_filtered))]]
            return round_val
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def scale_round(self, value, _min_val, _max_val, _n_pieces):
        try:
            if _max_val == _min_val:
                result = value  # Avoid division by zero
            else:
                step = (_max_val - _min_val) / _n_pieces
                precision = 2 + np.floor(-np.log10(step)) if step != 0 else 0
                result = round(value / step) * step, round(step, int(precision))

            return result
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise


    def _remove_outliers(self, _data):
        try:
            # Compute the IQR
            q1 = np.percentile(_data, 25)
            q3 = np.percentile(_data, 75)
            _iqr = stats.iqr(_data)

            # Determine outlier bounds
            lower_bound = q1 - 1.5 * _iqr
            upper_bound = q3 + 1.5 * _iqr

            # Filter outliers
            filtered_data = _data[(_data >= lower_bound) & (_data <= upper_bound)]

            return filtered_data
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def generate_pdf(self):
        try:
            local_ppt_dir: str = self.post_param['local_ppt_dir']
            ppt_file_name: str = self.post_param['ppt_file_name']
            pptx_path = os.path.join(local_ppt_dir, ppt_file_name)

            # Check if the input file is a valid pptx file
            if not pptx_path.lower().endswith('.pptx'):
                raise ValueError("The input file must be a PowerPoint file with .pptx extension")

            # Get the absolute path and the directory of the pptx file
            abs_pptx_path: str = os.path.abspath(pptx_path)
            pptx_directory: str = os.path.dirname(abs_pptx_path)
            pptx_filename: str = os.path.basename(abs_pptx_path)

            # Define the output PDF path
            pdf_filename = pptx_filename.replace('.pptx', '.pdf')
            pdf_path = os.path.join(pptx_directory, pdf_filename)

            # Initialize PowerPoint application
            powerpoint = win32com.client.Dispatch("PowerPoint.Application")
            powerpoint.Visible = 1  # Not hide the application window

            # Open the presentation
            presentation = powerpoint.Presentations.Open(abs_pptx_path)

            # Save as PDF
            presentation.SaveAs(pdf_path, 32)  # 32 is the enumeration for PDF format
            presentation.Close()

            # Quit the PowerPoint application
            powerpoint.Quit()
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    @staticmethod
    def get_user_directory():
        import ctypes.wintypes
        csidl_personal = 5  # My Documents
        shgfp_type_current = 0  # Get current, not default value
        buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(None, csidl_personal, None, shgfp_type_current, buf)
        return buf.value  # User's documents directory

    def create_new_dir_or_clean_existing_dir(self, _path: str, extension: str = '', is_remove_dirs: bool = True):
        """Create new project directory on server"""
        try:
            if is_samba_path(_path):
                self._samba_create_new_dir_or_clean_existing_dir(_path, extension, is_remove_dirs)
            else:
                self._local_create_new_dir_or_clean_existing_dir(_path, extension, is_remove_dirs)
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _samba_create_new_dir_or_clean_existing_dir(self, _path: str, extension: str = '', is_remove_dirs: bool = True):
        try:
            if smbclient.path.exists(_path):
                self.remove_content_of_remote_dir_using_samba(_path, extension, is_remove_dirs)
            else:
                smbclient.makedirs(_path)

            assert smbclient.path.isdir(_path), "Finally dir is not created after 'smbclient.mkdirs'"
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _local_create_new_dir_or_clean_existing_dir(self, _path: str, extension: str = '', is_remove_dirs: bool = True):
        try:
            if os.path.exists(_path):
                remove_content_of_local_dir(abs_path=_path,
                                            exclude_file_extensions=(extension, ),
                                            is_remove_dirs=is_remove_dirs)
            else:
                os.makedirs(_path)

            assert os.path.isdir(_path), "Finally dir is not created after 'os.mkdirs'"
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def remove_content_of_remote_dir_using_samba(self, _path: str, extension: str = '', is_remove_dirs: bool = True):
        try:
            file_counter = 0
            dir_counter = 0

            if smbclient.path.exists(_path):
                for root, dirs, files in smbclient.walk(str(_path)):
                    for _file in files:
                        if extension and os.path.splitext(_file)[1] != extension:
                            continue
                        smbclient.unlink(os.path.join(root, _file))
                        file_counter += 1
                    if is_remove_dirs:
                        for _dir in dirs:
                            smbclient.rmdir(os.path.join(root, _dir))
                            dir_counter += 1

            if file_counter > 0 or dir_counter > 0:
                LOGGER.info(f"{self.log_id} "
                            f"REMOVED {file_counter} files and {dir_counter} dirs in '{_path}'")
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _import_parameters_json_from_nas(self) -> dict:
        # LOGGER.info("START func '_import_previous_operation_parameters'")
        try:
            nas_dir: str = config.nas['absolute_path']
            project_dir_name: str = self.param['project']['project_dir_name']
            operation_dir_name: str = self.param['table'][self.eo]['operation_dir_name']
            filepath = os.path.join(nas_dir, project_dir_name, operation_dir_name, 'parameters.json')
            attempts = config.server['file_remove_attempts_before_raising_error']
            repeat_time = config.server['file_remove_attempts_cycle_time_sec']
            assert smbclient.path.isfile(filepath), \
                f"File '{filepath}' not found for 'execution_order'={self.eo}"
            # ------------------------------------------------------------------------
            is_success = False
            count = 0
            for count in range(1, max(2, attempts) + 1):
                try:
                    with smbclient.open_file(filepath, encoding='utf-8') as json_file:
                        operation_param = json.load(json_file)
                    is_success = True
                    break
                except Exception as _err:
                    LOGGER.warning(
                        f"{self.log_id} "
                        f"FAILED {count} of {attempts} attempts to read content of {filepath} file. "
                        f"Wait {repeat_time} sec before try again. {type(_err).__name__}: {_err}")
                    time.sleep(repeat_time)
            # ------------------------------------------------------------------------
            assert is_success, f"FAILED reading {filepath} after {count} attempts"
            assert operation_param, f"File '{filepath}' is empty for 'execution_order'={self.eo}"
            return operation_param
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _silent_query_set_post_status_error(self):
        """
        Do SQL query and set 'post_status'.
        """
        conn = config.get_connection()
        try:
            cur = conn.cursor()
            query = """
        UPDATE server_pre_main SET 
                post_server_id = NULL,
                post_status = 'error'::post_status_enum,
                post_time_finished = NOW(),
                post_images_abs_path = DEFAULT,
                post_pptx_abs_path = DEFAULT,
                ppt_file_name = DEFAULT 
            WHERE execution_id = %s;"""
            cur.execute(query, (self.eid,))
            conn.commit()
            cur.close()
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            LOGGER.warning(
                f"{self.log_id} FAILED UPDATE server_pre_main "
                f"SET 'post_status'='error' where 'execution_id'={self.eid}")
        finally:
            config.put_connection(conn)

    def _query_set_post_status_finished(self):
        try:
            server_id = config.server['id']
            values_dict = {
                'execution_id': self.eid,
                'ppt_file_name': self.post_param['ppt_file_name'],
                'post_images_abs_path': self.post_param['remote_images_dir'],
                'post_pptx_abs_path': self.post_param['remote_ppt_dir']}
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

        conn = config.get_connection()
        try:
            cur = conn.cursor()
            query = """
                UPDATE server_pre_main
                SET 
                    post_server_id = DEFAULT,
                    post_status = 'finished'::post_status_enum,
                    post_time_finished = NOW(),
                    post_images_abs_path = %(post_images_abs_path)s,
                    post_pptx_abs_path = %(post_pptx_abs_path)s,
                    ppt_file_name = %(ppt_file_name)s
                WHERE execution_id = %(execution_id)s;"""
            cur.execute(query, values_dict)
            conn.commit()
            cur.close()
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise RuntimeError(
                f"{self.log_id} FAILED Server 'id'={server_id} "
                f"when update 'server_pre_main' set 'post_status'='finished' "
                f"where eid={self.eid}")
        finally:
            config.put_connection(conn)

    @property
    def log_id(self):
        duration = str(round(time.monotonic() - self.time_start, 2))
        return f"{self.task_id_name} Duration {duration}s"

    @property
    def task_id_name(self) -> str:
        return f"[{self.pvid}][{self.eo}/{self.eo_last}] Post #{self.worker_id}"
