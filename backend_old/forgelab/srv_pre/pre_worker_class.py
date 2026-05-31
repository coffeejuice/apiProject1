import logging
import traceback
import decimal
import math
import os.path
from threading import Thread
from multiprocessing import Queue, Semaphore
import time
from itertools import cycle
import numpy as np
import pandas as pd
from psycopg2.extras import Json
from psycopg2.extensions import register_adapter
from psycopg2 import sql, DatabaseError, OperationalError
from psycopg2.extras import execute_values
from scipy import optimize
from scipy.interpolate import interp1d
from scipy.spatial.transform import Rotation
from scipy.spatial import ConvexHull
from shapely.geometry import Point, Polygon, box
from shapely import union_all
from shapely.affinity import scale
from trimesh import Trimesh, boolean, creation

from forgelab.common.common_funcs import log_error
from forgelab.config import config
# from forgelab.sql_setup.create_tooltip_images import img_height
from forgelab.srv_pre.geometry_class import Geometry

from forgelab.common.time_between_operations import get_time_between_operations
from forgelab.common.shapely_2d_funcs import \
    get_surface_area, prolongation_rotate_polygon, polygon_to_binary, height_of_polygon, \
    initial_width_of_contact, create_dies, get_cross_section_area, polygon_to_equivalent_diameter, \
    translate_geoms_increase_gap, strain_length_based_on_contact_shape, middle_polygon_fill_gap, \
    translate_polygons_after_optimization, assert_area_error, strain_error, \
    trim_middle_return_residual_area, import_3d_stl_intersect_by_xy_plane_return_2d_polygon, \
    gap_between_dies, final_dies_polygons, \
    convert_stl_binary_object_to_trimesh_object, intersect_3d_mesh_by_2d_plane, \
    rotate_trimesh_object, \
    polygon_to_3d_trimesh_object, convert_trimesh_object_to_memory_buffer_object, \
    randomize_vector, trimesh_basis_to_basis_transformation_matrix, polygon_y_scale_factor, \
    plot_trimesh_object, plot_polygon, _rigid_zone_weighting_factor
from forgelab.common.shapely_2d_funcs import rotate_basis


LOGGER = logging.getLogger(__name__)


register_adapter(dict, Json)


class PreWorker(Thread):
    """Main 'process_version_id' data processing."""

    def __init__(self, worker_id: int, task_queue: Queue, semaphore: Semaphore):
        super().__init__()

        # self.plot_queue = plot_queue
        self.worker_id: int = worker_id
        self.task_queue: Queue = task_queue
        self.semaphore: Semaphore = semaphore

        self.sim_units: list = []

        self._is_break = False

        self.pvid: int = 0
        self.operations: pd.DataFrame = pd.DataFrame()
        self.input: pd.DataFrame = pd.DataFrame()
        self.accumulation_trigger: pd.DataFrame = pd.DataFrame()
        self.accumulated: pd.DataFrame = pd.DataFrame()
        self.output: pd.DataFrame = pd.DataFrame()

        self.input_index: int = 0
        self.eo: int = 0

        self.input_index_last: int = 0
        self.eo_last: int = 0

        self.time_start: float = time.monotonic()

    def run(self):
        LOGGER.info(f"{self.log_id} started.")
        while True:
            try:
                (self.pvid, ) = self.task_queue.get()

                self._ini_counters()
                
                if self.pvid == 0:
                    LOGGER.warning(f"{self.log_id} received Shutdown Signal")
                    break

                LOGGER.info(f"{self.log_id} received Task")

                self._worker()
                self.semaphore.release()
                LOGGER.info(f"{self.log_id} Released 1 slot in Semaphore")

            except Exception as _err:
                log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
                break
        LOGGER.warning(f"{self.log_id} Terminated")

    def _worker(self):
        """
        Main threading.Thread method. When thread.start() is called, this method is executed.
        Contains a while loop which will be executed until row_id counter reaches total number of rows in SQL query.
        The loop starts with SQL query to get list of operations (one operation per row) for current simulation_id.
        """

        try:
            LOGGER.info(f"{self.log_id} OK: STARTED")

            self._query_block_run_switch()
            self.query_initialize_simulation_expected_duration_days()
            operations_list_of_tuples = self._query_operations()

            if not operations_list_of_tuples:
                self.query_set_preview_status('empty')
                return True

            self.query_set_preview_status('error')

            self.operations = self._query_operations_return_flat_tree(operations_list_of_tuples)

            if self.operations.shape[0] == 0:
                self._ini_counters()
                return False

            self.input, self.input_index_last = self._input_dataframe()

            if self.input.shape[0] == 0:
                self._ini_counters()
                return False

            self.accumulation_trigger = self.calculate_accumulation_trigger_from_library()
            self._accumulated_dataframe()

            self.output = self._output_dataframe()
            self._output_reversing_feed_direction()
            self._output_step_control()
            self.eo = self.get_input_index_return_output_index(self.input_index)
            self.eo_last = self.get_input_index_return_output_index(self.input_index_last)

            self._logging_dataframe_init_failure()

            if not self._query_insert_output_into_server_pre_main():
                return False

            while not self._is_break:
                if self.calculate_output_row():
                    if self.query_update_server_pre_main_set_output_row():
                        # ----------- EVERYTHING IS OK ------------
                        LOGGER.info(f"{self.log_id} OK")
                        if self.eo >= self.eo_last:
                            break
                        self.eo += 1
                        continue
                # ----------- ERROR IN OPERATION ------------
                break

            if self._is_break:
                self.query_set_preview_status('error')
                LOGGER.error(f"{self.log_id} FAILED")

            else:
                self.query_set_preview_status('ok')
                self.query_update_process_versions()
                self._query_unblock_run_switch()
                LOGGER.info(f"{self.log_id} OK FINISHED")

        except Exception as _err:
            LOGGER.warning(
                f"{self.log_id} FAILED Main Script, but Worker will be initialized and keeps running "
                f"{type(_err).__name__}: {_err}")

    def calculate_output_row(self) -> bool:
        """Iterates over 'self.operations'. Returns table of calculations."""
        row, i = self.output, self.eo
        try:
            self.input_index = self.get_output_index_return_input_index(i)
            row.at[i, 'is_ready'] = True
            row.at[i, 'feed_type_id'] = self.accumulated.loc[self.input_index, 'feed_type_id']
            row.at[i, 'max_temperature'] = self.max_temperature()

            match self.type_id:

                # Round Billets - parent_type_id = 7
                case 68:
                    self.add_billet()  # Billet round
                case 69:
                    self.add_billet()  # Billet round tail radius
                case 70:
                    self.add_billet()  # Billet round tail chamfer
                case 71:
                    self.add_billet() # Billet round length_to_diameter_ratio

                # Square Billets - parent_type_id = 7
                case 72:
                    self.add_billet()  # Billet square
                case 73:
                    self.add_billet()  # Billet square diagonal chamfers
                case 74:
                    self.add_billet()  # Billet square length_to_side_ratio

                # Rectangular Billets - parent_type_id = 7
                case 75:
                    self.add_billet()  # Billet rectangular
                case 76:
                    self.add_billet()  # Billet rectangular 'height_to_width_ratio', 'length_to_thickness_ratio'
                case 77:
                    self.add_billet()  # Billet rectangular equal diagonal chamfers
                case 78:
                    self.add_billet()  # Billet rectangular unequal diagonal chamfers

                # Octagon Billets - parent_type_id = 7
                case 79:
                    self.add_billet()  # Billet octagon

                # Heating operations - parent_type_id = 11
                case 23:
                    self.add_operation_23_heating()

                # Upsetting operations - parent_type_id = 37
                case 91:
                    self.add_operation_upsetting()
                case 93:
                    self.add_operation_upsetting()
                case 94:
                    self.add_operation_upsetting()
                case 92:
                    self.add_operation_upsetting()  # tail_flattening_with_rotation
                case 100:
                    self.add_operation_100_tail_chamfering()

                # Axial prolongation - parent_type_id = 38
                case 46:
                    self._add_operation_prolongation()  # axial_prolongation-simple
                case 83:
                    self._add_operation_prolongation()  # num_of_bites
                case 90:
                    self._add_operation_prolongation()  # num_of_bites_skip_bites

                # Spiral prolongation - parent_type_id = 99
                case 50:
                    self.add_operation_50_51_spiral_prolongation()  # rounding_spiral_1_rotation_1_feed
                case 51:
                    self.add_operation_50_51_spiral_prolongation()  # rounding_spiral_3_rotation_1_feed

                # Radial prolongation - parent_type_id = 35
                case 95:
                    self._add_operation_prolongation()  # Feed
                case 96:
                    self._add_operation_prolongation()  # Num of bites
                case 80:
                    self._add_operation_prolongation()  # (Obsolete) Feed
                case 82:
                    self._add_operation_prolongation()  # (Obsolete) Num of bites

                # Full die operations - parent_type_id = 39
                case 52:
                    self.add_operation_52_full_die_simple()

                # Radial forging GFM - parent_type_id = 63
                case 64:
                    self.add_operation_64_radial_forging_gfm()

                # Hot Cutting operations - parent_type_id = 40
                case 57:
                    self.add_operation_57_hot_cut_percentage()  # Cut on {} pieces, keep piece #{} with length ratio {}%

                # Cold Sawing operations - parent_type_id = 61
                case 86:
                    self.add_operation_86_cold_sawing_percentage()  # Cut on {} pieces, keep piece #{} with length ratio {}%

                case _:
                    raise ValueError(f"Unknown operation type_id: {self.type_id}")

            # ---------------------------------------------------------

            assert row.at[i, 'is_ready'], "'is_ready' = False"

            return True
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()
            return False

    def _ini_counters(self):
        self._is_break = False
        self.time_start = time.monotonic()
        self.input_index = 0
        self.input_index_last = 0
        self.eo = 0
        self.eo_last = 0

    def _stop_calculations(self):
        LOGGER.error(f"{self.log_id} FAIL: BREAK CALCULATIONS")
        self._is_break = True
        self._set_is_ready_false()

    def _set_is_ready_false(self):
        if 'is_ready' in self.output.columns:
            if self.output['is_ready'].dtype.type is np.bool_:
                if self.eo in self.output.index:
                    self.output.loc[self.eo, 'is_ready'] = False
                    return
        LOGGER.error(f"{self.log_id} FAILED to set OUTPUT['is_ready'] = False")

    def _logging_dataframe_init_failure(self):
        try:
            i_l, i_r = self.input_index_last, (self.input.shape[0] - 1)
            o_l, o_r = self.eo_last, (self.output.shape[0] - 1)

            input_failed_count, output_failed_count = (i_l - i_r), (o_l - o_r)
            input_failed, output_failed = input_failed_count != 0, output_failed_count != 0

            if input_failed and output_failed:
                LOGGER.warning(f"{self.log_id} FAIL to initialize both DataFrames: "
                               f"INPUT failed at row {i_l}/{i_r}, OUTPUT failed at row {o_l}/{o_r}")
            elif input_failed:
                LOGGER.warning(f"{self.log_id} FAILED to initialize INPUT DataFrames at row {i_l}/{i_r}")
            elif output_failed:
                LOGGER.warning(f"{self.log_id} FAILED to initialize OUTPUT DataFrames at row {o_l}/{o_r}")
            else:
                LOGGER.info(f"{self.log_id} OK: DataFrames initialized.")
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()

    def _query_block_run_switch(self):
        """Set 'process_versions.is_simulation_allowed' = False. It blocks 'run' button."""
        query = "UPDATE process_versions SET run_switch_is_active = False WHERE process_version_id = %s;"
        conn = config.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(query, (self.pvid,))
            conn.commit()
            cur.close()
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()
        finally:
            config.put_connection(conn)

    def _query_unblock_run_switch(self):
        """Set 'process_versions.is_simulation_allowed' = True. It unblocks 'run' button."""

        query = "UPDATE process_versions SET run_switch_is_active = True WHERE process_version_id = %s;"
        conn = config.get_connection()

        try:
            cur = conn.cursor()
            cur.execute(query, (self.pvid,))
            conn.commit()
            cur.close()

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()
        finally:
            config.put_connection(conn)

    def _query_insert_output_into_server_pre_main(self) -> bool:

        try:
            self._assert_mandatory_columns()

            columns_indices, rows_indices = self.select_rows()

            if self.eo == 0:
                self.query_delete_all()
            else:
                self.query_delete_selected(rows_indices)

            list_of_dicts = self.output.loc[rows_indices, columns_indices].to_dict('records')
            _data_list = [tuple(row[column] for column in columns_indices) for row in list_of_dicts]

            self._query_insert_many(_data_list, columns_indices)

            assert not self._is_break, "FAILED Update SQL"

            LOGGER.info(f"{self.log_id} OK Update SQL")
            return True
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()
            return False

    def _query_insert_many(self, _data_list: list[tuple], columns_indices: pd.Index):
        conn = config.get_connection()
        try:
            cur = conn.cursor()
            _insert_format = sql.SQL(',').join(map(sql.Identifier, columns_indices))
            _insert_query = sql.SQL("INSERT INTO server_pre_main ({}) VALUES %s").format(_insert_format)
            execute_values(cur, _insert_query, _data_list, template=None, page_size=100)
            conn.commit()
            cur.close()

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()
        finally:
            config.put_connection(conn)

    def _assert_mandatory_columns(self):
        try:
            all_not_na_bool_mask = self.output[config.lib['server_pre_main_columns']].notna().all(axis=0)
            fully_defined_columns = all_not_na_bool_mask.loc[all_not_na_bool_mask].index
            mandatory_columns = config.lib['server_pre_main_not_null_columns']
            missing_items = mandatory_columns.difference(fully_defined_columns).to_list()

            assert not missing_items, (f"Missing mandatory (FOREIGN KEY) columns "
                                       f"of 'server_pre_main' are: {missing_items}")

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()

    def select_rows(self) -> tuple[pd.Index, pd.Index]:
        try:
            any_not_na_bool_mask = self.output[config.lib['server_pre_main_columns']].notna().any(axis=0)
            any_not_na_columns = any_not_na_bool_mask.loc[any_not_na_bool_mask].index

            rows_indices = pd.Index(list(range(self.eo, self.output.shape[0])))
            return any_not_na_columns, rows_indices
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()

    def query_delete_selected(self, _rows):
        conn = config.get_connection()
        try:
            _delete_query = (f"DELETE FROM server_pre_main WHERE process_version_id"
                             f" = {self.pvid} AND execution_order = %s;")
            cur = conn.cursor()
            cur.executemany(_delete_query, [[value] for value in _rows])
            conn.commit()
            cur.close()
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()
        finally:
            config.put_connection(conn)

    def query_delete_all(self):
        conn = config.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(f"DELETE FROM server_pre_main WHERE process_version_id = {self.pvid};")
            conn.commit()
            cur.close()

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()
        finally:
            config.put_connection(conn)

    def query_update_server_pre_main_set_output_row(self):
        row, i = self.output, self.eo
        try:
            operation_id = row.at[i, 'operation_id'].item()
            # columns = config.lib['output_columns']

            not_na_bool_mask = row.loc[i, config.lib['server_pre_main_columns']].notna()
            columns_indices = not_na_bool_mask.loc[not_na_bool_mask].index
            _data_dict = row.loc[[i], columns_indices].to_dict('records')
            _data_list = tuple(row[column] for column in _data_dict[0])
            data_tuples = tuple((column, value,) for column, value in _data_dict[0].items())

            self.query_update_many(operation_id, data_tuples)

            return True
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()
            return False

    def query_set_preview_status(self, status: str):
        conn = config.get_connection()
        try:
            cur = conn.cursor()
            query = ("UPDATE process_versions SET preview_status = %s::preview_status_enum "
                     "WHERE process_version_id = %s;")
            cur.execute(query, (status, self.pvid,))
            conn.commit()
            cur.close()
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            LOGGER.error(f"{self.log_id} Failed to set process_versions.preview_status = '{status}'")
            self._stop_calculations()
        finally:
            config.put_connection(conn)

    def query_update_process_versions(self):
        conn = config.get_connection()
        try:
            operations_count = self.output.shape[0]
            simulation_server_id = config.server['default_queue_simulation_server_id']
            simulation_expected_duration_days = self.output['simulation_expected_duration_days'].sum(axis=0).item()
            cur = conn.cursor()
            query = ("UPDATE process_versions SET "
                     "execution_order = %(eo)s, "
                     "operations_count = %(operations_count)s, "
                     "simulation_percent = %(percent_done)s, "
                     "simulation_expected_duration_days = %(days)s, "
                     "simulation_server_id = %(server_id)s "
                     "WHERE process_version_id = %(pvid)s;")
            cur.execute(query, {'eo': 0,
                                'operations_count': operations_count,
                                'percent_done': 0,
                                'days': simulation_expected_duration_days,
                                'server_id': simulation_server_id,
                                'pvid': self.pvid})
            conn.commit()
            cur.close()

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()
        finally:
            config.put_connection(conn)

    def query_initialize_simulation_expected_duration_days(self):
        conn = config.get_connection()
        try:
            cur = conn.cursor()
            query = ("UPDATE process_versions SET "
                     "execution_order = DEFAULT, simulation_percent = DEFAULT, "
                     "simulation_expected_duration_days = DEFAULT, simulation_server_id = DEFAULT "
                     "WHERE process_version_id = %s;")
            cur.execute(query, (self.pvid,))
            conn.commit()
            cur.close()

        except Exception as _err:
            LOGGER.error(
                f"{self.log_id} "
                f"FAILED UPDATE SET process_versions.simulation_expected_duration_days = NULL "
                f"{type(_err).__name__}: {_err}")
            self._stop_calculations()
        finally:
            config.put_connection(conn)

    def query_update_many(self, operation_id: int, update_values: tuple):
        conn = config.get_connection()
        query = sql.SQL("UPDATE server_pre_main SET {} = %s WHERE operation_id = %s;")
        try:
            cur = conn.cursor()
            for column, value in update_values:
                sql_column = sql.Identifier(column)
                sql_query = query.format(sql_column)
                try:
                    cur.execute(sql_query, (value, operation_id,))
                except (OperationalError, DatabaseError, Exception) as _err:
                    LOGGER.error(f"{self.log_id}] Failed query: {sql_query.as_string(conn)}, where value type = {type(value)}. {type(_err).__name__}: {_err}")
                    self._stop_calculations()
            conn.commit()
            cur.close()
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()
        finally:
            config.put_connection(conn)

    def get_input_index_return_output_index(self, _input_index: int) -> int:
        try:
            row = self.input.loc[self.input['input_index'] == _input_index, 'output_index']
            assert not row.empty, f"Input index '{_input_index}' not found in 'self.input'"
            return row.iloc[0].item()
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()
            raise

    def get_output_index_return_input_index(self, _output_index: int, _input_index_if_failed: int = None) -> int:
        try:
            operation_id = self.output.loc[_output_index, 'operation_id']
            return self.operations[self.operations['operation_id'] == operation_id].index.item()
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            return _input_index_if_failed if _input_index_if_failed else None

    def _find_first_diff_in_dataframes(self, df1: pd.DataFrame, df2: pd.DataFrame) -> int:
        """Compare elements of both lists one by one"""
        try:
            _len = min(df1.shape[0], df2.shape[0])
            if df1.equals(df2):
                result = 1 + df1.shape[0]
            elif df1.shape[0] == df2.shape[0]:
                ne_indices = np.flatnonzero(np.where(df1 != df2))
                result = min(ne_indices)
            elif _len == 0:
                result = 0
            else:
                ne_indices = np.flatnonzero(np.where(df1.iloc[:_len, :] != df2.iloc[:_len, :]))
                result = min(ne_indices)
            return result
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()

    @staticmethod
    def _int(_value):
        """Converts value to integer."""
        try:
            return int(_value)
        except TypeError as _e:
            return None

    @staticmethod
    def _float(_value):
        """Converts value to float."""
        try:
            return float(_value)
        except TypeError as _e:
            return None

    def _query_operations(self) -> list:
        """Get list of operations as list of tuples. Tuple is operation_id, operation_type_id."""
        result = []
        config.is_error = True

        try:
            columns = config.lib['operations_columns']
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()
            return result

        conn = config.get_connection()

        try:
            sql_columns = sql.SQL(',').join(map(sql.Identifier, columns))
            count_text = "SELECT COUNT(*) FROM operations WHERE process_version_id = %s;"
            count_query = sql.SQL(count_text).format(sql.Identifier(columns[0]))
            cur = conn.cursor()
            previous_count = 0
            for _i in range(10):
                cur.execute(count_query, (self.pvid,))
                conn.commit()
                count = cur.fetchone()
                if not count:
                    break
                new_count = count[0]
                if new_count != previous_count:
                    timeout = 0.1 + 0.25 * _i
                    time.sleep(timeout)
                    previous_count = new_count
                    LOGGER.info(f"{self.log_id} Wait for {timeout} s. 'operations' table is still changing. "
                                f"Operations count Old/New = {previous_count}/{new_count}.")
                else:
                    break
            cur.close()

            cur = conn.cursor()
            query = sql.SQL("SELECT {} FROM operations WHERE process_version_id = %s;").format(sql_columns)
            cur.execute(query, (self.pvid,))
            conn.commit()
            result = cur.fetchall()
            cur.close()

            config.is_error = False

            return result

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()
        finally:
            config.put_connection(conn)

    @staticmethod
    def designate_root_as_0(operations: list[dict]):
        """Finds where 'parent_id' is None and substitute None with 0."""
        for index, values in enumerate(operations):
            if values['parent_id'] is None:
                operations[index]['parent_id'] = 0
                return

    @staticmethod
    def convert_operations_to_dict(records: list[tuple]) -> list[dict]:
        return [
            {column_name: operation[index] for index, column_name in enumerate(config.lib['operations_columns'])}
            for operation in records
        ]

    @staticmethod
    def find_child_ids(records: list[dict]) -> dict:
        child_parent: list[tuple[int, int]]
        child_parent = [(record_dict.get('id'), record_dict.get('parent_id'),) for record_dict in records]
        result = {}
        for child, parent in child_parent:
            if parent in result:
                result[parent].append(child)
            else:
                result[parent] = [child]
        return result

    @staticmethod
    def build_library_dict(records_dict: list[dict]) -> dict:
        result = {column_name: {} for column_name in config.lib['operations_columns']}
        for record_dict in records_dict:
            _id: int = record_dict.get('id')
            for column_name in config.lib['operations_columns']:
                result[column_name][_id] = record_dict.get(column_name)
        return result

    @staticmethod
    def sorting_generator(_list: list, _scores: list) -> list:
        """Generator for sorting list by scores"""
        for _i in range(len(_list)):
            _min_score = min(_scores)
            _min_score_index = _scores.index(_min_score)
            _next_item = _list.pop(_min_score_index)
            del _scores[_min_score_index]
            yield _next_item

    def reorder_by_row(self, input_ids: dict, row_dict: dict) -> dict:
        """Reorder 'child_type_ids' by 'row' in 'lib' in place."""
        result = {}
        for parent_id, children_ids in input_ids.items():
            children_ids: list
            row_list = [row_dict[child] for child in children_ids]
            result[parent_id] = [x for x in self.sorting_generator(children_ids, row_list)]
        return result

    @staticmethod
    def build_tree(input_dict: dict):
        """Build tree of 'child_type_ids'."""

        def recursive_tree(_parent_id: int) -> dict:
            """Recursive function for building tree of child_type_ids"""
            _parent_ids = input_dict.keys()
            if _parent_id in _parent_ids:
                _tree = {}
                for __child_id in input_dict[_parent_id]:
                    _tree[__child_id] = recursive_tree(__child_id)
                return _tree
            return {}

        root_id = min(input_dict.keys())
        return recursive_tree(root_id)

    @staticmethod
    def convert_tree_to_flat(full_tree: dict, type_ids: dict) -> list:
        """Returns flat tree of 'operations' SQL table.""" 
        result = []

        def recursively_flatten_tree(tree: dict):
            """Flatten tree of child_type_ids."""
            for _id, branch in tree.items():

                result.append((_id, type_ids[_id],))

                if branch:
                    recursively_flatten_tree(branch)

        recursively_flatten_tree(full_tree)
        return result

    def _query_operations_return_flat_tree(self, operations_list_of_tuples: list) -> pd.DataFrame:
        """
        Queries all records of 'operations' table where 'process_version_id'.
        Returns list of tuples ('id', 'type_id').
        """
        operations_list_of_dicts = self.convert_operations_to_dict(operations_list_of_tuples)
        self.designate_root_as_0(operations_list_of_dicts)

        operations_dict_of_lists = self.build_library_dict(operations_list_of_dicts.copy())

        # self.child_ids = {}
        parent_children = self.find_child_ids(operations_list_of_dicts)
        child_ids = self.reorder_by_row(parent_children.copy(), operations_dict_of_lists['row'])

        tree = self.build_tree(child_ids.copy())

        flat_tree = self.convert_tree_to_flat(tree.copy(), operations_dict_of_lists['type_id'])

        return pd.DataFrame(flat_tree,
                            columns=['operation_id', 'type_id'],
                            index=list(range(len(flat_tree))),
                            dtype=int)

    @staticmethod
    def convert_decimal(_value):
        if isinstance(_value, decimal.Decimal):
            return float(_value)
        return _value

    def _input_dataframe(self) -> tuple[pd.DataFrame, int]:
        """Queries 'operations_type_id_nnn'. Returns parameters of these tables."""
        try:

            row_count = self.operations.shape[0]
            _columns = config.lib['input_columns']
            _data_types = config.lib['input_data_types']
            ol = config.lib['operations_library']
            lib_die = config.lib['die']

            _df = pd.DataFrame(np.nan, index=np.arange(row_count), columns=_columns).astype(_data_types)
            _df_mask = pd.DataFrame(True, index=np.arange(row_count), columns=_columns).astype(pd.BooleanDtype())

            _df.loc[:, ['operation_id', 'type_id']] = self.operations

            for row_index, row in self.operations.iterrows():
                operation_id, type_id = row['operation_id'].item(), row['type_id'].item()
                if column_names := ol.loc[type_id, 'db_column_names']:

                    type_id_values = self.query_type_id_nnn(type_id, column_names, operation_id)

                    for column_name, _value in zip(column_names, type_id_values):
                        _df.loc[row_index, column_name] = self.convert_decimal(_value)
                        if _value is None:
                            _df_mask.loc[row_index, column_name] = False

            type_ids = pd.Index(_df['type_id'])

            # add_type_id_feed_type
            # Collects properties of current operation and returns operation type.
            where_is_feed = ol.loc[type_ids, 'is_feed'].to_numpy()
            _df.loc[where_is_feed, 'feed_type_id'] = _df.loc[where_is_feed, 'type_id']

            # get_die_assembly_id_return_top_and_bottom_die_ids
            row_index_vs_die_assembly_id = _df.loc[_df['die_assembly_id'].notna().to_numpy(), 'die_assembly_id']
            column_name_vs_die_position = (
                ('top_die_id', 'is_matching_as_top'),
                ('bottom_die_id', 'is_matching_as_bottom'),
                ('plus_y_die_id',  'is_matching_as_plus_y'),
                ('minus_y_die_id',  'is_matching_as_minus_y')
            )
            for die_id_column_name, die_position in column_name_vs_die_position:
                die_id_vs_die_assembly_id = lib_die.loc[lib_die[die_position].to_numpy(), 'die_assembly_id']
                die_assembly_id_vs_die_id = \
                    pd.Series(data=die_id_vs_die_assembly_id.index,
                              index=die_id_vs_die_assembly_id.values).astype(dtype=pd.Int64Dtype())
                _df[die_id_column_name] = _df.index.map(row_index_vs_die_assembly_id).map(die_assembly_id_vs_die_id)

            # set_press
            where_is_press = ol.loc[type_ids, 'is_press'].to_numpy()
            press_ids = pd.Index(_df.loc[where_is_press, 'press_id'])
            press_ids_row_indices = _df.loc[where_is_press].index
            _df.loc[press_ids_row_indices, 'press'] = config.lib['press'].loc[press_ids, 'name'].to_numpy()

            # Sets 'deformation_type'.
            _df['deformation_type'] = ol.loc[type_ids, 'deformation_type'].reset_index(drop=True)

            # Sets default empty dict into 'operation_specific_parameters'
            _df['operation_specific_parameters'] = [{} for _ in range(_df.shape[0])]

            # Sets 'input_index'.
            _df['input_index'] = pd.Series(_df.index).astype(_df['input_index'].dtypes)

            # Sets 'output_index'.
            where_is_simulation = pd.Series(ol.loc[type_ids, 'is_simulation'].to_numpy()).fillna(False).astype(bool)
            output_lengths = where_is_simulation.sum(axis=0)
            _df.loc[where_is_simulation, 'output_index'] = np.arange(output_lengths)
            _df['output_index'] = _df['output_index'].bfill()

            _df_last_correct_index = _df.shape[0] - 1

            return _df, _df_last_correct_index

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()

    def query_type_id_nnn(self, _type_id: int,  columns_list: list, _id: int):
        conn = config.get_connection()
        try:
            sql_table = sql.Identifier(f"operations_type_id_{_type_id}")
            sql_columns = sql.SQL(',').join(map(sql.Identifier, columns_list))
            query = sql.SQL("SELECT {} FROM {} WHERE id = %s LIMIT 1;").format(sql_columns, sql_table)
            cur = conn.cursor()
            cur.execute(query, (_id,))
            conn.commit()
            result = cur.fetchone()
            cur.close()

            return result

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()
        finally:
            config.put_connection(conn)

    def calculate_accumulation_trigger_from_library(self) -> list:
        try:
            type_ids = self.input['type_id'].to_numpy()
            columns = ['trigger', 'is_initialize', 'is_accumulate', 'is_keep']
            result = config.lib['operations_library'].loc[type_ids, columns].reset_index(drop=True)
            return result
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()

    def _accumulated_dataframe(self):
        try:
            self.accumulated = self.input.copy()

            # Extract the indices where each condition is True
            is_accumulate = self.accumulation_trigger[self.accumulation_trigger['is_accumulate']].index
            is_keep = self.accumulation_trigger[self.accumulation_trigger['is_keep']].index

            # Combine indices
            is_accumulate_and_keep = is_keep.union(is_accumulate)

            for i in is_accumulate_and_keep:
                self.accumulated.update(self.accumulated.loc[[i - 1, i]].ffill().loc[[i]])

            self.at_accumulated_set_speed()
            self.accumulated['angle'] = self.accumulated['rotation']

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()

    def _output_dataframe(self) -> pd.DataFrame:
        """Returns indexes of 'self.operations' where 'is_simulation' = True."""
        # _l - list
        # _i - index
        # _o - operation_id
        # _t - type_id
        try:
            ol = config.lib['operations_library']
            type_ids = pd.Index(self.accumulated['type_id'])
            is_simulation = ol.loc[type_ids, 'is_simulation'].to_numpy()
            input_index_vs_output_index = self.accumulated.loc[is_simulation, 'output_index']
            input_index = input_index_vs_output_index.index
            output_index = pd.Index(input_index_vs_output_index.to_numpy())
            _df = pd.DataFrame(pd.NA, index=output_index, columns=config.lib['output_columns']).astype(config.lib['output_data_types'])
            _columns = _df.columns.intersection(self.accumulated.columns)
            _df[_columns] = self.accumulated.loc[input_index, _columns].reset_index(drop=True)

            _df['process_version_id'] = self.pvid
            _df['execution_order'] = output_index
            _df['material_id'] = _df.loc[0, 'material_id']

            feed_columns = pd.Index(('feed_first', 'feed_middle', 'feed_last'))
            _df.loc[:, feed_columns] = _df.loc[:, feed_columns].fillna(0)
            return _df
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()

    def _output_reversing_feed_direction(self):
        """Returns indexes of 'self.operations' where 'is_simulation' = True."""
        try:
            ol = config.lib['operations_library']
            all_axial_prolongation_operations_type_ids = ol.loc[ol['parent_type_id'].to_numpy() == 38, 'type_id'].to_numpy()
            axial_prolongation_operations_mask = self.operations['type_id'].isin(all_axial_prolongation_operations_type_ids)
            o_dtype = self.operations['operation_id'].dtype
            operations_parent_operation_id = self.operations[['operation_id']].where(self.operations['type_id'] == 38).ffill()
            output_parent_operation_id = operations_parent_operation_id.loc[
                axial_prolongation_operations_mask
            ].set_index(self.accumulated.loc[axial_prolongation_operations_mask, 'output_index'])['operation_id'].astype(o_dtype)

            for parent_operation_id in output_parent_operation_id.unique():
                output_indices = output_parent_operation_id[output_parent_operation_id == parent_operation_id].index
                if self.output.loc[output_indices[0], 'feed_direction_id'].item() == 4:
                    # Convert 'feed_direction_id' = 4 into sequence of (2, 3, 2, 3, 2, 3, ...)
                    feed_direction_id_pool = cycle([2, 3])
                    feed_direction_ids = [next(feed_direction_id_pool) for _ in range(len(output_indices))]
                else:
                    # Keep 'feed_direction_id' as is
                    feed_direction_ids = self.output.loc[output_indices, 'feed_direction_id']
                self.output.loc[output_indices, 'feed_direction_name'] = config.lib['feed_direction'].loc[feed_direction_ids].to_numpy()
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()

    def _output_step_control(self):
        """Returns indexes of 'self.operations' where 'is_simulation' = True."""
        try:
            def determine_step_control(column_names):
                return 'StepsNum' if 'num_of_bites' in column_names else 'Feed'

            ol = config.lib['operations_library']

            is_forming_category = ol.loc[self.output['type_id'], 'is_forming_category'].to_numpy()
            self.output['step_control'] = ol.loc[self.output['type_id'].to_numpy(), 'db_column_names'].reset_index(drop=True).apply(determine_step_control)[is_forming_category]

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()

    def add_billet(self):
        """Calculates a 'billet' and returns a dict."""
        row, i = self.output, self.eo
        accum, ai = self.accumulated, self.input_index
        try:
            weight = accum.loc[ai, 'weight']

            material_id = int(row.at[i, 'material_id'])
            material_short_name = config.lib['materials']['short_name'][material_id]
            density = config.lib['materials']['density'][material_id]
            _volume = weight * 1e9 / density

            db_column_names = config.lib['operations_library'].loc[self.type_id, 'db_column_names']
            # if isinstance(db_column_names, str):
            #     db_column_names = [db_column_names]
            values = accum.loc[ai, db_column_names].to_list()

            billet = Geometry(self.worker_id, self.pvid, self.eo, self.eo_last, self.time_start, self.type_id, db_column_names, values, _volume)
            billet.create()
            assert billet.is_created, "FAILED to create Billet"

            _surface_area = get_surface_area(billet.cross_section_polygon, billet.length)

            row.at[i, 'operation_type'] = 'NewBillet'
            row.at[i, 'step_control'] = material_short_name
            row.at[i, 'deformation_control'] = 'NA'
            row.at[i, 'k1'] = None

            # row.at[i, 'mesh_elements'] = int(accum.mesh_elements)

            row.at[i, 'simulation_expected_duration_days'] = 0.0

            row.at[i, 'initial_polygon'] = polygon_to_binary(billet.cross_section_polygon)
            row.at[i, 'final_polygon'] = polygon_to_binary(billet.cross_section_polygon)

            row.at[i, 'TEMPORARY.initial_polygon'] = billet.cross_section_polygon
            row.at[i, 'TEMPORARY.final_polygon'] = billet.cross_section_polygon

            row.at[i, 'initial_weight'] = weight
            row.at[i, 'final_weight'] = weight

            row.at[i, 'volume_initial'] = _volume
            row.at[i, 'volume_final'] = _volume

            row.at[i, 'final_height'] = billet.height
            row.at[i, 'final_width'] = billet.width
            row.at[i, 'final_length'] = billet.length

            row.at[i, 'initial_height'] = billet.height
            row.at[i, 'initial_width'] = billet.width
            row.at[i, 'initial_length'] = billet.length

            row.at[i, 'equivalent_diameter'] = billet.equivalent_diameter

            row.at[i, 'initial_cross_section_area'] = billet.cross_section_area
            row.at[i, 'final_cross_section_area'] = billet.cross_section_area

            row.at[i, 'initial_surface_area'] = _surface_area
            row.at[i, 'final_surface_area'] = _surface_area

            row.at[i, 'total_time'] = 0.0

            row.at[i, 'initial_basis'] = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
            row.at[i, 'final_basis'] = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]

            row.at[i, 'initial_3d_stl'] = billet.binary_3d_stl
            row.at[i, 'final_3d_stl'] = billet.binary_3d_stl

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()

    def add_operation_23_heating(self):
        """Calculates a 'heating' and returns a dict."""
        row, i = self.output, self.eo
        try:
            previous_operation_type_id = self.accumulated.loc[self.input_index - 1, 'type_id']
            assert previous_operation_type_id in (62, 23), f"Previous operation type_id must = {previous_operation_type_id}. But it must be be 62 or 23 (a furnace temperature point)."

            _furnace_class_id = int(self.accumulated.loc[self.input_index, 'furnace_class_id'])
            _duration = 60.0 * float(self.accumulated.loc[self.input_index, 'duration'])

            _temp_furnace_ini = self.accumulated.loc[self.input_index - 1, 'temperature']
            _temp_furnace_final = self.accumulated.loc[self.input_index, 'temperature']

            row.at[i, 'operation_type'] = 'Heat'
            # row.at[i, 'step_control'] = 'NA'
            row.at[i, 'deformation_control'] = 'NA'
            row.at[i, 'k1'] = None

            row.at[i, 'furnace_class_id'] = _furnace_class_id
            row.at[i, 'control_temperature_furnace_initial'] = _temp_furnace_ini
            row.at[i, 'control_temperature_furnace_final'] = _temp_furnace_final
            row.at[i, 'control_duration'] = _duration

            row.at[i, 'material_id'] = row.at[i - 1, 'material_id']

            row.at[i, 'total_time'] = row.at[i - 1, 'total_time'] + _duration

            row.at[i, 'TEMPORARY.initial_polygon'] = row.at[i - 1, 'TEMPORARY.initial_polygon']
            row.at[i, 'TEMPORARY.final_polygon'] = row.at[i - 1, 'TEMPORARY.final_polygon']

            row.at[i, 'initial_weight'] = row.at[i - 1, 'initial_weight']
            row.at[i, 'final_weight'] = row.at[i - 1, 'final_weight']

            row.at[i, 'elongation_channel_a'] = 0.0
            row.at[i, 'elongation_channel_b'] = 0.0

            row.at[i, 'strain_accumulated_channel_a'] = 0.0
            row.at[i, 'strain_accumulated_channel_b'] = 0.0

            self.add_missed_keys_from_previous()
            self.simulation_expected_duration_days_for_operation_23_heat()

            self.sim_unit_append(category='post', type='measure_billet', options={})
            self.sim_unit_append(category='sim', type='heat_transfer', options={})

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()

    def add_operation_upsetting(self):
        """Calculates a 'heating' and returns a dict."""
        row, i = self.output, self.eo
        try:
            row.at[i, 'operation_type'] = 'Upset'
            # 'step_control': ['Feed', 'StepsNum', 'OneStrictly', 'Three(Mid+L+R)', 'OneOrThree']
            # row.at[i, 'step_control'] = 'OneStrictly'
            row.at[i, 'deformation_control'] = 'H'  # ['E', 'P', 'H']
            row.at[i, 'k1'] = None
            row.at[i, 'press_mode_id'] = self.press_mode_id()
            row.at[i, 'mesh_elements'] = row.at[i - 1, 'mesh_elements']
            row.at[i, 'material_id'] = row.at[i - 1, 'material_id']

            osp = row.at[i, 'operation_specific_parameters']

            self._angle()
            osp['radial_rotations'] = [('x', self.get_acc('angle')),
                                       ('y', 90.0)]

            self._initial_basis()
            self._final_basis()
            self._initial_3d_stl__and__temporary_trimesh_obj()
            self._initial_dimensions()
            self._initial_polygon___as_convex_hull_of_trimesh_xy_projection()

            self._upsetting_feed()

            self.initial_cross_section_area()
            self.initial_height_to_width_ratio()
            self.initial_surface_area()
            self.initial_volume()
            self.initial_weight()

            # ---------------
            match self.type_id:
                case 91:
                    self._upsetting_final_length()
                    self._upsetting_input_l_return_p_and_e()
                case 93:
                    self._upsetting_final_length()
                    self._upsetting_input_l_return_p_and_e()
                case 94:
                    self._upsetting_final_length()
                    self._upsetting_input_l_return_p_and_e()
                case 92:  # Tail flattening
                    self.set_penetration()
                    self.upsetting_input_p_return_l_and_e()
                case _:
                    raise KeyError(f"Unknown type_id = {self.type_id}")
            # ---------------

            self._num_of_bites()

            self._initial_length_of_contact()
            self._initial_width_of_contact()

            self._upsetting_final_strain()
            self._upsetting_final_dimensions()

            self._upsetting_final_length_of_contact()
            self._upsetting_final_width_of_contact()

            self._upsetting_final_3d_stl()
            self._upsetting_final_polygon()
            self.final_cross_section_area()
            self.final_height_to_width_ratio()
            self.final_surface_area()
            self.final_volume()
            self.final_weight()

            self.equivalent_diameter()
            self.elongation_channel()
            self.strain_accumulated_channel()

            self.limit_speed_by_press_working_speed()

            self._open_die_height_max_before_working_stroke()
            self._open_die_height_min_after_working_stroke()
            self._working_stroke()
            self._working_approaching_stroke()
            self._idle_stroke()
            self._back_stroke()
            self._open_die_height_before_idle_stroke()

            self.time_between_bites()
            self.time_before_pass()
            self.time_bite_working()
            self.cycle_time()
            self.total_time()
            self.total_time_minutes()

            self.simulation_expected_duration_days_for_prolongation()
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()

    def add_operation_92_tail_flattening(self):
        """Calculates a 'heating' and returns a dict."""
        row, i = self.output, self.eo
        try:
            row.at[i, 'operation_type'] = 'Upset'
            # row.at[i, 'step_control'] = 'Feed'  # ['Feed', 'StepsNum', 'OneStrictly', 'Three(Mid+L+R)', 'OneOrThree']
            row.at[i, 'deformation_control'] = 'P'  # ['E', 'P', 'H']
            row.at[i, 'k1'] = None
            row.at[i, 'press_mode_id'] = self.press_mode_id()
            row.at[i, 'mesh_elements'] = row.at[i - 1, 'mesh_elements']
            row.at[i, 'material_id'] = row.at[i - 1, 'material_id']

            osp = row.at[i, 'operation_specific_parameters']

            self._angle()
            osp['radial_rotations'] = [('x', self.get_acc('angle')),
                                       ('y', 90.0)]

            self._initial_basis()
            self._final_basis()
            self._initial_3d_stl__and__temporary_trimesh_obj()
            self._initial_dimensions()
            self._initial_polygon___as_convex_hull_of_trimesh_xy_projection()

            self._upsetting_feed()

            self.initial_cross_section_area()
            self.initial_height_to_width_ratio()
            self.initial_surface_area()
            self.initial_volume()
            self.initial_weight()

            # ---------------
            self.set_penetration()
            self.upsetting_input_p_return_l_and_e()

            # ---------------

            self._num_of_bites()
    
            self._initial_length_of_contact()
            self._initial_width_of_contact()
    
            self._upsetting_final_strain()
            self._upsetting_final_dimensions()
    
            self._upsetting_final_length_of_contact()
            self._upsetting_final_width_of_contact()

            self._upsetting_final_3d_stl()
            self._upsetting_final_polygon()
            self.final_cross_section_area()
            self.final_height_to_width_ratio()
            self.final_surface_area()
            self.final_volume()
            self.final_weight()
    
            self.equivalent_diameter()
            self.elongation_channel()
            self.strain_accumulated_channel()

            self.limit_speed_by_press_working_speed()

            self._open_die_height_max_before_working_stroke()
            self._open_die_height_min_after_working_stroke()
            self._working_stroke()
            self._working_approaching_stroke()
            self._idle_stroke()
            self._back_stroke()
            self._open_die_height_before_idle_stroke()

            self.time_between_bites()
            self.time_before_pass()
            self.time_bite_working()
            self.cycle_time()
            self.total_time()
            self.total_time_minutes()
    
            self.simulation_expected_duration_days_for_prolongation()
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()

    def add_operation_100_tail_chamfering(self):
        """Calculates a 'heating' and returns a dict."""
        row, i = self.output, self.eo
        try:

            row.at[i, 'operation_type'] = 'Upset'
            # 'step_control': ['Feed', 'StepsNum', 'OneStrictly', 'Three(Mid+L+R)', 'OneOrThree']
            # row.at[i, 'step_control'] = 'StepsNum'
            row.at[i, 'deformation_control'] = 'P'  # ['E', 'P', 'H']
            row.at[i, 'k1'] = None
            row.at[i, 'press_mode_id'] = self.press_mode_id()
            row.at[i, 'mesh_elements'] = row.at[i - 1, 'mesh_elements']
            row.at[i, 'material_id'] = row.at[i - 1, 'material_id']

            self._angle()
            self._final_height()

            self._osp_radial_initial_rotations()
            self._osp_radial_accumulated_billet_rotation()
            self._osp_radial_rotations()

            self._initial_basis()
            self._final_basis()
            self._initial_3d_stl__and__temporary_trimesh_obj()
            self._initial_dimensions()
            self._initial_polygon___as_convex_hull_of_trimesh_xy_projection()

            # --------------

            # Tail chamfering parameters
            _k = 1 / 3  # Relative chamfer leg orthogonal to billet axis (chamfer_leg / billet_height)
            _h, _w, _l = row.loc[i, ['initial_height', 'initial_width', 'initial_length']].to_list()
            assert isinstance(row.at[i, 'operation_specific_parameters'], dict), \
                f"row.at[i, 'operation_specific_parameters'] is not a dict"
            row.at[i, 'operation_specific_parameters'].update({
                'projections': {
                    'height_to_length_projection': self._tail_chamfering_parameters(_l, _h, _k),
                    'width_to_length_projection': self._tail_chamfering_parameters(_l, _w, _k)}})

            self.set_penetration()
            self.upsetting_input_p_return_l_and_e()

            self._upsetting_feed()
    
            self.initial_cross_section_area()
            self.initial_height_to_width_ratio()
            self.initial_surface_area()
            self.initial_volume()
            self.initial_weight()
    
            self._num_of_bites()
    
            self._initial_length_of_contact()
            self._initial_width_of_contact()
    
            self._upsetting_final_strain()
            self._upsetting_final_dimensions()
    
            self._upsetting_final_length_of_contact()
            self._upsetting_final_width_of_contact()
    
            self._upsetting_final_polygon()
            self._final_3d_stl()
            self.final_cross_section_area()
            self.final_height_to_width_ratio()
            self.final_surface_area()
            self.final_volume()
            self.final_weight()
    
            self.equivalent_diameter()
            self.elongation_channel()
            self.strain_accumulated_channel()

            self.limit_speed_by_press_working_speed()

            self._open_die_height_max_before_working_stroke()
            self._open_die_height_min_after_working_stroke()
            self._working_stroke()
            self._working_approaching_stroke()
            self._idle_stroke()
            self._back_stroke()
            self._open_die_height_before_idle_stroke()

            self.time_between_bites()
            self.time_before_pass()
            self.time_bite_working()
            self.cycle_time()
            self.total_time()
            self.total_time_minutes()
    
            self.simulation_expected_duration_days_for_prolongation()
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()

    def _add_operation_prolongation(self):
        """Calculates a 'heating' and returns a dict."""
        row, i = self.output, self.eo
        try:
            row.at[i, 'operation_type'] = 'Draw'
            # row.at[i, 'step_control'] = 'Feed'  # ['Feed', 'StepsNum', 'OneStrictly', 'Three(Mid+L+R)', 'OneOrThree']
            row.at[i, 'deformation_control'] = 'H'  # ['E', 'P', 'H']
            row.at[i, 'k1'] = None
            row.at[i, 'press_mode_id'] = self.press_mode_id()
            row.at[i, 'mesh_elements'] = row.at[i - 1, 'mesh_elements']
            row.at[i, 'material_id'] = row.at[i - 1, 'material_id']

            osp = row.at[i, 'operation_specific_parameters']

            self._angle()
            self._final_height()

            self._osp_radial_initial_rotations()
            self._osp_radial_accumulated_billet_rotation()
            self._osp_radial_rotations()

            self._initial_basis()
            self._final_basis()

            if self.eo == 4:
                print("")

            self._initial_3d_stl__and__temporary_trimesh_obj()
            self._initial_dimensions()
            self._initial_polygon___as_convex_hull_of_trimesh_xy_projection()

            # -------------------------------------------------------------------------------------------

            self.initial_cross_section_area()
            self.initial_height_to_width_ratio()
            self.initial_surface_area()
            self.initial_volume()
            self.initial_weight()

            self.prolongation_input_h_return_p_and_e()

            # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! DIFFERENCE
            self._radial_prolongation_feed()

            self._initial_width_of_contact()
            self._initial_length_of_contact()

            self.prolongation_final_length_of_contact()
            self.prolongation_final_strain_height()

            dies_polygons = self.dies_cross_section_polygons()
            initial_dies_gap, ini_dies_polygons = gap_between_dies(row.at[i, 'TEMPORARY.initial_polygon'], dies_polygons)
            fin_dies_polygons = final_dies_polygons(ini_dies_polygons, row.at[i, 'penetration'])

            self._final_polygon_and_trimesh_obj(fin_dies_polygons)

            # ------------------ RECORD OPERATION SPECIFIC PARAMETERS --------------------------
            osp['rotation_per_bite'] = 0.0
            osp['height'] = self.get_acc('height')
            osp['rotations_count_per_feed_list'] = (0, 0, 0)
            osp['initial_dies_gap'] = initial_dies_gap
            osp['initial_top_die_reference_point_z_coord'] = ini_dies_polygons[0].bounds[1]
            osp['initial_bottom_die_reference_point_z_coord'] = ini_dies_polygons[1].bounds[3]
            osp['final_dies_gap'] = initial_dies_gap - row.at[i, 'penetration']
            osp['final_top_die_reference_point_z_coord'] = fin_dies_polygons[0].bounds[1]
            osp['final_bottom_die_reference_point_z_coord'] = fin_dies_polygons[1].bounds[3]
            # -------------------------------------------------------------------------------------

            self._final_dimensions()
            self.final_cross_section_area()
            self.final_height_to_width_ratio()
            self.final_surface_area()
            self.final_volume()
            self.final_weight()
    
            self.equivalent_diameter()
            self.elongation_channel()
            self.strain_accumulated_channel()

            self.limit_speed_by_press_working_speed()

            self._open_die_height_max_before_working_stroke()
            self._open_die_height_min_after_working_stroke()
            self._working_stroke()
            self._working_approaching_stroke()
            self._idle_stroke()
            self._back_stroke()
            self._open_die_height_before_idle_stroke()

            # =========================== BITES TABLE =====================================
            self._bites_table()

            self._num_of_bites()

            self.time_between_bites()
            self.time_before_pass()
            self.time_bite_working()
            self.cycle_time()
            self.total_time()
            self.total_time_minutes()

            self.simulation_expected_duration_days_for_prolongation()

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()

    def add_operation_50_51_spiral_prolongation(self):
        """Calculates a 'heating' and returns a dict."""
        row, i = self.output, self.eo
        try:

            row.at[i, 'operation_type'] = 'Draw'
            # row.at[i, 'step_control'] = 'Feed'  # ['Feed', 'StepsNum', 'OneStrictly', 'Three(Mid+L+R)', 'OneOrThree']
            row.at[i, 'deformation_control'] = 'H'  # ['E', 'P', 'H']
            row.at[i, 'k1'] = None
            row.at[i, 'press_mode_id'] = self.press_mode_id()
            row.at[i, 'mesh_elements'] = row.at[i - 1, 'mesh_elements']
            row.at[i, 'material_id'] = row.at[i - 1, 'material_id']

            self._angle()
            self._final_height()

            self._osp_radial_initial_rotations()
            self._osp_radial_accumulated_billet_rotation()
            self._osp_radial_rotations()

            self._initial_basis()
            self._final_basis()
            self._initial_3d_stl__and__temporary_trimesh_obj()
            self._initial_dimensions()
            self._initial_polygon___as_convex_hull_of_trimesh_xy_projection()

            # ------------------ READ OPERATION SPECIFIC PARAMETERS --------------------------
            rotation_per_bite = self.accumulated.loc[self.input_index, 'rotation_per_bite']
            diameter = self.accumulated.loc[self.input_index, 'diameter']

            # ------------------ ASSERT OPERATION SPECIFIC PARAMETERS --------------------------
            assert -360.0 < rotation_per_bite < 360.0, (f"Rotation per bite is {rotation_per_bite}°, "
                                                        f"but it must be between -360° and 360°.")
            assert diameter > 0.0, f"Final diameter is {diameter} mm, but it must be greater than 0.0 mm."

            # ------------------ RECORD OPERATION SPECIFIC PARAMETERS --------------------------
            osp = row.at[i, 'operation_specific_parameters']
            osp['rotation_per_bite'] = rotation_per_bite
            osp['diameter'] = diameter
            # Press makes 5 bites with same position: first bite has 'first_feed' and 4 next bites have 0 feed.

            match self.type_id:
                case 50:
                    osp['rotations_count_per_feed_list'] = (5, 0, 5)
                case 51:
                    osp['rotations_count_per_feed_list'] = (5, 2, 5)
                case _:
                    raise ValueError(f"Type_id must be 50 or 51, but it is {self.type_id}.")

            self.initial_cross_section_area()
            self.initial_height_to_width_ratio()
            self.initial_surface_area()
            self.initial_volume()
            self.initial_weight()

            dies_polygons = self.dies_cross_section_polygons()

            self._final_height()

            self.set_nominal_feeds_for_spiral_prolongation()
            self._bites_table()

            self._num_of_bites()

            # --------------------------------
            ini_billet_polygon = row.at[i, 'TEMPORARY.initial_polygon']
            initial_dies_gap, ini_dies_polygons = gap_between_dies(ini_billet_polygon, dies_polygons)
            # _plot_multy_polygons([ini_billet_polygon] + ini_dies_polygons)

            final_shape = Point((0.0, 0.0)).buffer(diameter / 2)
            final_dies_gap, fin_dies_polygons = gap_between_dies(final_shape, dies_polygons)
            # _plot_multy_polygons([final_shape] + fin_dies_polygons)

            osp['initial_dies_gap'] = initial_dies_gap
            osp['initial_top_die_reference_point_z_coord'] = ini_dies_polygons[0].bounds[1]
            osp['initial_bottom_die_reference_point_z_coord'] = ini_dies_polygons[1].bounds[3]

            osp['final_dies_gap'] = final_dies_gap
            osp['final_top_die_reference_point_z_coord'] = fin_dies_polygons[0].bounds[1]
            osp['final_bottom_die_reference_point_z_coord'] = fin_dies_polygons[1].bounds[3]

            # self.prolongation_input_h_return_p_and_e()

            penetration = initial_dies_gap - final_dies_gap

            if penetration > 0:
                row.at[i, 'penetration'] = penetration
                row.at[i, 'relative_deformation'] = penetration / row.at[i, 'initial_height'] * 100.0
            else:
                row.at[i, 'penetration'] = 0.0
                row.at[i, 'relative_deformation'] = 0.0

            row.at[i, 'initial_width_of_contact'] = 1.0
            # self._initial_width_of_contact(dies_polygons)

            self._initial_length_of_contact()

            # self.prolongation_final_length_of_contact()
            row.at[i, 'final_length_of_contact'] = row.at[i, 'feed_first']

            # -------------------------------------- FINAL POLYGON ------------------------------------------
            # self.prolongation_spiral_type_50_final_polygon(ini_billet_polygon, initial_dies_gap, ini_dies_polygons,
            #                                                final_shape, final_dies_gap, fin_dies_polygons)
            row.at[i, 'final_width_of_contact'] = 0.5 * diameter
            row.at[i, 'final_cross_section_area'] = final_shape.area
            row.at[i, 'final_polygon'] = polygon_to_binary(final_shape)
            row.at[i, 'TEMPORARY.final_polygon'] = final_shape

            # --------------------------------------- STRAIN X, Y, Z ---------------------------------------
            # self.prolongation_final_strain_height()
            # self.prolongation_final_strain_length_and_width()
            _strain_length = math.log(row.at[i, 'initial_cross_section_area'] / row.at[i, 'final_cross_section_area'])
            _strain_radial = -0.5 * _strain_length
            row.at[i, 'strain_length'] = _strain_length
            row.at[i, 'strain_height'] = _strain_radial
            row.at[i, 'strain_width'] = _strain_radial

            self._final_3d_stl()
            self._final_dimensions()
            # self.final_cross_section_area()
            self.final_height_to_width_ratio()
            self.final_surface_area()
            self.final_volume()
            self.final_weight()

            self.equivalent_diameter()
            self.elongation_channel()
            self.strain_accumulated_channel()

            self.limit_speed_by_press_working_speed()

            self._open_die_height_max_before_working_stroke()
            self._open_die_height_min_after_working_stroke()
            self._working_stroke()
            self._working_approaching_stroke()
            self._idle_stroke()
            self._back_stroke()
            self._open_die_height_before_idle_stroke()

            self.time_between_bites()
            self.time_before_pass()
            self.time_bite_working()
            self.cycle_time()
            self.total_time()
            self.total_time_minutes()

            self.simulation_expected_duration_days_for_prolongation()
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()

    def add_operation_64_radial_forging_gfm(self):
        """Calculates a 'heating' and returns a dict."""
        row, i = self.output, self.eo
        try:

            row.at[i, 'operation_type'] = 'Draw'
            # row.at[i, 'step_control'] = 'Feed'  # ['Feed', 'StepsNum', 'OneStrictly', 'Three(Mid+L+R)', 'OneOrThree']
            row.at[i, 'deformation_control'] = 'H'  # ['E', 'P', 'H']
            row.at[i, 'k1'] = None
            row.at[i, 'press_mode_id'] = self.press_mode_id()
            row.at[i, 'mesh_elements'] = row.at[i - 1, 'mesh_elements']
            row.at[i, 'material_id'] = row.at[i - 1, 'material_id']

            self._angle()
            self._final_height()

            self._osp_radial_initial_rotations()
            self._osp_radial_accumulated_billet_rotation()
            self._osp_radial_rotations()

            self._initial_basis()
            self._final_basis()
            self._initial_3d_stl__and__temporary_trimesh_obj()
            self._initial_dimensions()
            self._initial_polygon___as_convex_hull_of_trimesh_xy_projection()

            # ------------------ READ OPERATION SPECIFIC PARAMETERS --------------------------
            rotation_per_bite = self.accumulated.loc[self.input_index, 'rotation_per_bite']
            diameter = self.accumulated.loc[self.input_index, 'diameter']

            # ------------------ ASSERT OPERATION SPECIFIC PARAMETERS --------------------------
            assert -180.0 < rotation_per_bite < 180.0, (f"Rotation per bite is {rotation_per_bite}°, "
                                                        f"but it must be between -180° and 180°.")
            assert diameter > 0.0, f"Final diameter is {diameter} mm, but it must be greater than 0.0 mm."

            # ------------------ RECORD OPERATION SPECIFIC PARAMETERS --------------------------
            osp = row.at[i, 'operation_specific_parameters']
            osp['rotation_per_bite'] = rotation_per_bite
            osp['diameter'] = diameter
            osp['rotations_count_per_feed_list'] = (0, 0, 0)
            # -------------------------------------------------------------------------------------------

            self.initial_cross_section_area()
            self.initial_height_to_width_ratio()
            self.initial_surface_area()
            self.initial_volume()
            self.initial_weight()

            die_ids = [row.at[i, 'top_die_id'],
                       row.at[i, 'bottom_die_id'],
                       row.at[i, 'plus_y_die_id'],
                       row.at[i, 'minus_y_die_id']]
            die_template_file_name = config.lib['die']['die_template_file_name'][die_ids].to_list()

            dies_polygons = []
            for zip_file_name in die_template_file_name:
                stl_file_name: str = zip_file_name.replace('.zip', '.stl')
                dies_data_dir: str = config.server['data_files_dies']
                die_abs_path = os.path.join(dies_data_dir, stl_file_name)
                _2d_contour = import_3d_stl_intersect_by_xy_plane_return_2d_polygon(die_abs_path, i)
                dies_polygons.append(_2d_contour)

            self._final_height()
            # self.set_stage_name()
            # self.set_max_temperature()

            # self.set_speed()

            self.set_nominal_feeds_for_spiral_prolongation()
            self._bites_table()

            self._num_of_bites()

            # --------------------------------
            ini_billet_polygon = row.at[i, 'TEMPORARY.initial_polygon']
            initial_dies_gap, ini_dies_polygons = gap_between_dies(ini_billet_polygon, dies_polygons)
            # _plot_multy_polygons([ini_billet_polygon] + ini_dies_polygons)

            final_shape = Point((0.0, 0.0)).buffer(diameter / 2)
            final_dies_gap, fin_dies_polygons = gap_between_dies(final_shape, dies_polygons)
            # _plot_multy_polygons([final_shape] + fin_dies_polygons)

            op_param = {

                'initial_dies_gap': initial_dies_gap,
                'initial_top_die_reference_point_z_coord': ini_dies_polygons[0].bounds[1],
                'initial_bottom_die_reference_point_z_coord': ini_dies_polygons[1].bounds[3],

                'final_dies_gap': final_dies_gap,
                'final_top_die_reference_point_z_coord': fin_dies_polygons[0].bounds[1],
                'final_bottom_die_reference_point_z_coord': fin_dies_polygons[1].bounds[3]
            }
            row.at[i, 'operation_specific_parameters'].update(op_param)
            # self.prolongation_input_h_return_p_and_e()

            penetration = initial_dies_gap - final_dies_gap

            if penetration > 0:
                row.at[i, 'penetration'] = penetration
                row.at[i, 'relative_deformation'] = penetration / row.at[i, 'initial_height'] * 100.0
            else:
                row.at[i, 'penetration'] = 0.0
                row.at[i, 'relative_deformation'] = 0.0

            row.at[i, 'initial_width_of_contact'] = 1.0
            # self._initial_width_of_contact(dies_polygons)

            self._initial_length_of_contact()

            # self.prolongation_final_length_of_contact()
            row.at[i, 'final_length_of_contact'] = row.at[i, 'feed_first']

            # -------------------------------------- FINAL POLYGON ------------------------------------------
            # self.prolongation_spiral_type_50_final_polygon(ini_billet_polygon, initial_dies_gap, ini_dies_polygons,
            #                                                final_shape, final_dies_gap, fin_dies_polygons)
            row.at[i, 'final_width_of_contact'] = 0.5 * diameter
            row.at[i, 'final_cross_section_area'] = final_shape.area
            row.at[i, 'final_polygon'] = polygon_to_binary(final_shape)
            row.at[i, 'TEMPORARY.final_polygon'] = final_shape

            # --------------------------------------- STRAIN X, Y, Z ---------------------------------------
            # self.prolongation_final_strain_height()
            # self.prolongation_final_strain_length_and_width()
            _strain_length = math.log(row.at[i, 'initial_cross_section_area'] / row.at[i, 'final_cross_section_area'])
            _strain_radial = -0.5 * _strain_length
            row.at[i, 'strain_length'] = _strain_length
            row.at[i, 'strain_height'] = _strain_radial
            row.at[i, 'strain_width'] = _strain_radial

            self._final_3d_stl()
            self._final_dimensions()
            # self.final_cross_section_area()
            self.final_height_to_width_ratio()
            self.final_surface_area()
            self.final_volume()
            self.final_weight()

            self.equivalent_diameter()
            self.elongation_channel()
            self.strain_accumulated_channel()

            self.limit_speed_by_press_working_speed()

            self._open_die_height_max_before_working_stroke()
            self._open_die_height_min_after_working_stroke()
            self._working_stroke()
            self._working_approaching_stroke()
            self._idle_stroke()
            self._back_stroke()
            self._open_die_height_before_idle_stroke()

            self.time_between_bites()
            self.time_before_pass()
            self.time_bite_working()
            self.cycle_time()
            self.total_time()
            self.total_time_minutes()

            self.simulation_expected_duration_days_for_prolongation()
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()

    def dies_cross_section_polygons(self) -> list[Polygon]:
        row, i = self.output, self.eo
        try:
            die_ids = [row.at[i, 'top_die_id'], row.at[i, 'bottom_die_id']]
            die_template_file_name = config.lib['die']['die_template_file_name'][die_ids].to_list()
            dies_polygons = []
            for zip_file_name in die_template_file_name:
                stl_file_name: str = zip_file_name.replace('.zip', '.stl')
                dies_data_dir: str = config.server['data_files_dies']
                die_abs_path = os.path.join(dies_data_dir, stl_file_name)
                _2d_contour = import_3d_stl_intersect_by_xy_plane_return_2d_polygon(die_abs_path, i)
                dies_polygons.append(_2d_contour)
            return dies_polygons
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._set_is_ready_false()
            return []

    def _final_polygon_and_trimesh_obj(self, dies_polygons):
        row, i = self.output, self.eo
        try:

            initial_polygon = row.at[i, 'TEMPORARY.initial_polygon']
            initial_trimesh_obj= row.at[i, 'TEMPORARY.initial_trimesh_obj']
            initial_length = row.at[i, 'initial_length']
            initial_width = row.at[i, 'initial_width']
            initial_height = row.at[i, 'initial_height']
            final_height = row.at[i, 'final_height']
            penetration = row.at[i, 'penetration']
            final_length_of_contact = row.at[i, 'final_length_of_contact']
            strain_height = row.at[i, 'strain_height']

            initial_basis = np.array(row.at[i, 'initial_basis'])
            final_basis = np.array(row.at[i, 'final_basis'])

            initial_cross_section_area = row.at[i, 'initial_cross_section_area']

            # ============================= OUTPUT FUNCTION ================================================

            def _save_output(_dimensions_trimesh_obj, _final_trimesh_obj, _polygon, _final_width_of_contact, _vertical_scale_factor, _ini_x_extending, _strain_length, _strain_width):

                row.at[i, 'TEMPORARY.final_trimesh_obj_in_initial_basis'] = _dimensions_trimesh_obj

                row.at[i, 'TEMPORARY.final_trimesh_obj'] = _final_trimesh_obj
                row.at[i, 'final_3d_stl'] = convert_trimesh_object_to_memory_buffer_object(_final_trimesh_obj)

                row.at[i, 'TEMPORARY.final_polygon'] = _polygon
                row.at[i, 'final_polygon'] = polygon_to_binary(_polygon)

                row.at[i, 'final_width_of_contact'] = _final_width_of_contact

                row.at[i, 'TEMPORARY.y_scale_factor'] = _vertical_scale_factor
                row.at[i, 'TEMPORARY.x_polygon_widening'] = _ini_x_extending

                row.at[i, 'strain_length'] = _strain_length
                row.at[i, 'strain_width'] = _strain_width

            # ============================= NO DEFORMATION =================================================

            if abs(height_of_polygon(initial_polygon) / final_height - 1) < 0.0002:
                _transformation_matrix = trimesh_basis_to_basis_transformation_matrix(initial_basis, final_basis)
                _final_trimesh_obj = initial_trimesh_obj.copy()
                _final_trimesh_obj.apply_transform(_transformation_matrix)
                # _output_polygon: Polygon = intersect_3d_mesh_by_2d_plane(mesh_stl=_final_trimesh_obj,
                #                                                          plane_normal=[1, 0, 0],
                #                                                          output_polygon_y_axis=[0, 1, 0],
                #                                                          eo=i)
                _save_output(
                    _dimensions_trimesh_obj = initial_trimesh_obj,
                    _final_trimesh_obj = _final_trimesh_obj,
                    _polygon = initial_polygon,
                    _final_width_of_contact = 0.0,
                    _vertical_scale_factor = 1.0,
                    _ini_x_extending = 0.0,
                    _strain_length = 0.0,
                    _strain_width = 0.0
                )
                return

            # ============================= Y SCALE FACTOR =================================================
            # TODO: Distance between top and bottom dies are 0.6 mm less than 'final_height'
            _die_top, _die_bottom = dies_polygons
            vertical_scale_factor = polygon_y_scale_factor(initial_polygon, _die_top, _die_bottom, initial_width, initial_height, penetration)

            # ============================= FINAL WIDTH OF CONTACT =========================================

            _y_scaled_polygon = scale(initial_polygon, xfact=1.0, yfact=vertical_scale_factor, origin=(0, 0, 0))

            assert not _y_scaled_polygon.is_empty, "Polygon after Y-scale is empty"

            area_except_middle, _split_lines, _split_polygons, _gaps = trim_middle_return_residual_area(_y_scaled_polygon, _die_top, _die_bottom, final_height)

            _width_of_contact_initial_guess: float = _gaps[0]

            # ==========================================================================================================
            def _final_width_of_contact__rough_eval():
                _, _strain_length_contact = strain_length_based_on_contact_shape(_width_of_contact_initial_guess, final_length_of_contact, initial_width, initial_height, strain_height)
                _final_cross_section_area__initial_guess = initial_cross_section_area /  math.exp(_strain_length_contact)
                return (_final_cross_section_area__initial_guess - area_except_middle) / final_height

            final_width_of_contact__roughly = _final_width_of_contact__rough_eval()
            # ==========================================================================================================

            iteration = [0]
            _optimization_function = optimize.minimize(fun=strain_error,
                                                       x0=np.array([final_width_of_contact__roughly]),
                                                       args=(area_except_middle, final_length_of_contact, strain_height, initial_width, initial_height, final_height, initial_cross_section_area, iteration, self.eo),
                                                       tol=1e-3)
            final_width_of_contact: float = _optimization_function.x.item(0)

            # ============================= PROLONGATION FINAL POLYGON =====================================

            boundary_list = translate_geoms_increase_gap(_width_of_contact_initial_guess, _split_lines)
            _middle_polygon = middle_polygon_fill_gap(boundary_list, final_width_of_contact)

            polygon_list = translate_geoms_increase_gap(_width_of_contact_initial_guess, _split_polygons)
            _output_polygons = translate_polygons_after_optimization(polygon_list, final_width_of_contact)

            output_polygon_collection: list[Polygon] = [*_output_polygons[0], _middle_polygon, *_output_polygons[1]]
            output_polygon_collection_sorted_by_x_coord = sorted(output_polygon_collection, key=lambda out_pol: out_pol.centroid.x, reverse=False)

            def polygon_dimensions(_p: Polygon) -> tuple[float, float]:
                _b = _p.bounds
                _x = _b[2] - _b[0]
                _y = _b[3] - _b[1]
                return _x, _y

            def trimesh_dimensions(_t: Trimesh) -> np.ndarray:
                _b = _t.bounds
                _dimensions = _b[1, :] - _b[0, :]
                return _dimensions

            def _combine_list_of_polygons(input_list_of_polygons, tolerance_mm):
                polygon_with_positive_offset = union_all([_p.buffer(tolerance_mm) for _p in input_list_of_polygons])
                polygon_with_negative_offset = polygon_with_positive_offset.buffer(-tolerance_mm)
                return polygon_with_negative_offset

            def _join_polygons(list_of_polygons):
                _min_dim = min([min(polygon_dimensions(out_pol)) for out_pol in list_of_polygons])
                #
                tolerance_factor, tolerance_steps = 1E-4, 10
                tolerance_values = [_min_dim * tolerance_factor * multiplication_factor ** 2 for multiplication_factor in range(1, tolerance_steps + 1)]
                #
                joined_polygons = _combine_list_of_polygons(list_of_polygons, tolerance_values[0])
                if not isinstance(joined_polygons, Polygon):
                    for next_tolerance_value in tolerance_values[1:]:
                        joined_polygons = _combine_list_of_polygons(list_of_polygons, next_tolerance_value)
                        if isinstance(joined_polygons, Polygon):
                            break
                return joined_polygons

            def _is_acceptable_area_error(_single_polygon: Polygon, _list_of_polygons: list[Polygon]) -> bool:
                total_area_of_polygons = sum([out_pol.area for out_pol in _list_of_polygons])
                area_error = 100 * abs(1 - _single_polygon.area / total_area_of_polygons)
                area_error_limit = 1E-2  # percent
                return area_error <= area_error_limit

            # ============================= FINAL OUTPUT POLYGON ===========================================

            output_polygon = _join_polygons(output_polygon_collection_sorted_by_x_coord)
            assert isinstance(output_polygon, Polygon), f"Can't convert polygon to list of coordinates. Type must be Polygon, but {type(output_polygon)} received."
            assert _is_acceptable_area_error(output_polygon, output_polygon_collection_sorted_by_x_coord), f"Error of area modification is more than allowed error"

            # ============================= FINAL CROSS-SECTION AREA =======================================

            final_cross_section_area: float = output_polygon.area
            assert final_cross_section_area > 0.0, f"ValueError: 'final_cross_section_area' should be above zero, but {final_cross_section_area}."

            # ============================= ROUNDED STRAIN =================================================

            def _rounded_strain(_strain) -> float:
                if not isinstance(_strain, float):
                    _strain = float(_strain)
                if _strain == 0.0:
                    return 0.0
                strain_accuracy_order = 4 - int(math.log10(abs(_strain)))
                return round(_strain, strain_accuracy_order)

            # ============================= FINAL STRAIN LENGTH ============================================

            strain_length: float = math.log(initial_cross_section_area / final_cross_section_area)
            assert _rounded_strain(strain_length) >= 0.0, f"ValueError: 'strain_length' should be positive or zero, but {strain_length}"

            # ============================= FINAL STRAIN WIDTH =============================================

            strain_width: float = 0 - strain_height - strain_length
            assert _rounded_strain(strain_width) >= 0.0, f"ValueError: 'strain_width' should be positive or zero, but {strain_width}"

            # ============================= VERTICAL SCALE OF TRIMESH OBJECT ===============================

            scale_matrix = np.eye(4)
            scale_matrix[2, 2] *= vertical_scale_factor
            vertically_scaled_initial_trimesh_obj = initial_trimesh_obj.copy().apply_transform(scale_matrix)

            # ============================= DIES TRIMESH ===================================================

            outer_dies_bounds = np.multiply(1.1, vertically_scaled_initial_trimesh_obj.bounds)
            top_die_bounds, bottom_die_bounds = outer_dies_bounds.copy(), outer_dies_bounds.copy()
            top_die_bounds[0, 2] = _die_top.bounds[1]
            bottom_die_bounds[1, 2] = _die_bottom.bounds[3]
            _die_top_trimesh, _die_bottom_trimesh = creation.box(bounds=top_die_bounds), creation.box(bounds=bottom_die_bounds)

            # ============================= BOOLEAN EXTRACT OF DIES FROM BILLET ============================

            trimesh_obj_cut = boolean.difference(meshes=(
                boolean.difference(meshes=(vertically_scaled_initial_trimesh_obj, _die_top_trimesh)),
                _die_bottom_trimesh))

            # ============================= WIDENING OF TRIMESH OBJECT =====================================

            def _extending_trimesh_obj_along_axis(_trimesh_obj: Trimesh, _abs_extension: float | np.float64, _axis_name: str) -> Trimesh:
                _axis_index = {'x': 0, 'y': 1, 'z': 2}[_axis_name]
                _half_ext: np.float64 = np.float64(_abs_extension / 2)
                t = _trimesh_obj.copy()
                v = t.vertices.view(np.ndarray)  # [x, y, z] coordinates of vertices
                v[:, _axis_index] = np.where(v[:, _axis_index] >= 0, v[:, _axis_index] + _half_ext, v[:, _axis_index] - _half_ext)
                return t

            y_polygon_widening: float = final_width_of_contact - _width_of_contact_initial_guess
            widened_trimesh_obj = _extending_trimesh_obj_along_axis(trimesh_obj_cut, y_polygon_widening, 'y')

            # ============================= LENGTHENING OF TRIMESH OBJECT ==================================

            def _trimesh_volumes_difference(_abs_extension: np.ndarray, _widened_trimesh_obj: Trimesh, _initial_volume: np.float64) -> np.float64:
                try:
                    assert isinstance(_abs_extension, np.ndarray), "Optimized variable 'abs_extension' must be np.ndarray"
                    _abs_extension_scalar: np.float64 = _abs_extension[0]
                    new_trimesh_obj: Trimesh = _extending_trimesh_obj_along_axis(_widened_trimesh_obj, _abs_extension_scalar, 'x')
                    volume_relative_error: np.float64 = abs(1 - new_trimesh_obj.volume / _initial_volume)
                    return volume_relative_error
                except Exception:
                    return np.float64(1E6)

            # v = [
            #     initial_trimesh_obj.volume,
            #     vertically_scaled_initial_trimesh_obj.volume,
            #     trimesh_obj_cut.volume,
            #     widened_trimesh_obj.volume]
            #
            # vr = np.multiply(1 / v[0], np.array(v)).tolist()
            #
            # d = [
            #     trimesh_dimensions(initial_trimesh_obj),
            #     trimesh_dimensions(vertically_scaled_initial_trimesh_obj),
            #     trimesh_dimensions(trimesh_obj_cut),
            #     trimesh_dimensions(widened_trimesh_obj)]

            ini_x_extending: np.float64 = initial_length * (initial_cross_section_area / final_cross_section_area - 1)
            _optimization_function = optimize.minimize(fun=_trimesh_volumes_difference,
                                                       x0=np.array([ini_x_extending]),
                                                       args=(widened_trimesh_obj, initial_trimesh_obj.volume),
                                                       tol=1e-4)
            final_x_extending: float = _optimization_function.x.item(0)
            final_trimesh_obj_in_initial_basis = _extending_trimesh_obj_along_axis(widened_trimesh_obj, final_x_extending, 'x')

            # ============================= ROTATION OF FINAL TRIMESH OBJ INTO FINAL BASIS =================

            transformation_matrix = trimesh_basis_to_basis_transformation_matrix(initial_basis, final_basis)
            final_trimesh_obj = final_trimesh_obj_in_initial_basis.copy()
            final_trimesh_obj.apply_transform(transformation_matrix)

            # ===================================== OUTPUT ============================================

            # plot_trimesh_object(convert_stl_binary_object_to_trimesh_object(self.get_previous_out('final_3d_stl')), "INITIAL_BEFORE", i)
            # plot_trimesh_object(initial_trimesh_obj, "INITIAL_IN_INI_BASIS", i)
            # plot_trimesh_object(final_trimesh_obj_in_initial_basis, "FINAL_IN_INI_BASIS", i)
            # plot_trimesh_object(final_trimesh_obj, "FINAL_IN_FINAL_BASIS", i)

            _save_output(
                _dimensions_trimesh_obj=final_trimesh_obj_in_initial_basis,
                _final_trimesh_obj=final_trimesh_obj,
                _polygon=output_polygon,
                _final_width_of_contact=final_width_of_contact,
                _vertical_scale_factor=vertical_scale_factor,
                _ini_x_extending=ini_x_extending,
                _strain_length=strain_length,
                _strain_width=strain_width
            )

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _y_scale_factor(self, dies_polygons):
        row, i = self.output, self.eo
        try:
            input_polygon = row.at[i, 'TEMPORARY.initial_polygon']
            initial_width = row.at[i, 'initial_width']
            initial_height = row.at[i, 'initial_height']
            final_height = row.at[i, 'final_height']
            penetration = row.at[i, 'penetration']

            if height_of_polygon(input_polygon) <= final_height:
                y_scale_factor = 1.0
            else:
                _die_top, _die_bottom = dies_polygons
                y_scale_factor = polygon_y_scale_factor(input_polygon, _die_top, _die_bottom, initial_width, initial_height, penetration)

            row.at[i, 'TEMPORARY.y_scale_factor'] = y_scale_factor
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _final_width_of_contact(self, dies_polygons):
        row, i = self.output, self.eo
        try:
            input_polygon = row.at[i, 'TEMPORARY.initial_polygon']
            initial_width = row.at[i, 'initial_width']
            initial_height = row.at[i, 'initial_height']
            final_height = row.at[i, 'final_height']
            final_length_of_contact = row.at[i, 'final_length_of_contact']
            strain_height = row.at[i, 'strain_height']
            y_scale_factor = row.at[i, 'TEMPORARY.y_scale_factor']

            if height_of_polygon(input_polygon) <= final_height:
                _width_of_contact_initial_guess = 0.0
                final_width_of_contact = 0.0
            else:
                _die_top, _die_bottom = dies_polygons
                _y_scaled_polygon = scale(input_polygon, xfact=1.0, yfact=y_scale_factor, origin=(0, 0, 0))
                area_except_middle, _split_lines, _split_polygons, _gaps = trim_middle_return_residual_area(_y_scaled_polygon, _die_top, _die_bottom, final_height)
                area_initial = input_polygon.area
                _width_of_contact_initial_guess: float = _gaps[0]
                _optimization_function = optimize.minimize(fun=strain_error,
                                                           x0=np.array([_width_of_contact_initial_guess]),
                                                           args=(
                                                               area_except_middle,
                                                               final_length_of_contact,
                                                               strain_height,
                                                               initial_width,
                                                               initial_height,
                                                               final_height,
                                                               area_initial),
                                                           tol=1e-3)
                final_width_of_contact = _optimization_function.x.item(0)

            row.at[i, 'final_width_of_contact'] = final_width_of_contact
            row.at[i, 'TEMPORARY.x_polygon_widening'] = _width_of_contact_initial_guess - final_width_of_contact
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _prolongation_final_polygon(self, dies_polygons):
        row, i = self.output, self.eo
        try:
            input_polygon = row.at[i, 'TEMPORARY.initial_polygon']
            final_height = row.at[i, 'final_height']
            final_width_of_contact = row.at[i, 'final_width_of_contact']
            y_scale_factor = row.at[i, 'TEMPORARY.y_scale_factor']

            if height_of_polygon(input_polygon) <= final_height:
                    return

            _die_top, _die_bottom = dies_polygons

            _y_scaled_polygon = scale(input_polygon, xfact=1.0, yfact=y_scale_factor, origin=(0, 0, 0))

            assert not _y_scaled_polygon.is_empty, "Polygon after Y-scale is empty"

            area_except_middle, _split_lines, _split_polygons, _gaps = trim_middle_return_residual_area(_y_scaled_polygon, _die_top, _die_bottom, final_height)

            boundary_list = translate_geoms_increase_gap(_gaps[0], _split_lines)
            polygon_list = translate_geoms_increase_gap(_gaps[0], _split_polygons)

            _middle_polygon = middle_polygon_fill_gap(boundary_list, final_width_of_contact)
            _output_polygons = translate_polygons_after_optimization(polygon_list, final_width_of_contact)

            _p_1: list[Polygon] = [*_output_polygons[0], _middle_polygon, *_output_polygons[1]]
            _p_2 = sorted(_p_1, key=lambda _p_s: _p_s.centroid.x, reverse=False)
            _p_2_area = sum([_o_p.area for _o_p in _p_2])

            _min_dim = min([min(_p_2i.bounds[3] - _p_2i.bounds[1],
                                _p_2i.bounds[2] - _p_2i.bounds[0]
                                ) for _p_2i in _p_2
                            ])
            _start = math.sqrt(0.0001 * _min_dim)
            _end = math.sqrt(0.01 * _min_dim)
            _steps = 10
            _tol_values = [_value ** 2
                           for _value
                           in [_start + i * (_end - _start) / (_steps - 1) for i in range(_steps)]
                           ]

            def _combine_list_of_polygons(_tol_mm):
                return union_all([_p_2i.buffer(_tol_mm) for _p_2i in _p_2]).buffer(-_tol_mm)

            output_polygon = _combine_list_of_polygons(_tol_values[0])
            if not isinstance(output_polygon, Polygon):
                for _tol_value in _tol_values[1:]:
                    output_polygon = _combine_list_of_polygons(_tol_value)
                    if isinstance(output_polygon, Polygon):
                        break

            # ------------------- ASSERT ------------------------------
            assert isinstance(output_polygon, Polygon), (f"Can't convert polygon to list of coordinates. "
                                                         f"Type must be Polygon, but {type(output_polygon)} received.")

            area_error_limit = 1E-2  # percent
            area_error = 100 * abs(1 - output_polygon.area / _p_2_area)
            assert area_error <= area_error_limit, \
                f"Error of area modification is more than allowed error {area_error:.2g}% > {area_error_limit:.2g}%."

            row.at[i, 'TEMPORARY.final_polygon'] = output_polygon
            row.at[i, 'final_polygon'] = polygon_to_binary(output_polygon)

            row.at[i, 'TEMPORARY.y_scale_factor'] = y_scale_factor
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            # plot_queue.put((output_polygon,))
            raise RuntimeError("FAILED 2D-geometry creation of final polygon")

    def add_operation_52_full_die_simple(self):
        """Calculates a 'heating' and returns a dict."""
        row, i = self.output, self.eo
        try:
            row.at[i, 'operation_type'] = 'FullDie'
            # 'step_control': ['Feed', 'StepsNum', 'OneStrictly', 'Three(Mid+L+R)', 'OneOrThree']
            # row.at[i, 'step_control'] = 'OneStrictly'
            row.at[i, 'deformation_control'] = 'H'  # ['E', 'P', 'H']
            row.at[i, 'k1'] = None
            row.at[i, 'press_mode_id'] = self.press_mode_id()
            row.at[i, 'mesh_elements'] = row.at[i - 1, 'mesh_elements']
            row.at[i, 'material_id'] = row.at[i - 1, 'material_id']

            self._angle()
            self._final_height()

            self._osp_radial_initial_rotations()
            self._osp_radial_accumulated_billet_rotation()
            self._osp_radial_rotations()

            self._initial_basis()
            self._final_basis()
            self._initial_3d_stl__and__temporary_trimesh_obj()
            self._initial_dimensions()
            self._initial_polygon___as_convex_hull_of_trimesh_xy_projection()

            # ---------------

            self.initial_cross_section_area()
            self.initial_height_to_width_ratio()
            self.initial_surface_area()
            self.initial_volume()
            self.initial_weight()
    
            self.prolongation_input_h_return_p_and_e()
            row.at[i, 'num_of_bites'] = 1
            self._initial_width_of_contact()
            self._initial_length_of_contact()
    
            self.prolongation_final_strain_height()
            row.at[i, 'final_length_of_contact'] = row.at[i, 'initial_length']
            self.full_die_final_polygon()
            self.prolongation_final_strain_length_and_strain_width()
    
            self._final_3d_stl()
            self._final_dimensions()
            self.final_cross_section_area()
            self.final_height_to_width_ratio()
            self.final_surface_area()
            self.final_volume()
            self.final_weight()
    
            self.equivalent_diameter()
            self.elongation_channel()
            self.strain_accumulated_channel()

            self.limit_speed_by_press_working_speed()

            self._open_die_height_max_before_working_stroke()
            self._open_die_height_min_after_working_stroke()
            self._working_stroke()
            self._working_approaching_stroke()
            self._idle_stroke()
            self._back_stroke()
            self._open_die_height_before_idle_stroke()

            self.time_between_bites()
            self.time_before_pass()
            self.time_bite_working()
            self.cycle_time()
            self.total_time()
            self.total_time_minutes()
    
            self.simulation_expected_duration_days_for_prolongation()
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()

    def add_operation_57_hot_cut_percentage(self):
        """Calculates a 'heating' and returns a dict."""
        row, i = self.output, self.eo
        try:
            previous_width = row.at[i - 1, 'final_width']
            previous_height = row.at[i - 1, 'final_height']
    
            previous_final_cross_section_area = row.at[i - 1, 'final_cross_section_area']
            previous_final_height_to_width_ratio = row.at[i - 1, 'final_height_to_width_ratio']
    
            row.at[i, 'operation_type'] = 'Cut'
            # 'step_control': ['Feed', 'StepsNum', 'OneStrictly', 'Three(Mid+L+R)', 'OneOrThree']
            # row.at[i, 'step_control'] = 'StepsNum'
            row.at[i, 'deformation_control'] = 'P'  # ['E', 'P', 'H']
            row.at[i, 'k1'] = None
            row.at[i, 'press_mode_id'] = self.press_mode_id()
            row.at[i, 'mesh_elements'] = row.at[i - 1, 'mesh_elements']

            row.at[i, 'material_id'] = row.at[i - 1, 'material_id']

            row.at[i, 'strain_length'] = 0.0
            row.at[i, 'strain_height'] = 0.0
            row.at[i, 'strain_width'] = 0.0
            row.at[i, 'penetration'] = 0.0
            row.at[i, 'relative_deformation'] = 0.0

            row.at[i, 'initial_length_of_contact'] = 0.0
            row.at[i, 'initial_width_of_contact'] = 0.0
            row.at[i, 'final_length_of_contact'] = 0.0
            row.at[i, 'final_width_of_contact'] = 0.0

            row.at[i, 'initial_height'] = previous_height
            row.at[i, 'initial_width'] = previous_width
            row.at[i, 'initial_length'] = row.at[i - 1, 'final_length']

            row.at[i, 'initial_cross_section_area'] = previous_final_cross_section_area
            row.at[i, 'initial_height_to_width_ratio'] = previous_final_height_to_width_ratio
            row.at[i, 'initial_surface_area'] = row.at[i - 1, 'final_surface_area']
            row.at[i, 'volume_initial'] = row.at[i - 1, 'volume_final']
            row.at[i, 'final_weight'] = row.at[i - 1, 'final_weight']

            row.at[i, 'final_cross_section_area'] = previous_final_cross_section_area
            row.at[i, 'final_height_to_width_ratio'] = previous_final_height_to_width_ratio

            row.at[i, 'final_height'] = previous_height
            row.at[i, 'final_width'] = previous_width

            row.at[i, 'elongation_channel_a'] = row.at[i - 1, 'elongation_channel_a']
            row.at[i, 'elongation_channel_b'] = row.at[i - 1, 'elongation_channel_b']
            row.at[i, 'strain_accumulated_channel_a'] = row.at[i - 1, 'strain_accumulated_channel_a']
            row.at[i, 'strain_accumulated_channel_b'] = row.at[i - 1, 'strain_accumulated_channel_b']

            row.at[i, 'equivalent_diameter'] = row.at[i - 1, 'equivalent_diameter']

            row.at[i, 'initial_basis'] = row.at[i - 1, 'final_basis']
            row.at[i, 'final_basis'] = row.at[i - 1, 'final_basis']

            xy_coord = row.at[i - 1, 'final_polygon']
            _p = Polygon(xy_coord)
            row.at[i, 'initial_polygon'] = xy_coord
            row.at[i, 'TEMPORARY.initial_polygon'] = _p
            row.at[i, 'TEMPORARY.final_polygon'] = _p

            row.at[i, 'initial_3d_stl'] = row.at[i - 1, 'final_3d_stl']
            row.at[i, 'TEMPORARY.initial_trimesh_obj'] = convert_stl_binary_object_to_trimesh_object(row.at[i, 'initial_3d_stl'])

            row.at[i, 'angle'] = 0.0

            # ---------------

            self._cutting_scrap_rate()
            self._final_volume_cutting()
            self._cutting_final_length()
            self._num_of_bites()
            # self.set_stage_name()
            # self.set_max_temperature()

            final_trimesh_obj = polygon_to_3d_trimesh_object(_p, row.at[i, 'final_length'])
            row.at[i, 'TEMPORARY.final_trimesh_obj'] = final_trimesh_obj
            row.at[i, 'final_3d_stl'] = convert_trimesh_object_to_memory_buffer_object(final_trimesh_obj)

            self.final_surface_area()
            self.final_weight()

            self.limit_speed_by_press_working_speed()

            self._open_die_height_max_before_working_stroke()
            self._open_die_height_min_after_working_stroke()
            self._working_stroke()
            self._working_approaching_stroke()
            self._idle_stroke()
            self._back_stroke()
            self._open_die_height_before_idle_stroke()

            self.time_between_bites()
            self.time_before_pass()
            self.time_bite_working()
            self.cycle_time()
            self.total_time()
            self.total_time_minutes()

            row.at[i, 'simulation_expected_duration_days'] = 0.0
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()

    def add_operation_86_cold_sawing_percentage(self):
        """Calculates a 'heating' and returns a dict."""
        row, i = self.output, self.eo
        try:
            row.at[i, 'operation_type'] = 'Cut'
            # 'step_control': ['Feed', 'StepsNum', 'OneStrictly', 'Three(Mid+L+R)', 'OneOrThree']
            # row.at[i, 'step_control'] = 'StepsNum'
            row.at[i, 'deformation_control'] = 'P'  # ['E', 'P', 'H']
            row.at[i, 'k1'] = None
            row.at[i, 'press_mode_id'] = self.press_mode_id()
            row.at[i, 'mesh_elements'] = row.at[i - 1, 'mesh_elements']
            row.at[i, 'material_id'] = row.at[i - 1, 'material_id']
            row.at[i, 'angle'] = 0.0

            pieces_count = self.accumulated.loc[self.input_index, 'pieces_count'].item()
            piece_number = self.accumulated.loc[self.input_index, 'piece_number'].item()
            percentage_to_keep = self.accumulated.loc[self.input_index, 'percentage_to_keep'].item()

            assert isinstance(row.at[i, 'operation_specific_parameters'], dict), \
                f"row.at[i, 'operation_specific_parameters'] is not a dict"
            row.at[i, 'operation_specific_parameters'].update({
                'pieces_count': pieces_count,
                'piece_number': piece_number,
                'percentage_to_keep': percentage_to_keep})

            previous_width = row.at[i - 1, 'final_width']
            previous_height = row.at[i - 1, 'final_height']
    
            previous_temporary_final_polygon = row.at[i - 1, 'TEMPORARY.final_polygon']
            previous_final_polygon = row.at[i - 1, 'final_polygon']
    
            previous_final_cross_section_area = row.at[i - 1, 'final_cross_section_area']
            previous_final_height_to_width_ratio = row.at[i - 1, 'final_height_to_width_ratio']

            row.at[i, 'strain_length'] = 0.0
            row.at[i, 'strain_height'] = 0.0
            row.at[i, 'strain_width'] = 0.0
            row.at[i, 'penetration'] = 0.0
            row.at[i, 'relative_deformation'] = 0.0

            row.at[i, 'initial_length_of_contact'] = 0.0
            row.at[i, 'initial_width_of_contact'] = 0.0
            row.at[i, 'final_length_of_contact'] = 0.0
            row.at[i, 'final_width_of_contact'] = 0.0

            row.at[i, 'initial_polygon'] = previous_final_polygon
            row.at[i, 'TEMPORARY.initial_polygon'] = previous_temporary_final_polygon
            row.at[i, 'final_polygon'] = previous_final_polygon
            row.at[i, 'TEMPORARY.final_polygon'] = previous_temporary_final_polygon

            row.at[i, 'initial_height'] = previous_height
            row.at[i, 'initial_width'] = previous_width
            row.at[i, 'initial_length'] = row.at[i - 1, 'final_length']

            row.at[i, 'initial_cross_section_area'] = previous_final_cross_section_area
            row.at[i, 'initial_height_to_width_ratio'] = previous_final_height_to_width_ratio
            row.at[i, 'initial_surface_area'] = row.at[i - 1, 'final_surface_area']
            row.at[i, 'volume_initial'] = row.at[i - 1, 'volume_final']
            row.at[i, 'initial_weight'] = row.at[i - 1, 'final_weight']

            row.at[i, 'final_cross_section_area'] = previous_final_cross_section_area
            row.at[i, 'final_height_to_width_ratio'] = previous_final_height_to_width_ratio

            row.at[i, 'final_height'] = previous_height
            row.at[i, 'final_width'] = previous_width

            row.at[i, 'elongation_channel_a'] = row.at[i - 1, 'elongation_channel_a']
            row.at[i, 'elongation_channel_b'] = row.at[i - 1, 'elongation_channel_b']
            row.at[i, 'strain_accumulated_channel_a'] = row.at[i - 1, 'strain_accumulated_channel_a']
            row.at[i, 'strain_accumulated_channel_b'] = row.at[i - 1, 'strain_accumulated_channel_b']

            row.at[i, 'equivalent_diameter'] = row.at[i - 1, 'equivalent_diameter']

            self._cutting_scrap_rate()
            self._final_volume_cutting()
            self._cutting_final_length()
            self._num_of_bites()
            # self.set_stage_name()
            # self.set_max_temperature()
    
            # self.set_speed()
    
            # self.upsetting_set_feed()
    
            self._final_3d_stl()
            self.final_surface_area()
            self.final_weight()
    
            self.time_between_bites()
            self.time_before_pass()
            self.time_bite_working()
            self.cycle_time()
            self.total_time()
            self.total_time_minutes()
    
            row.at[i, 'simulation_expected_duration_days'] = 0.0
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()

    def _upsetting_final_length(self):
        row, i = self.output, self.eo
        try:
            _final_length = self.accumulated.loc[self.input_index, 'height']

            assert _final_length > 0.0

            row.at[i, 'final_length'] = _final_length

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def set_penetration(self):
        row, i = self.output, self.eo
        try:
            match self.type_id:
                case 92:  # Tail flattening
                    penetration = self.accumulated.loc[self.input_index, 'stroke'].item()
                case 100:  # Tail chamfering
                    pp = row.at[i, 'operation_specific_parameters']['projections']
                    p1 = pp['height_to_length_projection']['axial_virtual_penetration']
                    p2 = pp['width_to_length_projection']['axial_virtual_penetration']
                    penetration = (p1 + p2) / 2
                case _:
                    raise ValueError(f"Unknown type_id: {self.type_id} for 'set_penetration' function.")

            assert penetration > 0.0, f"Penetration = {penetration}, but must be greater than 0.0."

            row.at[i, 'penetration'] = penetration

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._set_is_ready_false()

    def _final_height(self):
        row, i = self.output, self.eo
        try:
            if self.type_id in (46, 83, 90, 52, 64, 80, 82, 95, 96):
                _final_height = self.accumulated.loc[self.input_index, 'height']
            elif self.type_id in (50, 51):
                _final_height = self.accumulated.loc[self.input_index, 'diameter']
            else:
                raise ValueError(f"Unknown type_id: {self.type_id}")

            assert _final_height > 0.0, f"Final height = {_final_height}, but must be greater than 0.0."

            row.at[i, 'final_height'] = _final_height

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def set_stage_name(self):
        row, i = self.output, self.eo
        try:
            row.at[i, 'stage_name'] = self.accumulated.loc[self.input_index, 'stage_name']

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._set_is_ready_false()

    def set_max_temperature(self):
        row, i = self.output, self.eo
        try:
            max_t = self.input.loc[self.input_index - 1, 'max_temperature']

            assert pd.notna(max_t), f"Max temperature = {max_t}, but must be not NaN."
            assert max_t > 0.0, f"Max temperature = {max_t}, but must be greater than 0.0."

            row.at[i, 'max_temperature'] = max_t

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._set_is_ready_false()

    def convert_die_assembly_id_to_die_name(self, die_assembly_id: int) -> str:
        """Converts 'type_id_die_assembly_type' to 'die' name."""
        try:
            if die_assembly_id == 1 or die_assembly_id not in config.lib['die_assembly']['name'].keys():
                result = 'Error'
            else:
                result = config.lib['die_assembly']['name'][die_assembly_id]
            return result
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._set_is_ready_false()

    def _radial_prolongation_feed(self):
        row, i = self.output, self.eo
        try:
            if self.parent_type_id != 35:  # 35 - Radial prolongation
                return

            # ------------------------------------- FEED ------------------------------------------------
            if self.type_id in (80, 95):
                feed = self.get_acc('radial_feed')
                assert feed > 0.0, f"User entered Radial Feed {feed} mm, but it must be greater than 0.0 mm"
            elif self.type_id in (82, 96):
                _num_of_bites = self.get_acc('num_of_bites')
                assert _num_of_bites > 0, f"User entered Number of Bites {_num_of_bites}, but it must be greater than 0"
                feed = row.at[i, 'initial_length'] / _num_of_bites
            else:
                raise ValueError(f"Wrong value 'type_id'={self.type_id} (Allowed 'type_id' = 80, 82, 95, 96)")
            row.loc[i, ['feed_first', 'feed_middle', 'feed_last']] = np.array((feed, 0.0, 0.0))
            # -------------------------------------------------------------------------------------------
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._set_is_ready_false()

    def _upsetting_feed(self):
        row, i = self.output, self.eo
        try:
            min_die_working_length = self._max_working_length_of_dies()
            half_die_length = 0.5 * min_die_working_length

            billet_width = row.at[i, 'initial_height']
            first_feed_till_billet_center = 0.5 * billet_width + 0.5 * min_die_working_length

            # ('feed_first', 'feed_middle', 'feed_last')
            match self.type_id:
                case 93:  # Single upsetting
                    row.at[i, 'feed_first'] = first_feed_till_billet_center
                    assert_keys = ('feed_first', )

                case 91:  # Single OR triple upsetting with rotation
                    row.at[i, 'feed_first'] = first_feed_till_billet_center
                    assert_keys = ['feed_first']

                    if billet_width >= min_die_working_length:
                        row.at[i, 'feed_middle'] = half_die_length
                        row.at[i, 'feed_last'] = min_die_working_length
                        assert_keys.extend(['feed_middle', 'feed_last'])

                case 94:  # Triple upsetting
                    row.at[i, 'feed_first'] = first_feed_till_billet_center
                    row.at[i, 'feed_middle'] = half_die_length
                    row.at[i, 'feed_last'] = min_die_working_length
                    assert_keys = ('feed_first', 'feed_middle', 'feed_last')

                case 92:  # Tail flattening
                    average_feed = 200.0
                    average_num_of_bites = billet_width / average_feed
                    num_of_bites = max(2, round(average_num_of_bites))
                    feed = billet_width / num_of_bites
                    row.at[i, 'feed_first'] = feed
                    assert_keys = ('feed_first', )

                case 100:  # Tail chamfering
                    # It can be 4 or 8 bites for tail chamfering
                    row.at[i, 'feed_first'] = first_feed_till_billet_center
                    assert_keys = ['feed_first']

                    if billet_width >= min_die_working_length:
                        row.at[i, 'feed_middle'] = half_die_length
                        row.at[i, 'feed_last'] = min_die_working_length
                        assert_keys.extend(['feed_middle', 'feed_last'])

                case _:
                    raise ValueError(f"Unknown 'type_id': {self.type_id}")

            for key in assert_keys:
                assert pd.notna(row.at[i, key]), f"Key '{key}' is None."
                assert row.at[i, key] > 0.0, f"Key '{key}' is not positive."

            columns = pd.Index(('feed_middle', 'feed_last'))
            row.loc[[i], columns] = row.loc[[i], columns].fillna(0)

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    @staticmethod
    def convert_list(_list: list):
        if len(_list) == 1:
            return _list[0]
        return _list

    def at_accumulated_set_speed(self):
        """Sets 'speed'"""
        try:
            # Filter forming operations and speed columns only

            ol = config.lib['operations_library']
            _names = ol['speed_column_name']
            unique_legal_column_names = pd.Index(_names.loc[pd.notna(_names)].unique())
            type_ids = pd.Index(self.operations['type_id'])
            mask = pd.Index(ol.loc[type_ids, 'is_forming_operation'])
            accumulated_forming_operations = self.accumulated.loc[mask, unique_legal_column_names]

            # Select speed from many columns into one column 'speed'

            forming_operations_type_ids = pd.Index(self.operations.loc[accumulated_forming_operations.index, 'type_id'])
            speed_column_names = ol.loc[forming_operations_type_ids, 'speed_column_name']
            speed_column_names.index = accumulated_forming_operations.index
            speed_column_names_mask = (
                    np.reshape(speed_column_names.to_numpy(), (-1, 1))
                    ==
                    np.repeat(np.reshape(
                        unique_legal_column_names.to_numpy(), (1, -1)),
                        accumulated_forming_operations.shape[0],
                        axis=0)
            )
            speed = accumulated_forming_operations.where(speed_column_names_mask).bfill(axis=1).iloc[:, 0]
            self.accumulated.loc[speed.index, 'speed'] = speed

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()

    def _angle(self):
        try:
            match self.type_id:

                # UPSETTING
                case 91:
                    _angle: float = self.get_acc('angle')  # single or triple
                case 93:
                    _angle: float = self.get_acc('angle')  # single bite strictly
                case 94:
                    _angle: float = self.get_acc('angle')  # three bites (middle, then sides)
                case 92:
                    _angle: float = self.get_acc('angle')  # tail_flattening_with_rotation
                case 100:
                    _angle: float = self.get_acc('angle')  # tail_chamfering_rotation

                # AXIAL PROLONGATION
                case 46:
                    _angle: float = self.get_acc('angle')  # simple
                case 83:
                    _angle: float = self.get_acc('angle')  # num_of_bites
                case 90:
                    _angle: float = self.get_acc('angle')  # num_of_bites_skip_bites

                case 50:
                    _angle = 0.0
                case 51:
                    _angle = 0.0
                case 57:
                    _angle = 0.0
                case 64:
                    _angle = 0.0
                case 86:
                    _angle = 0.0
                case 95:
                    _angle: float = self.get_acc('rotation_manipulator')
                case 96:
                    _angle: float = self.get_acc('rotation_manipulator')
                case 80:
                    _angle: float = self.get_acc('x_rotation')
                case 82:
                    _angle: float = self.get_acc('x_rotation')
                case _:
                    raise KeyError(f"Unknown 'type_id'={self.type_id} for angle rotation")

            if -360.0 >= _angle >= 360.0:
                _old_angle = _angle
                _angle = _old_angle % 360.0
                LOGGER.warning(f"User entered rotation {_old_angle}°, but value {_angle} will be used")

            self.set_out('angle', _angle)
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _obsolete_initial_polygon(self):
        """
        Reads 'TEMPORARY.final_polygon' from previous operation.
        Rotates and centers it. Returns Polygon to 'TEMPORARY.initial_polygon'."""
        row, i = self.output, self.eo
        try:
            if self.parent_type_id == 35:
                trimesh_obj = self.get_out('TEMPORARY.initial_trimesh_obj')
                _p: Polygon = intersect_3d_mesh_by_2d_plane(trimesh_obj, plane_normal=[1, 0, 0], output_polygon_y_axis=[0, 1, 0], eo=i)

            elif self.parent_type_id in (37, 38, 39):
                previous_p = row.at[i - 1, 'TEMPORARY.final_polygon']
                _p: Polygon = prolongation_rotate_polygon(previous_p, row.at[i, 'angle'])

            else:
                _p: Polygon = row.at[i - 1, 'TEMPORARY.final_polygon']

            assert not _p.is_empty
            assert _p.area >= 1e-3

            # plot_polygon(_p, name='polygon_INITIAL', eo=i)

            row.at[i, 'initial_polygon'] = polygon_to_binary(_p)
            row.at[i, 'TEMPORARY.initial_polygon'] = _p

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._set_is_ready_false()

    def _initial_polygon___as_convex_hull_of_trimesh_xy_projection(self):
        """
        Reads 'TEMPORARY.final_polygon' from previous operation.
        Rotates and centers it. Returns Polygon to 'TEMPORARY.initial_polygon'."""
        row, i = self.output, self.eo
        try:
            if self.parent_type_id == 37:  # UPSETTING
                axis_indices = [1, 0]  # YX - projection
            else:
                axis_indices = [1, 2]  # YZ - projection
            trimesh_obj = self.get_out('TEMPORARY.initial_trimesh_obj')
            nodes = trimesh_obj.vertices.view(np.ndarray)[:, axis_indices]
            tri = ConvexHull(nodes)
            nodes_indices = tri.vertices
            line_xy = nodes[nodes_indices]
            _p = Polygon(line_xy)

            # plot_polygon(_p)

            assert not _p.is_empty
            assert _p.area >= 1e-3

            # plot_polygon(_p, name='polygon_INITIAL', eo=i)

            row.at[i, 'TEMPORARY.initial_polygon'] = _p
            row.at[i, 'initial_polygon'] = polygon_to_binary(_p)
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _is_same_parent_type_id(self) -> bool:
        try:
            return self.parent_type_id == self.previous_parent_type_id
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._set_is_ready_false()
            raise RuntimeError("Can't calculate Boolean value")

    def prolongation_spiral_type_50_final_polygon(self,
                                                  input_polygon: Polygon,
                                                  target_polygon: Polygon,
                                                  fin_dies_polygons: list[Polygon]
                                                  ):
        """Reads 'TEMPORARY.initial_polygon' and 'final_height'. Returns Polygon to 'TEMPORARY.final_polygon'."""
        row, i = self.output, self.eo
        try:
            if input_polygon.area <= target_polygon.area:
                _w = 0.0
                _a = row.at[i, 'initial_cross_section_area']
                _op = row.at[i, 'TEMPORARY.initial_polygon']

            else:
                _w, _a, _op = self.__type_50_final_polygon(input_polygon, fin_dies_polygons)

            # ------------------------------- RECORD RESULTS -------------------------------------
            row.at[i, 'final_width_of_contact'] = _w
            row.at[i, 'final_cross_section_area'] = _a
            row.at[i, 'final_polygon'] = polygon_to_binary(_op)
            row.at[i, 'TEMPORARY.final_polygon'] = _op

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._set_is_ready_false()

    def __type_50_final_polygon(self, p0: Polygon, fin_dies_polygons: list[Polygon]):
        row, i = self.output, self.eo
        try:
            initial_width = row.at[i, 'initial_width']
            initial_height = row.at[i, 'initial_height']
            final_height = row.at[i, 'final_height']

            pt: Polygon = fin_dies_polygons[0]
            pb: Polygon = fin_dies_polygons[1]

            y_scale_factor = polygon_y_scale_factor(p0, pt, pb,
                                                    row.at[i, 'initial_width'],
                                                    row.at[i, 'initial_height'],
                                                    row.at[i, 'penetration'])
            _y_scaled_polygon = scale(p0, xfact=1.0, yfact=y_scale_factor, origin=(0, 0, 0))

            area_except_middle, _split_lines, _split_polygons, _gaps = trim_middle_return_residual_area(
                _y_scaled_polygon, pt, pb, final_height)
            area_initial = p0.area

            boundary_list = translate_geoms_increase_gap(_gaps[0], _split_lines)
            polygon_list = translate_geoms_increase_gap(_gaps[0], _split_polygons)
            _width_of_contact_initial_guess = _gaps[0]
            _optimization_function = optimize.minimize(fun=strain_error,
                                                       x0=np.array([_width_of_contact_initial_guess]),
                                                       args=(area_except_middle,
                                                             row.at[i, 'final_length_of_contact'],
                                                             row.at[i, 'strain_height'],
                                                             initial_width,
                                                             initial_height,
                                                             final_height,
                                                             area_initial),
                                                       tol=1e-3)
            _optimal_width_of_contact = _optimization_function.x.item(0)
            _middle_polygon = middle_polygon_fill_gap(boundary_list, _optimal_width_of_contact)
            _output_polygons = translate_polygons_after_optimization(polygon_list, _optimal_width_of_contact)
            _p_1: list[Polygon] = [*_output_polygons[0], _middle_polygon, *_output_polygons[1]]
            _p_2 = sorted(_p_1, key=lambda _p_s: _p_s.centroid.x, reverse=False)
            _p_2_area = sum([_o_p.area for _o_p in _p_2])
            _min_dim = min([min(_p_2i.bounds[3] - _p_2i.bounds[1],
                                _p_2i.bounds[2] - _p_2i.bounds[0]
                                ) for _p_2i in _p_2
                            ])
            _start = math.sqrt(0.0001 * _min_dim)
            _end = math.sqrt(0.01 * _min_dim)
            _steps = 10
            _tol_values = [_value ** 2
                           for _value
                           in [_start + i * (_end - _start) / (_steps - 1) for i in range(_steps)]
                           ]

            def _combine_list_of_polygons(_tol_mm):
                return union_all([_p_2i.buffer(_tol_mm) for _p_2i in _p_2]).buffer(-_tol_mm)

            output_polygon = _combine_list_of_polygons(_tol_values[0])
            if not isinstance(output_polygon, Polygon):
                for _tol_value in _tol_values[1:]:
                    output_polygon = _combine_list_of_polygons(_tol_value)
                    if isinstance(output_polygon, Polygon):
                        break
            assert isinstance(output_polygon, Polygon), (f"Can't convert polygon to list of coordinates. "
                                                         f"Type must be Polygon, but {type(output_polygon)} received.")
            _area_error_limit = 0.0001
            _area_error_actual = abs(1 - output_polygon.area / _p_2_area)
            assert _area_error_actual <= _area_error_limit, (
                "Error of area modification is more than allowed error "
                f"{100 * _area_error_actual}% > {100 * _area_error_limit}%.")
            output_cross_section_area = area_except_middle + final_height * _optimal_width_of_contact
            assert_area_error(output_cross_section_area, output_polygon.area)
            # self.plot_polygon(output_polygon)
            return _optimal_width_of_contact, output_cross_section_area, output_polygon
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._set_is_ready_false()

    def full_die_final_polygon(self):
        """Reads 'TEMPORARY.initial_polygon' and 'final_height'. Returns Polygon to 'TEMPORARY.final_polygon'."""
        row, i = self.output, self.eo
        try:
            input_polygon = row.at[i, 'TEMPORARY.initial_polygon']
            initial_width = row.at[i, 'initial_width']
            initial_height = row.at[i, 'initial_height']
            fin_h = row.at[i, 'final_height']

            if height_of_polygon(input_polygon) <= fin_h:
                row.at[i, 'final_width_of_contact'] = 0.0
                row.at[i, 'final_cross_section_area'] = row.at[i, 'initial_cross_section_area']

                row.at[i, 'final_polygon'] = row.at[i, 'initial_polygon']
                row.at[i, 'TEMPORARY.final_polygon'] = row.at[i, 'TEMPORARY.initial_polygon']
                return

            _die_top, _die_bottom = create_dies(fin_h, input_polygon)

            y_scale_factor = polygon_y_scale_factor(input_polygon, _die_top, _die_bottom,
                                                    initial_width,
                                                    initial_height,
                                                    row.at[i, 'penetration'])
            _y_scaled_polygon = scale(input_polygon, xfact=1.0, yfact=y_scale_factor, origin=(0, 0, 0))

            area_except_middle, _split_lines, _split_polygons, _gaps = trim_middle_return_residual_area(
                _y_scaled_polygon, _die_top, _die_bottom, fin_h)

            area_initial = input_polygon.area

            boundary_list = translate_geoms_increase_gap(_gaps[0], _split_lines)
            polygon_list = translate_geoms_increase_gap(_gaps[0], _split_polygons)

            _width_of_contact_initial_guess = _gaps[0]
            _optimization_function = optimize.minimize(fun=strain_error,
                                                       x0=np.array([_width_of_contact_initial_guess]),
                                                       args=(area_except_middle,
                                                             row.at[i, 'final_length_of_contact'],
                                                             row.at[i, 'strain_height'],
                                                             initial_width,
                                                             initial_height,
                                                             fin_h,
                                                             area_initial),
                                                       tol=1e-3)
            _optimal_width_of_contact = _optimization_function.x.item(0)

            _middle_polygon = middle_polygon_fill_gap(boundary_list, _optimal_width_of_contact)
            _output_polygons = translate_polygons_after_optimization(polygon_list, _optimal_width_of_contact)

            _p_1: list[Polygon] = [*_output_polygons[0], _middle_polygon, *_output_polygons[1]]
            _p_2 = sorted(_p_1, key=lambda _p_s: _p_s.centroid.x, reverse=False)
            _p_2_area = sum([_o_p.area for _o_p in _p_2])

            _min_dim = min([min(_p_2i.bounds[3] - _p_2i.bounds[1],
                                _p_2i.bounds[2] - _p_2i.bounds[0])
                            for _p_2i in _p_2])
            _start = math.sqrt(0.0001 * _min_dim)
            _end = math.sqrt(0.01 * _min_dim)
            _steps = 10
            _tol_values = [_value ** 2
                           for _value
                           in [_start + i * (_end - _start) / (_steps - 1) for i in range(_steps)]
                           ]

            def _combine_list_of_polygons(_tol_mm):
                return union_all([_p_2i.buffer(_tol_mm) for _p_2i in _p_2]).buffer(-_tol_mm)

            output_polygon = _combine_list_of_polygons(_tol_values[0])
            if not isinstance(output_polygon, Polygon):
                for _tol_value in _tol_values[1:]:
                    output_polygon = _combine_list_of_polygons(_tol_value)
                    if isinstance(output_polygon, Polygon):
                        break

            assert isinstance(output_polygon, Polygon), (f"Can't convert polygon to list of coordinates. "
                                                         f"Type must be Polygon, but {type(output_polygon)} received.")

            _area_error_limit = 0.0001
            _area_error_actual = abs(1 - output_polygon.area / _p_2_area)
            assert _area_error_actual <= _area_error_limit, (
                "Error of area modification is more than allowed error "
                f"{100 * _area_error_actual}% > {100 * _area_error_limit}%.")

            output_cross_section_area = area_except_middle + fin_h * _optimal_width_of_contact

            assert_area_error(output_cross_section_area, output_polygon.area)

            # self.plot_polygon(output_polygon)

            row.at[i, 'final_width_of_contact'] = _optimal_width_of_contact
            row.at[i, 'final_cross_section_area'] = output_cross_section_area

            row.at[i, 'final_polygon'] = polygon_to_binary(output_polygon)
            row.at[i, 'TEMPORARY.final_polygon'] = output_polygon

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._set_is_ready_false()

    def _upsetting_final_polygon(self):
        """Reads 'TEMPORARY.initial_polygon' and 'final_height'. Returns Polygon to 'TEMPORARY.final_polygon'."""
        row, i = self.output, self.eo
        try:
            input_polygon = row.at[i, 'TEMPORARY.initial_polygon']

            strain_x = row.at[i, 'strain_width']
            strain_y = row.at[i, 'strain_height']

            x_scale_factor = math.exp(strain_x)
            y_scale_factor = math.exp(strain_y)

            output_polygon = scale(input_polygon, xfact=x_scale_factor, yfact=y_scale_factor, origin=(0.0, 0.0, 0.0))

            row.at[i, 'final_polygon'] = polygon_to_binary(output_polygon)
            row.at[i, 'TEMPORARY.final_polygon'] = output_polygon

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _obsolete_initial_basis(self):
        """Creating straight prism tesselation. Returns stl mesh object."""
        row, i = self.output, self.eo
        try:

            previous_basis = np.array(self.get_previous_out('final_basis'))

            if self.parent_type_id != 35:
                rotations = [('x', self.get_out('angle'))]

            else:  # self.parent_type_id == 35:

                osp = row.at[i, 'operation_specific_parameters']

                if self.previous_parent_type_id != 35:
                    rotations = [
                        ('x', osp['rotation_1_manipulator']),
                        ('y', osp['rotation_2_operator']),
                        ('x', osp['rotation_3_manipulator']),
                        ('y', osp['rotation_4_operator']),
                        ('x', osp['rotation_5_manipulator'])
                    ]

                elif self.previous_parent_type_id == 35 and self.previous_accumulated_type_id in (35, 98):
                    previous_osp = row.at[i - 1, 'operation_specific_parameters']
                    rotations = [

                        # Use previous rotations and return back to coaxial state of the Billet with Global X-asis
                        ('x', previous_osp['rotation_5_manipulator']),
                        ('y', previous_osp['rotation_4_operator']),
                        ('x', previous_osp['rotation_3_manipulator']),
                        ('y', previous_osp['rotation_2_operator']),
                        ('x', previous_osp['rotation_1_manipulator']),

                        # New rotations
                        ('x', osp['rotation_1_manipulator']),
                        ('y', osp['rotation_2_operator']),
                        ('x', osp['rotation_3_manipulator']),
                        ('y', osp['rotation_4_operator']),
                        ('x', osp['rotation_5_manipulator'])
                    ]

                else:  # self.previous_parent_type_id == 35 and self.previous_accumulated_type_id not in (35, 98):
                    rotations = [('x', self.get_out('angle'))]

            initial_basis: np.ndarray = rotate_basis(input_cs=previous_basis, list_of_rotations_xyz=rotations)
            self.set_out('initial_basis', initial_basis.tolist())

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._set_is_ready_false()

    def _osp_radial_initial_rotations(self):
        row, i = self.output, self.eo
        try:
            if self.parent_type_id == 35:  # radial_prolongation
                if self.previous_accumulated_type_id == 98:  # New "Initial Rotations"
                    initial_rotations = [
                        ('x', self.get_acc('rotation_1_manipulator')),
                        ('y', 90.0),
                        ('x', self.get_acc('rotation_3_manipulator')),
                        ('y', self.get_acc('rotation_4_operator'))
                    ]
                elif self.previous_parent_type_id != 35:  # Previous operation is not Radial prolongation type
                    initial_rotations =[
                        ('x', 0.0),
                        ('y', 90.0),
                        ('x', 0.0),
                        ('y', 0.0)]
                elif self.previous_accumulated_type_id == 35:  # New Block holder (of Radial prolongations)
                    initial_rotations = [
                        ('x', 0.0),
                        ('y', 90.0),
                        ('x', 0.0),
                        ('y', 0.0)]
                else:
                    previous_osp = row.at[i - 1, 'operation_specific_parameters']
                    initial_rotations = previous_osp['radial_initial_rotations']

            # elif self.type_id == 92:  # tail_flattening_with_rotation
            #
            #
            else:
                initial_rotations = []

            osp = row.at[i, 'operation_specific_parameters']

            osp['radial_initial_rotations'] = initial_rotations
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _osp_radial_accumulated_billet_rotation(self):
        row, i = self.output, self.eo
        try:
            if self.parent_type_id != 35:  # EXCEPT radial_prolongation
                # accumulated_rotation = 0.0
                accumulated_rotation = self.get_out('angle')

            else:  # self.parent_type_id == 35  # radial_prolongation
                if any((
                        self.previous_accumulated_type_id == 35,  # New Block holder (of Radial prolongations)
                        self.previous_accumulated_type_id == 98,  # New "Initial Rotations"
                        self.previous_parent_type_id != 35  # Any non-Radial prolongation operation
                )):
                    accumulated_rotation = self.get_out('angle')  # Initialize accumulated rotation
                else:
                    previous_osp = row.at[i - 1, 'operation_specific_parameters']
                    accumulated_rotation = previous_osp['radial_accumulated_billet_rotation']  # Read previously accumulated value
                    accumulated_rotation += self.get_out('angle')

            osp = row.at[i, 'operation_specific_parameters']

            osp['radial_accumulated_billet_rotation'] = accumulated_rotation
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _osp_radial_rotations(self):
        row, i = self.output, self.eo
        try:
            # if self.parent_type_id == 35:
            #     return

            osp = row.at[i, 'operation_specific_parameters']

            radial_initial_rotations = osp['radial_initial_rotations']
            radial_rotations = radial_initial_rotations.copy()

            accumulated_billet_rotation = osp['radial_accumulated_billet_rotation']
            radial_rotations.append(('x', accumulated_billet_rotation))

            osp['radial_rotations'] = radial_rotations
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _initial_basis(self):
        """Creating straight prism tesselation. Returns stl mesh object."""
        row, i = self.output, self.eo
        try:
            osp = row.at[i, 'operation_specific_parameters']
            rotations = osp['radial_rotations']

            previous_basis = np.array(self.get_previous_out('final_basis'))
            initial_basis: np.ndarray = rotate_basis(input_cs=previous_basis, list_of_rotations_xyz=rotations)
            row.at[i, 'initial_basis'] = initial_basis.tolist()

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _final_basis(self):
        """Creating straight prism tesselation. Returns stl mesh object."""
        row, i = self.output, self.eo
        try:
            initial_basis: np.ndarray = np.array(self.get_out('initial_basis'))

            if self.parent_type_id == 35:  # Radial Prolongation AND Upsetting
                osp: dict = self.get_out('operation_specific_parameters')
                direct_rotations: list = osp['radial_rotations']
                reversed_rotations: list = [(_axis_name, -1 * _angle) for (_axis_name, _angle) in direct_rotations[::-1]]
                final_basis: np.ndarray = rotate_basis(input_cs=initial_basis, list_of_rotations_xyz=reversed_rotations)

            elif self.parent_type_id == 37:
                y_angle: list = self.get_out('operation_specific_parameters')['radial_rotations'][-1][-1]
                reversed_rotations: list = [('y', -1 * y_angle)]
                final_basis: np.ndarray = rotate_basis(input_cs=initial_basis, list_of_rotations_xyz=reversed_rotations)

            else:  # EXCEPT radial_rotations
                final_basis: np.ndarray = initial_basis

            row.at[i, 'final_basis'] = final_basis.tolist()

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _obsolete_initial_3d_stl(self):
        """Creating straight prism tesselation. Returns stl mesh object."""
        row, i = self.output, self.eo
        try:
            if self.parent_type_id != 35:
                _polygon = row.at[i, 'TEMPORARY.initial_polygon']

                # plot_polygon(_polygon, 'polygon_NOT_OP_35_INITIAL_POLYGON', eo=i)

                _length = row.at[i, 'initial_length']
                trimesh_obj = polygon_to_3d_trimesh_object(_polygon, _length, i)

            else:  # self.parent_type_id == 35:
                if self.previous_parent_type_id != 35:
                    # Convert "Axial cross-section" into "Side view" cross-section (of Radial Prolongation)
                    previous_polygon: Polygon = row.at[i - 1, 'TEMPORARY.final_polygon']

                    # plot_polygon(previous_polygon, name='polygon_OP_35_I-1_FINAL_POLYGON', eo=i)

                    previous_length: np.float64 = row.at[i - 1, 'final_length']
                    previous_mesh = polygon_to_3d_trimesh_object(previous_polygon, previous_length, i)

                    # plot_trimesh_object(previous_mesh, name='mesh_OP_35_I-1_FINAL_POLYGON', eo=i)

                    osp = row.at[i, 'operation_specific_parameters']
                    rotations = [
                        ('x', osp['rotation_1_manipulator']),
                        ('y', osp['rotation_2_operator']),
                        ('x', osp['rotation_3_manipulator']),
                        ('y', osp['rotation_4_operator']),
                        ('x', osp['rotation_5_manipulator'])
                    ]
                    trimesh_obj = rotate_trimesh_object(previous_mesh, rotations, eo=i)

                elif self.previous_parent_type_id == 35 and self.previous_accumulated_type_id in (35, 98):
                    previous_polygon: Polygon = row.at[i - 1, 'TEMPORARY.final_polygon']
                    previous_length: np.float64 = row.at[i - 1, 'final_length']
                    previous_mesh = polygon_to_3d_trimesh_object(previous_polygon, previous_length, i)

                    previous_osp = row.at[i - 1, 'operation_specific_parameters']
                    back_to_original_cs_rotations = [
                        ('x', previous_osp['rotation_5_manipulator']),
                        ('y', previous_osp['rotation_4_operator']),
                        ('x', previous_osp['rotation_3_manipulator']),
                        ('y', previous_osp['rotation_2_operator']),
                        ('x', previous_osp['rotation_1_manipulator'])
                    ]
                    previous_mesh_in_original_cs = rotate_trimesh_object(previous_mesh, back_to_original_cs_rotations, eo=i)

                    osp = row.at[i, 'operation_specific_parameters']
                    rotations = [
                        ('x', osp['rotation_1_manipulator']),
                        ('y', osp['rotation_2_operator']),
                        ('x', osp['rotation_3_manipulator']),
                        ('y', osp['rotation_4_operator']),
                        ('x', osp['rotation_5_manipulator'])
                    ]
                    trimesh_obj = rotate_trimesh_object(previous_mesh_in_original_cs, rotations, eo=i)

                else:  # self.previous_parent_type_id == 35 and self.previous_accumulated_type_id not in (35, 98):
                    previous_osp = row.at[i - 1, 'operation_specific_parameters']
                    osp = row.at[i, 'operation_specific_parameters']
                    rotation_manipulator = osp['rotation_5_manipulator'] - previous_osp['rotation_5_manipulator']
                    previous_polygon: Polygon = row.at[i - 1, 'TEMPORARY.final_polygon']
                    previous_length: np.float64 = row.at[i - 1, 'final_length']
                    _mesh = polygon_to_3d_trimesh_object(previous_polygon, previous_length, i)
                    trimesh_obj = rotate_trimesh_object(_mesh, [('x', rotation_manipulator)], eo=i)

            # ----------------------CONVERT TRIMESH TO STL --------------------------------
            # plot_trimesh_object(trimesh_obj, name="mesh_INITIAL_3D_STL_AS_IS", eo=i)
            _stl_binary: bytes = convert_trimesh_object_to_memory_buffer_object(trimesh_obj)
            # -------------------------- SAVE STL BINARY ----------------------------------
            row.at[i, 'initial_3d_stl'] = _stl_binary

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._set_is_ready_false()

    def _tails_x_length(self) -> list:
        """Creating straight prism tesselation. Returns stl mesh object."""
        row, i = self.output, self.eo
        try:
            initial_trimesh_obj: Trimesh = row.at[i, 'TEMPORARY.initial_trimesh_obj']
            t = initial_trimesh_obj.copy()
            bounds = t.bounds
            center = np.multiply(0.5, np.sum(bounds, axis=0))  # Center of bounds of Trimesh object
            back_to_center_offset = np.multiply(-1, center)

            y_axis = np.array([0, 1, 0])  # Y-axis
            angle = math.radians(45.0)
            rot = Rotation.from_rotvec(angle * y_axis)

            v = t.vertices.view(np.ndarray)  # [x, y, z] coordinates of vertices
            v = np.add(v, back_to_center_offset)
            v = rot.apply(v)
            t.vertices = v

            rotated_bounds = t.bounds

            """
                CHAMFERS:
                   12      z_top       21   
            (1)    +--------------------+  (2)
                 /          ^ Z          \
            11  +           |             + 22
                |           |             |
                |           o---->X       |
            42  +                         + 31
                 \                       /
            (4)   +---------------------+  (3)
                  41     z_bottom      32  
            """

            z_top_12_21 = abs(bounds[1, 2])
            z_bottom_41_32 = abs(bounds[0, 2])
            x_left_11_42 = abs(bounds[0, 0])
            x_right_22_31 = abs(bounds[1, 0])

            r_1 = abs(rotated_bounds[1, 2])  # Z-top Rotated
            r_3 = abs(rotated_bounds[0, 2])  # Z-bottom Rotated
            r_4 = abs(rotated_bounds[0, 0])  # X-left Rotated
            r_2 = abs(rotated_bounds[1, 0])  # X-right Rotated

            sqrt2 = math.sqrt(2)

            chamfer_1_x_length = x_left_11_42 - (sqrt2 * r_1 - z_top_12_21)
            chamfer_4_x_length = x_left_11_42 - (sqrt2 * r_4 - z_bottom_41_32)
            chamfer_2_x_length = x_right_22_31 - (sqrt2 * r_2 - z_top_12_21)
            chamfer_3_x_length = x_right_22_31 - (sqrt2 * r_3 - z_bottom_41_32)

            left_tail_x_length = max(chamfer_1_x_length, chamfer_4_x_length)
            right_tail_x_length = max(chamfer_2_x_length, chamfer_3_x_length)

            # osp = row.at[i, 'operation_specific_properties']
            # osp['tails_x_length'] = [left_tail_x_length, right_tail_x_length]
            return [left_tail_x_length, right_tail_x_length]
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise RuntimeError("Error in calculating lengths of tails barreling")

    def _initial_3d_stl__and__temporary_trimesh_obj(self):
        """Creating straight prism tesselation. Returns stl mesh object."""
        row, i = self.output, self.eo
        try:
            previous_final_basis = np.array(self.get_previous_out('final_basis'))
            initial_basis = np.array(self.get_out('initial_basis'))

            transformation_matrix = trimesh_basis_to_basis_transformation_matrix(previous_final_basis, initial_basis)
            trimesh_obj = convert_stl_binary_object_to_trimesh_object(self.get_previous_out('final_3d_stl'))
            trimesh_obj.apply_transform(transformation_matrix)

            row.at[i, 'TEMPORARY.initial_trimesh_obj'] = trimesh_obj
            row.at[i, 'initial_3d_stl'] = convert_trimesh_object_to_memory_buffer_object(trimesh_obj)
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _final_3d_stl(self):
        """Creating straight prism tesselation. Returns stl mesh object."""
        row, i = self.output, self.eo
        try:
            final_height = row.at[i, 'final_height']
            if height_of_polygon(row.at[i, 'TEMPORARY.initial_polygon']) <= final_height:
                return

            trimesh_obj = self.get_out('TEMPORARY.initial_trimesh_obj')

            z_scale = row.at[i, 'TEMPORARY.y_scale_factor']
            scale_matrix = np.eye(4)
            scale_matrix[2, 2] *= z_scale
            trimesh_obj.apply_transform(scale_matrix)

            trimesh_obj_bounds = trimesh_obj.bounds
            top_die_bounds, bottom_die_bounds = trimesh_obj_bounds.copy(), trimesh_obj_bounds.copy()

            top_die_bounds[:, :2] *= 1.1
            bottom_die_bounds[:, :2] *= 1.1

            top_die_z_coord, bottom_die_z_coord = top_die_bounds[0, 2], top_die_bounds[1, 2]
            target_top_die_z_coord, target_bottom_die_z_coord = 0.5 * final_height, -0.5 * final_height

            top_die_bounds[:, 2] += (target_top_die_z_coord - top_die_z_coord)
            bottom_die_bounds[:, 2] += (target_bottom_die_z_coord - bottom_die_z_coord)

            _die_top, _die_bottom = creation.box(bounds=top_die_bounds), creation.box(bounds=bottom_die_bounds)

            trimesh_obj_cut = boolean.difference(meshes=(
                boolean.difference(meshes=(trimesh_obj, _die_top)),
                _die_bottom
                )
            )


            # ================
            transformation_matrix = trimesh_basis_to_basis_transformation_matrix(np.array(self.get_out('initial_basis')),
                                                                                 np.array(self.get_out('final_basis')))

            trimesh_obj = self.get_out('TEMPORARY.initial_trimesh_obj')
            trimesh_obj.apply_transform(transformation_matrix)

            row.at[i, 'TEMPORARY.final_trimesh_obj'] = trimesh_obj
            row.at[i, 'TEMPORARY.final_trimesh_obj_in_initial_basis'] = trimesh_obj
            row.at[i, 'final_3d_stl'] = convert_trimesh_object_to_memory_buffer_object(trimesh_obj)
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise
    def _upsetting_final_3d_stl(self):
        """Creating straight prism tesselation. Returns stl mesh object."""
        row, i = self.output, self.eo
        try:
            strain_x, strain_y, strain_z = row.loc[i, ['strain_height', 'strain_width', 'strain_length']].to_list()
            x_scale_factor, y_scale_factor, z_scale_factor = math.exp(strain_x), math.exp(strain_y), math.exp(strain_z)

            scale_matrix = np.eye(4)
            scale_matrix[0, 0] *= x_scale_factor
            scale_matrix[1, 1] *= y_scale_factor
            scale_matrix[2, 2] *= z_scale_factor

            trimesh_obj: Trimesh = row.at[i, 'TEMPORARY.initial_trimesh_obj']
            trimesh_scaled_obj = trimesh_obj.copy().apply_transform(scale_matrix)

            initial_basis = row.at[i, 'initial_basis']
            final_basis = row.at[i, 'final_basis']
            transformation_matrix = trimesh_basis_to_basis_transformation_matrix(initial_basis, final_basis)
            final_trimesh_obj = trimesh_scaled_obj.copy().apply_transform(transformation_matrix)

            row.at[i, 'TEMPORARY.final_trimesh_obj_in_initial_basis'] = trimesh_scaled_obj
            row.at[i, 'TEMPORARY.final_trimesh_obj'] = final_trimesh_obj
            row.at[i, 'final_3d_stl'] = convert_trimesh_object_to_memory_buffer_object(final_trimesh_obj)
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def function_of_radial_prolongation_height_vs_cross_section_area(self) -> list[tuple[float, float]]:
        """
        Computes the coefficients 'a' and 'b' for the linear equation ra = a*w + b,
        where 'ra' is the relative area of the intersection between the input polygon 'p'
        and a box of width 'w', iterated from 99% to 1% of 'p's width.

        Parameters:
        - stl_binary (bytes): Input Buffer Memory file object with Binary STL inside.

        Returns:
        - a (float): Coefficient for width 'w'.
        - b (float): Constant term.
        """
        row, i = self.output, self.eo
        try:
            previous_final_volume: np.float64 = row.at[i - 1, 'volume_final']
            stl_binary: bytes = row.at[i, 'initial_3d_stl']

            if not isinstance(stl_binary, bytes):
                raise TypeError(f"Input 'stl_binary' must have 'bytes' type, but it has '{type(stl_binary)}' type.")

            trimesh_obj = convert_stl_binary_object_to_trimesh_object(stl_binary)

            # plot_trimesh_object(trimesh_obj, name="mesh_INPUT_TO_FUNCTION", eo=i)

            stl_volume = trimesh_obj.volume
            if stl_volume <= 0:
                raise ValueError("Input mesh must have positive volume")

            volume_error_limit = 1e-3
            volume_error = abs(stl_volume / previous_final_volume - 1) * 100.0
            if volume_error > volume_error_limit:
                raise ValueError(f"Volume Error between 'initial_3d_stl' and previous 'final_volume' "
                                 f"is {volume_error}% which exceeds Volume Error Limit ({volume_error_limit}%)")

            osp = row.at[i, 'operation_specific_parameters']
            list_of_rotations = [('x', osp['rotation_1_manipulator']),
                                 ('y', osp['rotation_2_operator']),
                                 ('x', osp['rotation_3_manipulator']),
                                 ('y', osp['rotation_4_operator']),
                                 ('x', osp['rotation_5_manipulator'])]
            global_basis = np.array(((1, 0, 0), (0, 1, 0), (0, 0, 1)))
            actual_billet_basis = rotate_basis(global_basis, list_of_rotations, randomize_deviation=1e-3)

            actual_billet_x_axis = randomize_vector(actual_billet_basis[0, :].tolist())

            polygon_normal_to_billet_axis: Polygon = intersect_3d_mesh_by_2d_plane(mesh_stl=trimesh_obj, plane_normal=actual_billet_x_axis, output_polygon_y_axis=[1, 0, 0], eo=i)
            # plot_polygon(polygon_normal_to_billet_axis, name='polygon_NORMAL_TO_BILLET_AXIS_POLYGON_Y_IS_GLOBAL_X', eo=i)

            global_x_axis = [1, 0, 0]
            billet_width_axis = np.cross(actual_billet_x_axis, global_x_axis)
            polygon_billet_side_projection: Polygon = intersect_3d_mesh_by_2d_plane(mesh_stl=trimesh_obj, plane_normal=global_x_axis, output_polygon_y_axis=billet_width_axis, eo=i)
            # plot_polygon(polygon_billet_side_projection, name='polygon_BILLET_GLOBAL_YZ_SECTION', eo=i)

            _bounds: np.ndarray | None = trimesh_obj.bounds  # (2, 3) [min, max]

            assert _bounds is not None

            min_x, min_y, max_x, max_y = polygon_normal_to_billet_axis.bounds
            width = max_x - min_x
            height = max_y - min_y

            if width == 0 or height == 0:
                raise ValueError("Input polygon must have non-zero width and height.")

            polygon_normal_area = polygon_normal_to_billet_axis.area
            polygon_side_projection = polygon_billet_side_projection.area
            if polygon_normal_area == 0:
                raise ValueError("Input polygon must have area")

            center_x = (min_x + max_x) / 2
            min_y_b = min_y - 1.0
            max_y_b = max_y + 1.0

            polygon_length = previous_final_volume / polygon_normal_area

            result = []

            for percent in range(100, 0, -10):
                w = (percent / 100) * width
                l = (percent / 100) * polygon_length

                min_x_b = center_x - w / 2
                max_x_b = center_x + w / 2

                # Create the box with the current width 'w' and the same height as 'p'
                b_box = box(min_x_b, min_y_b, max_x_b, max_y_b)

                # Compute the intersection of 'p' and 'b_box'
                ip = polygon_normal_to_billet_axis.intersection(b_box)

                # Delta volume
                dv = stl_volume - ip.area * l

                # Cross-section area
                final_cross_section_area = polygon_side_projection * (percent / 100) ** 2

                # Delta height
                dh = dv / final_cross_section_area

                # Final height
                final_height = height + dh

                result.append((final_cross_section_area, final_height,))

            return result
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _initial_width_of_contact(self):
        """Calculate elongation coefficient"""
        row, i = self.output, self.eo
        try:
            ini_billet_polygon = row.at[i, 'TEMPORARY.initial_polygon']
            if self.parent_type_id == 37:  # Upsetting
                result = row.at[i, 'initial_width']

            elif self.type_id in (46, 83, 90, 52, 80, 82, 95, 96):
                """
                46, 83, 90 - Prolongation (Feed, Num of Bites, Num of Bites Skip Bites),
                52 - Full die, 
                80 - (Obsolete) Radial prolongation Feed, 
                82 - (Obsolete) Radial prolongation Num of Bites
                95 - Radial prolongation Feed, 
                96 - Radial prolongation Num of Bites
                """
                result = initial_width_of_contact(ini_billet_polygon,
                                                  row.at[i, 'initial_height'],
                                                  row.at[i, 'final_height'])
            else:
                raise KeyError(f"Unknown 'type_id': {self.type_id}")

            row.at[i, 'initial_width_of_contact'] = result

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _initial_dimensions(self):
        """
        Reads 'TEMPORARY.initial_polygon'. Returns total dimensions to 'initial_height', 'initial_width'.
        Copies 'final_length' to 'initial_length'.
        """
        row, i = self.output, self.eo
        try:
            if self.parent_type_id == 37:  # All Upsetting operations
                keys = ['initial_height', 'initial_width', 'initial_length']
            else:
                keys = ['initial_length', 'initial_width', 'initial_height']

            trimesh_obj: Trimesh = row.at[i, 'TEMPORARY.initial_trimesh_obj']
            bounds = trimesh_obj.bounds
            row.loc[i, keys] = bounds[1, :] - bounds[0, :]

            negative_keys = [key for key in keys if row.at[i, key] <= 0.0]
            assert not negative_keys, f"ValueError: {', '.join(keys)} in self.output[...] are negative."

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _radial_prolongation_length(self, cross_section_area: float) -> float:
        row, i = self.output, self.eo
        try:
            points = np.array(row.at[i, 'operation_specific_parameters']['length_vs_cross_section_area'])
            interpolation_function = interp1d(points[:, 0], points[:, 1], kind='cubic', fill_value="extrapolate")
            _l: np.ndarray = interpolation_function(cross_section_area)
            return _l.item()
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._set_is_ready_false()
            return 0.0

    def prolongation_input_h_return_p_and_e(self):
        """Calculate Final height, Penetration and Relative deformation for Drawing"""
        row, i = self.output, self.eo
        try:
            if row.at[i, 'initial_height'] > row.at[i, 'final_height']:
                row.at[i, 'penetration'] = row.at[i, 'initial_height'] - row.at[i, 'final_height']
                row.at[i, 'relative_deformation'] = \
                    (1.0 - row.at[i, 'final_height'] / row.at[i, 'initial_height']) * 100.0
            else:
                row.at[i, 'final_height'] = row.at[i, 'initial_height']
                row.at[i, 'penetration'] = 0.0
                row.at[i, 'relative_deformation'] = 0.0

            assert row.at[i, 'penetration'] >= 0.0, f"'penetration' is negative or zero."
            assert row.at[i, 'relative_deformation'] >= 0.0, f"'relative_deformation' is negative or zero."

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._set_is_ready_false()

    def _upsetting_input_l_return_p_and_e(self):
        """Calculate Final height, Penetration and Relative deformation for Drawing"""
        row, i = self.output, self.eo
        try:
            if row.at[i, 'initial_length'] > row.at[i, 'final_length']:

                row.at[i, 'penetration'] = row.at[i, 'initial_length'] - row.at[i, 'final_length']
                row.at[i, 'relative_deformation'] = \
                    (1.0 - row.at[i, 'final_length'] / row.at[i, 'initial_length']) * 100.0

            else:
                row.at[i, 'final_length'] = row.at[i, 'initial_length']
                row.at[i, 'penetration'] = 0.0
                row.at[i, 'relative_deformation'] = 0.0

            not_negative = True
            for key in ('penetration', 'relative_deformation'):
                if row.at[i, key] < 0.0:
                    LOGGER.error(f"ValueError: self.output['{key}'] is negative.")
                    not_negative = False
            assert not_negative, f"ValueError: negative value"

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def upsetting_input_p_return_l_and_e(self):
        """Calculate Final height, Penetration and Relative deformation for Upsetting Tail Flattening"""
        row, i = self.output, self.eo
        try:
            if row.at[i, 'penetration'] > 0.0:
                row.at[i, 'final_length'] = row.at[i, 'initial_length'] - row.at[i, 'penetration']
                row.at[i, 'relative_deformation'] = \
                    (1.0 - row.at[i, 'final_length'] / row.at[i, 'initial_length']) * 100.0
            else:
                row.at[i, 'final_length'] = row.at[i, 'initial_length']
                row.at[i, 'penetration'] = 0.0
                row.at[i, 'relative_deformation'] = 0.0

            not_negative = True
            for key in ('penetration', 'relative_deformation'):
                if row.at[i, key] < 0.0:
                    LOGGER.error(f"ValueError: self.output['{key}'] is negative.")
                    not_negative = False
            assert not_negative, f"ValueError: negative value"

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._set_is_ready_false()

    def _final_volume_cutting(self):
        """Calculate Final height, Penetration and Relative deformation for Upsetting Tail Flattening"""
        row, i = self.output, self.eo
        try:
            scrap_rate = row.at[i, 'scrap_rate']
            initial_volume = row.at[i, 'volume_initial']
            volume_except_scrap = initial_volume * (1 - scrap_rate)

            _id = row.at[i, 'type_id']
            match _id:
                case 57:  # Hot Cutting percentage
                    percentage_to_keep = int(self.accumulated.loc[self.input_index, 'percentage_to_keep'].item())
                    final_volume = volume_except_scrap * percentage_to_keep / 100
                case 86:  # Cold Sawing percentage
                    percentage_to_keep = int(self.accumulated.loc[self.input_index, 'percentage_to_keep'].item())
                    final_volume = volume_except_scrap * percentage_to_keep / 100
                case _:
                    raise KeyError(f"Type ID = {_id} is not recognized for cutting operation")

            assert final_volume > 0.0, f"Final volume ({final_volume}) is zero or negative, but must be positive."

            row.at[i, 'volume_final'] = final_volume

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._set_is_ready_false()

    def _cutting_final_length(self):
        """Calculate Final height, Penetration and Relative deformation for Upsetting Tail Flattening"""
        row, i = self.output, self.eo
        try:
            final_area = row.at[i, 'final_cross_section_area']
            final_volume = row.at[i, 'volume_final']
            final_length = final_volume / final_area

            assert final_length > 0.0, f"Final length ({final_length}) is zero or negative, but must be positive."

            row.at[i, 'final_length'] = final_length

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._set_is_ready_false()

    def _cutting_scrap_rate(self):
        row, i = self.output, self.eo
        try:
            initial_area = row.at[i, 'initial_cross_section_area']
            initial_volume = row.at[i, 'volume_initial']
        except KeyError as _err:
            LOGGER.error(f"KeyError: {_err}")
            self._set_is_ready_false()
            return

        def hot_cutting_scrap_volume() -> float:
            equivalent_diameter = 2 * math.sqrt(initial_area / math.pi)
            return 6.3488E+5 * math.exp(3.9233E-3 * equivalent_diameter)

        def cold_sawing_scrap_volume() -> float:
            saw_thickness = 3.0  # mm
            return initial_area * saw_thickness

        try:
            match row.at[i, 'type_id']:
                case 57:  # Hot Cutting percentage
                    single_cut_scrap_volume = hot_cutting_scrap_volume()
                    pieces_count = int(self.accumulated.loc[self.input_index, 'pieces_count'].item())
                    cuttings_count = pieces_count - 1
                case 86:  # Cold Sawing percentage
                    single_cut_scrap_volume = cold_sawing_scrap_volume()
                    pieces_count = int(self.accumulated.loc[self.input_index, 'pieces_count'].item())
                    cuttings_count = pieces_count - 1
                case _:
                    raise KeyError(f"Type ID = {row.at[i, 'type_id']} is not recognized for calculating Scrap volume "
                                   f"of cutting operation")

            total_scrap_volume = single_cut_scrap_volume * cuttings_count
            scrap_rate = total_scrap_volume / initial_volume

            assert scrap_rate > 0.0, f"Scrap rate ({scrap_rate}) is zero or negative, but must be positive."

            row.at[i, 'scrap_rate'] = scrap_rate

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._set_is_ready_false()

    def _feed_table__automatic_feed__control_last_feed(self, initial_length: float, initial_height: float, first_and_last_tails_barrels: list, middle_of_die_edge__at_relative_penetration_percent: float = 30.0) -> dict:
        try:
            press_mode_id = self.get_out('press_mode_id')
            max_manual_feed_count = config.lib['press_mode']['automatic_feed_mode_is_on_when_bites_count'][press_mode_id]
            last_manual_feeds_count = config.services['pre']['operations_settings']['prolongation']['automatic_feed_control']['when_last_feed_is_controlled']['last_manual_feeds_count']

            _first, _middle, _last = self.output.loc[self.eo, ['feed_first', 'feed_middle', 'feed_last']].to_list()
            nominal_middle = self.first_non_zero(_middle, _first)
            nominal_last = self.first_non_zero(_last, _middle, _first)

            skipped_last_feed_count = 1
            skipped_middle_feed_count = max(0, (last_manual_feeds_count - 1))
            skip_last_feeds_count = int(math.floor((nominal_last * skipped_last_feed_count + nominal_middle * skipped_middle_feed_count) / nominal_middle))
            while True:
                automatic_steps = self._feed_table__automatic_feed__do_not_control_last_feed(initial_length=initial_length,
                                                                                             initial_height=initial_height,
                                                                                             first_and_last_tails_barrels=first_and_last_tails_barrels,
                                                                                             middle_of_die_edge__at_relative_penetration_percent=middle_of_die_edge__at_relative_penetration_percent,
                                                                                             skip_last_feeds_count=skip_last_feeds_count)
                initial_residual_length_after_automatic_feeds = automatic_steps['initial_residual_length'][-1] - \
                                                                automatic_steps['deformed_length_increment'][-1]
                manual_steps = self._feed_table__manual_mode__feed_control__multiple_bites(initial_length=initial_length,
                                                                                           initial_height=initial_height,
                                                                                           first_and_last_tails_barrels=first_and_last_tails_barrels,
                                                                                           middle_of_die_edge__at_relative_penetration_percent=middle_of_die_edge__at_relative_penetration_percent,
                                                                                           starting_initial_residual_length=initial_residual_length_after_automatic_feeds)
                automatic_steps_count = len(automatic_steps['initial_residual_length'])
                manual_steps_count = len(manual_steps['initial_residual_length'])
                is_lack_of_automatic_feeds = automatic_steps_count < (max_manual_feed_count - last_manual_feeds_count - 1)
                if is_lack_of_automatic_feeds or manual_steps_count >= last_manual_feeds_count:
                    break
                else:
                    skip_last_feeds_count += 1

            _common_keys = set(automatic_steps.keys()).intersection(set(manual_steps.keys()))
            steps = {key: [] for key in _common_keys}
            for key in _common_keys:
                steps[key].extend(automatic_steps[key])
                steps[key].extend(manual_steps[key])

            return steps
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()

    def _feed_table__automatic_feed__do_not_control_last_feed(self, initial_length: float, initial_height: float, first_and_last_tails_barrels: list, middle_of_die_edge__at_relative_penetration_percent: float = 30.0, skip_last_feeds_count: int = 0) -> dict:
        row, i = self.output, self.eo
        try:
            _first, _middle = row.loc[i, ['feed_first', 'feed_middle']].to_list()

            abs_first = _first
            abs_middle = self.first_non_zero(_middle, _first)

            count_first = 1
            count_middle = int(math.ceil((initial_length - abs_first) / abs_middle))

            # ============================= COMPENSATION OF DIE EDGE CONTACT LENGTH ====================================
            die_edge_contact_length__full: float = self._contact_length_along_die_edge()
            die_edge_contact_length__part_of_theoretical_feed: float = self._contact_length_along_die_edge(at_relative_penetration_percent=middle_of_die_edge__at_relative_penetration_percent)
            die_edge_contact_length__part_of_next_feed: float = die_edge_contact_length__full - die_edge_contact_length__part_of_theoretical_feed

            # --------------------------------------------------------------------
            num_of_bites = count_first + count_middle
            nominal_feed__table = [abs_first] * count_first + [abs_middle] * count_middle

            die_length = self._die_straight_length()
            half_penetration = 0.5 * self.get_out('penetration')
            first_tail_barrel_length = first_and_last_tails_barrels[0]
            last_tail_barrel_length = first_and_last_tails_barrels[1]

            initial_residual_length: float = initial_length

            steps = {
                'initial_residual_length': [],
                'theoretical_feed': [],
                'initial_contact_length': [],
                'final_contact_length': [],
                'deformed_length_increment': [],
                'distance_center_of_die_till_undeformed_tail': [],
                'residual_length_elongation_increment': [],
                'feeds_table': []
            }

            for bite_index in range(num_of_bites - skip_last_feeds_count):  # Except last bite
                bite_num = bite_index + 1

                nominal_feed = nominal_feed__table[bite_index]

                # ======================== COMPENSATION OF TAIL DOUBLE BARRELING FOR 1ST FEED ==========================
                die_edge_contact_length__per_bite_type = self._die_edge_contact_length__per_bite_type(bite_num, num_of_bites,
                                                                                                      die_edge_contact_length__full,
                                                                                                      die_edge_contact_length__part_of_next_feed,
                                                                                                      die_edge_contact_length__part_of_theoretical_feed)
                if bite_num == 1:
                    theoretical_initial_contact_length = nominal_feed
                else:
                    theoretical_initial_contact_length = nominal_feed - die_edge_contact_length__full

                residual_length_elongation_increment = self._residual_length_elongation_increment(initial_height, initial_length,
                                                                                                  initial_residual_length, theoretical_initial_contact_length,
                                                                                                  half_penetration, first_tail_barrel_length, last_tail_barrel_length)
                if bite_num == 1:
                    initial_contact_length = nominal_feed
                else:
                    initial_contact_length = nominal_feed - die_edge_contact_length__full + residual_length_elongation_increment

                # ================================= THEORETICAL FEED ===================================================
                if bite_num == 1:
                    theoretical_feed = nominal_feed - residual_length_elongation_increment + die_edge_contact_length__per_bite_type
                else:
                    theoretical_feed = nominal_feed

                # ================================= FINAL CONTACT LENGTH ===============================================
                if bite_num == 1:
                    final_contact_length = initial_contact_length + die_edge_contact_length__full
                elif bite_num == num_of_bites:
                    final_contact_length = initial_contact_length + die_edge_contact_length__full
                else:
                    final_contact_length = initial_contact_length + 2 * die_edge_contact_length__full

                # ================================= DISTANCE TILL DIE EDGE =============================================
                distance__till_die_edge = initial_residual_length - initial_contact_length
                relative_distance__till_initial_contact = distance__till_die_edge / initial_length

                # ================================= DISTANCE TILL DIE CENTER ===========================================
                if bite_num == num_of_bites:
                    distance__till_center_of_die = final_contact_length / 2
                else:
                    distance__till_center_of_die = distance__till_die_edge + 0.5 * die_length
                # relative_die_center = distance__till_center_of_die / initial_length

                # ================================= RESIDUAL LENGTH INCREMENT ==========================================
                # if bite_num == 1:
                #     residual_length__increment = initial_contact_length + die_edge_contact_length__full
                # elif bite_num == num_of_bites:
                #     residual_length__increment = initial_contact_length
                # else:  # First and middle bites
                residual_length__increment = initial_contact_length + die_edge_contact_length__full

                # ================================= FEED TABLE =========================================================
                # if bite_num == num_of_bites:  # Last bite
                #     feeds_table_item = ('relative_die_center', relative_die_center)
                # else:
                feeds_table_item = ('automatic_feed', 'relative_die_edge', relative_distance__till_initial_contact)

                steps['initial_residual_length'].append(initial_residual_length)
                steps['theoretical_feed'].append(theoretical_feed)
                steps['initial_contact_length'].append(initial_contact_length)
                steps['final_contact_length'].append(final_contact_length)
                steps['deformed_length_increment'].append(residual_length__increment)
                steps['distance_center_of_die_till_undeformed_tail'].append(distance__till_center_of_die)
                steps['residual_length_elongation_increment'].append(residual_length_elongation_increment)
                steps['feeds_table'].append(feeds_table_item)

                initial_residual_length -= residual_length__increment

            return steps
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()

    def _initial_forging_length_for_prolongation(self) -> float:
        row, i = self.output, self.eo
        try:
            l0 = row.at[i, 'initial_length']

            forging_length = l0

            if row.at[i, 'feed_last'] == 0.0:
                forging_length += (self._die_straight_length()
                                   - self.first_non_zero(row.loc[i, ['feed_last', 'feed_middle', 'feed_first']].to_list())
                                   )

            assert forging_length > 0.0, f"Forging length should be positive, but it is = {forging_length}"

            return forging_length
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._set_is_ready_false()

    def set_nominal_feeds_for_spiral_prolongation(self):
        try:
            row, i = self.output, self.eo
            self.assert_allowed_type_ids(50, 51, 64)

            feed_per_bite = self.accumulated.loc[self.input_index, 'feed']
            input_height = row.at[i, 'initial_height']

            _first = min(1.0 * input_height, 0.8 * self._die_straight_length())
            _middle = feed_per_bite
            _last = 0.0

            assert _first > 0.0, (f"'Feed first' was calculated based on Die length and Input height and "
                                  f"resulting value is {_first}. But value of 'Feed first' must be positive "
                                  f"and not zero. ")
            assert _middle > 0.0, (f"'Feed per bite' was entered by user with value {feed_per_bite}. But value"
                                   f"of 'Feed per bite' must be positive and not zero. ")

            row.at[i, 'feed_first'] = _first
            row.at[i, 'feed_middle'] = _middle
            row.at[i, 'feed_last'] = _last

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._set_is_ready_false()

    def _feed_table__manual_mode__single_bite(self, initial_length: float) -> dict:
        try:

            die_length = self._die_straight_length()
            die_edge_contact_length: float = self._contact_length_along_die_edge()

            # Manual forging mode (1 feed)
            final_contact_length = die_length + 2 * die_edge_contact_length

            theoretical_feed = min(initial_length, final_contact_length)
            initial_contact_length = min(initial_length, die_length)
            final_contact_length = min(initial_length, final_contact_length)
            deformed_length_increment = min(initial_length, final_contact_length)
            distance_center_of_die_till_undeformed_tail = initial_length / 2

            # Check if there are fins on billet sides after single bite (with allowed fins heights = 10 mm)
            allowed_fin_height = 10.0  # Two sides fin height = 2 * 10 mm
            penetration = self.get_out('penetration')
            if penetration == 0.0:
                relative_fin_height = 100.0
            else:
                relative_fin_height = min(100.0, 100.0 * (2 * allowed_fin_height) / self.get_out('penetration'))  # Percent, but not more than 100%
            residual_length = 0.5 * (initial_length - die_length - 2 * self._contact_length_along_die_edge(at_relative_penetration_percent=relative_fin_height))
            relative_residual_length = residual_length / initial_length

            steps = {
                'initial_residual_length': [initial_length],
                'final_residual_length': [2 * residual_length],
                'theoretical_feed': [theoretical_feed],
                'initial_contact_length': [initial_contact_length],
                'final_contact_length': [final_contact_length],
                'deformed_length_increment': [deformed_length_increment],
                'distance_center_of_die_till_undeformed_tail': [distance_center_of_die_till_undeformed_tail],

                'feeds_table': [
                    ('manual_feed', 'relative_die_center', 0.5)
                ]
            }

            if residual_length > 0.0:
                steps['initial_residual_length'].extend([residual_length, initial_length])
                steps['final_residual_length'].extend([residual_length, initial_length])
                steps['theoretical_feed'].extend([residual_length, -initial_length])
                steps['initial_contact_length'].extend(2 * [2 * residual_length])
                steps['final_contact_length'].extend(2 * [0.5 * (initial_length - die_length)])
                steps['deformed_length_increment'].extend(2 * [2 * residual_length + die_edge_contact_length])
                steps['distance_center_of_die_till_undeformed_tail'].extend([residual_length, initial_length - residual_length])

                steps['feeds_table'].extend(
                    [
                        ('manual_feed', 'relative_die_center', 0.5 * relative_residual_length),
                        ('manual_feed', 'relative_die_center', 1 - 0.5 * relative_residual_length)
                    ]
                )

            return steps

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()

    def _feed_table__manual_mode__num_of_bites__multiple_bites(self, initial_length: float, initial_height: float, first_and_last_tails_barrels: list, middle_of_die_edge__at_relative_penetration_percent: float = 30.0) -> dict:
        try:
            num_of_bites = self.get_out('num_of_bites')
            theoretical_feeds = [initial_length / num_of_bites] * num_of_bites
            die_length = self._die_straight_length()
            half_penetration = 0.5 * self.get_out('penetration')
            first_tail_barrel_length = first_and_last_tails_barrels[0]
            last_tail_barrel_length = first_and_last_tails_barrels[1]

            # ============================= COMPENSATION OF DIE EDGE CONTACT LENGTH ====================================
            die_edge_contact_length__full: float = self._contact_length_along_die_edge()
            die_edge_contact_length__part_of_theoretical_feed: float = self._contact_length_along_die_edge(at_relative_penetration_percent=middle_of_die_edge__at_relative_penetration_percent)
            die_edge_contact_length__part_of_next_feed: float = die_edge_contact_length__full - die_edge_contact_length__part_of_theoretical_feed

            initial_residual_length: float = initial_length

            steps = {
                'initial_residual_length': [],
                'theoretical_feed': [],
                'initial_contact_length': [],
                'final_contact_length': [],
                'deformed_length_increment': [],
                'distance_center_of_die_till_undeformed_tail': [],
                'residual_length_elongation_increment': [],
                'feeds_table': []
            }

            for bite_index, theoretical_feed in enumerate(theoretical_feeds):  # Except last bite
                bite_num = bite_index + 1

                # ======================== COMPENSATION OF TAIL DOUBLE BARRELING FOR 1ST FEED ==========================
                die_edge_contact_length__per_bite_type = self._die_edge_contact_length__per_bite_type(bite_num, num_of_bites,
                                                                                                      die_edge_contact_length__full,
                                                                                                      die_edge_contact_length__part_of_next_feed,
                                                                                                      die_edge_contact_length__part_of_theoretical_feed)
                theoretical_initial_contact_length = theoretical_feed - die_edge_contact_length__per_bite_type

                residual_length_elongation_increment = self._residual_length_elongation_increment(initial_height, initial_length,
                                                                                                  initial_residual_length, theoretical_initial_contact_length,
                                                                                                  half_penetration, first_tail_barrel_length, last_tail_barrel_length)

                # ================================= INITIAL CONTACT LENGTH =============================================
                # die_edge_contact_length__per_bite_type = self._die_edge_contact_length__per_bite_type(bite_num, num_of_bites,
                #                                                                                       die_edge_contact_length__full,
                #                                                                                       die_edge_contact_length__part_of_next_feed,
                #                                                                                       die_edge_contact_length__part_of_theoretical_feed)
                initial_contact_length = theoretical_feed + residual_length_elongation_increment - die_edge_contact_length__per_bite_type

                # ================================= FINAL CONTACT LENGTH ===============================================
                if bite_num == 1:
                    final_contact_length = initial_contact_length + die_edge_contact_length__full
                elif bite_num == num_of_bites:
                    final_contact_length = initial_contact_length + die_edge_contact_length__full
                else:
                    final_contact_length = initial_contact_length + 2 * die_edge_contact_length__full

                # ================================= DISTANCE TILL DIE EDGE =============================================
                distance__till_die_edge = initial_residual_length - initial_contact_length
                relative_distance__till_initial_contact = distance__till_die_edge / initial_length

                # ================================= DISTANCE TILL DIE CENTER ===========================================
                if bite_num == num_of_bites:
                    distance__till_center_of_die = final_contact_length / 2
                else:
                    distance__till_center_of_die = distance__till_die_edge + 0.5 * die_length
                relative_die_center = distance__till_center_of_die / initial_length

                # ================================= RESIDUAL LENGTH INCREMENT ==========================================
                if bite_num == 1:
                    residual_length__increment = initial_contact_length + die_edge_contact_length__full
                elif bite_num == num_of_bites:
                    residual_length__increment = initial_contact_length
                else:  # First and middle bites
                    residual_length__increment = initial_contact_length + die_edge_contact_length__full

                # ================================= FEED TABLE =========================================================
                if bite_num == num_of_bites:  # Last bite
                    feeds_table_item = ('manual_feed', 'relative_die_center', relative_die_center)
                else:
                    feeds_table_item = ('manual_feed', 'relative_die_edge', relative_distance__till_initial_contact)

                steps['initial_residual_length'].append(initial_residual_length)
                steps['theoretical_feed'].append(theoretical_feed)
                steps['initial_contact_length'].append(initial_contact_length)
                steps['final_contact_length'].append(final_contact_length)
                steps['deformed_length_increment'].append(residual_length__increment)
                steps['distance_center_of_die_till_undeformed_tail'].append(distance__till_center_of_die)
                steps['residual_length_elongation_increment'].append(residual_length_elongation_increment)
                steps['feeds_table'].append(feeds_table_item)

                initial_residual_length -= residual_length__increment

            return steps

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()

    @staticmethod
    def _die_edge_contact_length__per_bite_type(bite_num, num_of_bites,
                                                die_edge_contact_length__full,
                                                die_edge_contact_length__part_of_next_feed,
                                                die_edge_contact_length__part_of_theoretical_feed) -> float:
        if bite_num == 1:  # First bite
            die_edge_contact_length__per_bite_type = die_edge_contact_length__part_of_theoretical_feed
        elif bite_num == num_of_bites:  # Last bite
            die_edge_contact_length__per_bite_type = die_edge_contact_length__part_of_next_feed
        else:
            die_edge_contact_length__per_bite_type = die_edge_contact_length__full
        return die_edge_contact_length__per_bite_type

    def _feed_table__manual_mode__feed_control__multiple_bites(self, initial_length: float, initial_height: float, first_and_last_tails_barrels: list, middle_of_die_edge__at_relative_penetration_percent: float = 30.0, starting_initial_residual_length: float = 0.0) -> dict:
        try:
            die_length = self._die_straight_length()
            # ============================= COMPENSATION OF DIE EDGE CONTACT LENGTH ====================================
            die_edge_contact_length__full: float = self._contact_length_along_die_edge()
            # die_edge_contact_length__part_of_theoretical_feed: float = self._contact_length_along_die_edge(at_relative_penetration_percent=middle_of_die_edge__at_relative_penetration_percent)

            # =============================================== FEED =====================================================
            _first, _middle, _last = self.output.loc[self.eo, ['feed_first', 'feed_middle', 'feed_last']].to_list()
            nominal_middle = self.first_non_zero(_middle, _first)
            nominal_first = nominal_middle if starting_initial_residual_length else _first
            nominal_last = self.first_non_zero(_last, _middle, nominal_first)

            # =========================================== NUM OF BITES =================================================
            # middle_length = initial_length - (nominal_first + die_edge_contact_length__full) - nominal_last
            # middle_length = max(0.0, middle_length)  # Zero if negative
            middle_feed__with_die_edge = nominal_middle + die_edge_contact_length__full
            assert middle_feed__with_die_edge > 0, "Middle feed is zero or negative"
            # initial_guess_middle_bites_count_float: float = middle_length / middle_feed__with_die_edge
            # middle_bites_count: int = max(0, math.floor(initial_guess_middle_bites_count_float / 2 - 1))

            # ============================= COMPENSATION OF DIE EDGE CONTACT LENGTH ====================================
            die_edge_contact_length__full: float = self._contact_length_along_die_edge()
            die_edge_contact_length__part_of_theoretical_feed: float = self._contact_length_along_die_edge(at_relative_penetration_percent=middle_of_die_edge__at_relative_penetration_percent)
            die_edge_contact_length__part_of_next_feed: float = die_edge_contact_length__full - die_edge_contact_length__part_of_theoretical_feed

            # ======================================= CYCLE OF THEORETICAL FEEDS =======================================
            def __residual_length__table(_initial_contact_length__table: list[float]) -> tuple[float, list, list]:
                try:
                    _num_of_bites = len(_initial_contact_length__table)
                    one_side_penetration = 0.5 * self.get_out('penetration')
                    first_tail_barrel_length = first_and_last_tails_barrels[0]
                    last_tail_barrel_length = first_and_last_tails_barrels[1]

                    _initial_residual_length: float = starting_initial_residual_length
                    _initial_residual_length__table = []
                    _deformed_length_increment__table = []
                    for _bite_index, _initial_contact_length in enumerate(_initial_contact_length__table):  # Except last bite
                        _bite_num = _bite_index + 1
                        _initial_residual_length__table.append(_initial_residual_length)
                        _residual_length_elongation_increment = self._residual_length_elongation_increment(initial_height, initial_length,
                                                                                                           _initial_residual_length, _initial_contact_length,
                                                                                                           one_side_penetration, first_tail_barrel_length,
                                                                                                           last_tail_barrel_length)
                        die_edge_contact_length__full__except_last_feed = die_edge_contact_length__full if _bite_num != _num_of_bites else 0.0  # Except last bite
                        _deformed_length_increment = _initial_contact_length + die_edge_contact_length__full__except_last_feed - _residual_length_elongation_increment

                        _deformed_length_increment__table.append(_deformed_length_increment)

                        _initial_residual_length -= _deformed_length_increment
                    residual_length__error = abs(_initial_residual_length)
                    return residual_length__error, _initial_residual_length__table, _deformed_length_increment__table
                except Exception as _e:
                    LOGGER.error(f"{self.log_id} {type(_e).__name__}: {_e}")
                    raise

            def __residual_length__error(nominal_feed__correction_coefficient__numpy: np.ndarray, _nominal_feeds__table: list[float]) -> float:
                try:
                    nominal_feed__correction_coefficient = nominal_feed__correction_coefficient__numpy[0].item()
                    corrected_feeds__table = [nominal_feed * nominal_feed__correction_coefficient for nominal_feed in _nominal_feeds__table]
                    residual_length__error, _, _ = __residual_length__table(corrected_feeds__table)
                    return residual_length__error
                except Exception as _e:
                    LOGGER.error(f"{self.log_id} {type(_e).__name__}: {_e}")
                    raise

            def _nominal_feeds_table(_num_of_bites: int) -> list:
                try:
                    _first_feeds_count = 0 if starting_initial_residual_length > 0.0 else 1
                    _last_feeds_count = 1
                    _middle_feeds_count = _num_of_bites - _first_feeds_count - _last_feeds_count
                    return [nominal_first] * _first_feeds_count + [nominal_middle] * _middle_feeds_count + [nominal_last] * _last_feeds_count
                except Exception as _e:
                    LOGGER.error(f"{self.log_id} {type(_e).__name__}: {_e}")
                    raise

            def __feeds_table__and__deviation(_num_of_bites: int) -> tuple[float, float]:
                try:
                    _nominal_feeds__table = _nominal_feeds_table(_num_of_bites)
                    # _num_of_bites = len(_nominal_feeds__table)
                    die_edge_contact_length__total_sum = (_num_of_bites - 1) * die_edge_contact_length__full
                    billet_length__excluding__die_edges = initial_length - starting_initial_residual_length - die_edge_contact_length__total_sum
                    nominal_feed__correction_coefficient__initial_guess = billet_length__excluding__die_edges / sum(_nominal_feeds__table)
                    _optimization_function = optimize.minimize(fun=__residual_length__error,
                                                               x0=np.array([nominal_feed__correction_coefficient__initial_guess]),
                                                               args=(_nominal_feeds__table,),
                                                               tol=0.1)
                    nominal_feed__correction_coefficient__optimal: float = _optimization_function.x.item(0)
                    initial_contact_length__standard_deviation: float = sum([(nominal_feed * (1 - nominal_feed__correction_coefficient__optimal)) ** 2 for nominal_feed in _nominal_feeds__table]) / _num_of_bites
                    return nominal_feed__correction_coefficient__optimal, initial_contact_length__standard_deviation
                except Exception as _e:
                    LOGGER.error(f"{self.log_id} {type(_e).__name__}: {_e}")
                    raise

            def _optimal_num_of_bites():
                try:
                    _num_of_bites__optimal = 1
                    _feed_correction_coefficient__optimal, _standard_deviation__minimum = __feeds_table__and__deviation(_num_of_bites=_num_of_bites__optimal)
                    _num_of_bites = _num_of_bites__optimal
                    while True:
                        _num_of_bites += 1
                        _feed_correction_coefficient__new, _standard_deviation__new = __feeds_table__and__deviation(_num_of_bites=_num_of_bites)
                        if _standard_deviation__new < _standard_deviation__minimum:
                            _feed_correction_coefficient__optimal, _num_of_bites__optimal, _standard_deviation__minimum = _feed_correction_coefficient__new, _num_of_bites, _standard_deviation__new
                        else:
                            break
                    return _feed_correction_coefficient__optimal, _num_of_bites__optimal
                except Exception as _e:
                    LOGGER.error(f"{self.log_id} {type(_e).__name__}: {_e}")
                    raise

            # ===================================== BITES CALCULATION ==================================================
            feed_correction_coefficient__optimal, num_of_bites__optimal = _optimal_num_of_bites()
            nominal_feeds__table = _nominal_feeds_table(num_of_bites__optimal)
            initial_contact_length__table = [nominal_feed * feed_correction_coefficient__optimal for nominal_feed in nominal_feeds__table]
            _, initial_residual_length__table, deformed_length_increment__table = __residual_length__table(initial_contact_length__table)

            steps = {
                'initial_residual_length': initial_residual_length__table,  # calculated in '__residual_length__table()'
                'theoretical_feed': [],
                'initial_contact_length': initial_contact_length__table,
                'final_contact_length': [],
                'deformed_length_increment': deformed_length_increment__table,  # calculated in '__residual_length__table()'
                'distance_center_of_die_till_undeformed_tail': [],
                'residual_length_elongation_increment': [],
                'feeds_table': []
            }

            num_of_bites = len(initial_residual_length__table)
            for bite_index in range(num_of_bites):
                bite_num = bite_index + 1
                initial_contact_length = initial_contact_length__table[bite_index]
                initial_residual_length = initial_residual_length__table[bite_index]

                # ================================= THEORETICAL FEED ===================================================
                if bite_num == 1:
                    theoretical_feed = deformed_length_increment__table[bite_index] - die_edge_contact_length__part_of_next_feed
                elif bite_num == num_of_bites:
                    theoretical_feed = deformed_length_increment__table[bite_index] + die_edge_contact_length__part_of_next_feed
                else:
                    theoretical_feed = deformed_length_increment__table[bite_index]

                # ================================= FINAL CONTACT LENGTH ===============================================
                if bite_num == 1 or bite_num == num_of_bites:
                    final_contact_length = initial_contact_length + die_edge_contact_length__full
                else:
                    final_contact_length = initial_contact_length + 2 * die_edge_contact_length__full

                # ================================= DISTANCE TILL DIE EDGE =============================================
                distance__till_die_edge = initial_residual_length - initial_contact_length
                relative_distance__till_initial_contact = distance__till_die_edge / initial_length

                # ================================= DISTANCE TILL DIE CENTER ===========================================
                if bite_num == num_of_bites:
                    distance__till_center_of_die = final_contact_length / 2
                else:
                    distance__till_center_of_die = distance__till_die_edge + 0.5 * die_length
                relative_die_center = distance__till_center_of_die / initial_length

                # ================================= RESIDUAL LENGTH INCREMENT ==========================================
                # if bite_num == 1:
                #     residual_length__increment = initial_contact_length + die_edge_contact_length__full
                # elif bite_num == num_of_bites:
                #     residual_length__increment = initial_contact_length
                # else:  # First and middle bites
                #     residual_length__increment = initial_contact_length + die_edge_contact_length__full

                # ================================= FEED TABLE =========================================================
                if bite_num == num_of_bites:  # Last bite
                    feeds_table_item = ('manual_feed', 'relative_die_center', relative_die_center)
                else:
                    feeds_table_item = ('manual_feed', 'relative_die_edge', relative_distance__till_initial_contact)

                steps['theoretical_feed'].append(theoretical_feed)
                steps['final_contact_length'].append(final_contact_length)
                # steps['deformed_length_increment'].append(residual_length__increment)
                steps['distance_center_of_die_till_undeformed_tail'].append(distance__till_center_of_die)
                # steps['residual_length_elongation_increment'].append(residual_length_elongation_increment)
                steps['feeds_table'].append(feeds_table_item)

            return steps

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _residual_length_elongation_increment(self,
                                              initial_height,
                                              initial_length,
                                              initial_residual_length,
                                              initial_contact_length,
                                              one_side_penetration,
                                              first_tail_barrel_length,
                                              last_tail_barrel_length):
        try:
            initial_deformed_length = initial_length - initial_residual_length
            first_shearing_line__length_projection__full = first_tail_barrel_length + initial_deformed_length + initial_contact_length
            last_shearing_line__length_projection__full = last_tail_barrel_length + initial_residual_length
            first_shearing_line__length_projection__till_billet_axis = max(1E-3,
                                                                           min(initial_height, first_shearing_line__length_projection__full))
            last_shearing_line__length_projection__till_billet_axis = max(1E-3,
                                                                          min(initial_height, last_shearing_line__length_projection__full))
            relative_asymmetric_sharing_lines = (last_shearing_line__length_projection__till_billet_axis - first_shearing_line__length_projection__till_billet_axis) / initial_height
            residual_length_elongation_coef = 2 * math.atan(relative_asymmetric_sharing_lines) / math.pi  # From 1 to -1
            residual_length_elongation_increment = one_side_penetration * max(0.0, residual_length_elongation_coef)  # Only positive values
            return residual_length_elongation_increment
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _feed_table__manual_feed__control_last_feed(self, initial_length: float, initial_height: float) -> dict:
        row, i = self.output, self.eo
        try:
            # ============================ DIE PARAM =========================================================
            die_length = self._die_straight_length()
            die_edge_contact_length: float = self._contact_length_along_die_edge()

            # ============================ FEED ==============================================================
            _first, _middle, _last = row.loc[i, pd.Index(('feed_first', 'feed_middle', 'feed_last'))]

            nominal_first = _first
            nominal_middle = self.first_non_zero(_middle, _first)
            nominal_last = self.first_non_zero(_last, _middle, _first)

            feed_first_correction = -1 * self._contact_length_along_die_edge(at_relative_penetration_percent=10.0)
            feed_middle_correction = self._contact_length_along_die_edge(at_relative_penetration_percent=10.0)
            feed_last_correction = self._contact_length_along_die_edge(at_relative_penetration_percent=10.0)
            #
            abs_first = nominal_first + feed_first_correction
            abs_middle = nominal_middle + feed_middle_correction
            abs_last = nominal_last + feed_last_correction
            #
            count_first = 1
            count_middle = int(round((initial_length - abs_first - abs_last) / abs_middle, 0))
            count_last = 1
            #
            feed_factor = (initial_length
                           - feed_first_correction
                           - feed_middle_correction * count_middle
                           - feed_last_correction
                           ) / (nominal_first + nominal_middle * count_middle + nominal_last)
            #
            abs_first = feed_factor * nominal_first + feed_first_correction
            abs_middle = 0.0 if count_middle == 0 else feed_factor * nominal_middle + feed_middle_correction
            abs_last = feed_factor * nominal_last + feed_middle_correction

            # --------------------------------------------------------------------

            return (
                [abs_first, abs_middle, 0.0, abs_last],  # feeds
                [count_first, count_middle, 0, count_last])  # feeds_counts

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()

    @staticmethod
    def first_non_zero(*args) -> float:
        for _f in args:
            if _f > 0.0:
                return _f
        return 0.0

    def __evaluate_feed_count_roughly(self, length_excluding_tails: float) -> float:
        row, i = self.output, self.eo
        try:
            if self.type_id in (83, 90, 82):  # Num of Bites
                return row.at[i, 'num_of_bites']

            _first, _middle, _last = row.loc[i, pd.Index(('feed_first', 'feed_middle', 'feed_last'))]
            assert _first > 0.0, f"'feed_first' must be positive and not zero, but {_first}"
            assert _middle >= 0.0, f"'feed_middle' must be positive, but {_middle}"
            assert _last >= 0.0, f"'feed_last' must be positive, but {_last}"

            # ------------------------ First feed -------------------------------
            first_feed_count = length_excluding_tails / _first
            if first_feed_count <= 1.0:
                feed_count = first_feed_count

            else:
                # ------------------------ Last feed ------------------------------
                last_feed = self.first_non_zero(_last, _middle, _first)
                last_feed_count = (length_excluding_tails - _first) / last_feed
                if last_feed_count <= 1.0:
                    feed_count = 1.0 + last_feed_count

                else:
                    # ------------------------- Other feeds -----------------------------
                    other_feeds = self.first_non_zero(_middle, _first)
                    feed_count = 2.0 + (length_excluding_tails - _first - last_feed) / other_feeds

            assert feed_count > 0.0, f"Rough evaluation of Feed count should be above zero, but {feed_count}"

            return feed_count

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._set_is_ready_false()

    def _bites_table(self):
        row, i = self.output, self.eo
        try:
            osp = row.at[i, 'operation_specific_parameters']

            self.assert_allowed_type_ids(46, 50, 51, 64, 80, 82, 95, 96, 83, 90)

            left_and_right_tail_barrels: list = self._tails_x_length()
            is_starts_from_right_tail = self.get_out('feed_direction_name') == '<=='
            first_and_last_tails_barrels = left_and_right_tail_barrels[::-1] if is_starts_from_right_tail else left_and_right_tail_barrels

            length_excluding_tails = self.get_out('initial_length') - sum(left_and_right_tail_barrels)

            self._set_is_press_in_automatic_mode(length_excluding_tails)

            l, h = length_excluding_tails, self.get_out('initial_height')
            if self.parent_type_id == 37:  # Upsetting operations
                l, h = h, l

            step_control = self.get_out('step_control')
            assert step_control in ('StepsNum', 'Feed',), f"TEMPORARY ASSERT. 'step_control' must be 'StepsNum' or 'Feed' but it is '{step_control}'"

            # ================================ FEED MODE:  AUTOMATIC ===================================================
            if self.get_out('is_press_in_automatic_mode'):
                last_manual_feeds_count = config.services['pre']['operations_settings']['prolongation']['automatic_feed_control']['when_last_feed_is_controlled']['last_manual_feeds_count']
                is_control_last_feed = self.get_out('feed_last') > 0.0 and last_manual_feeds_count > 0

                if is_control_last_feed:  # Is control last feed
                    steps = self._feed_table__automatic_feed__control_last_feed(initial_length=l,
                                                                                initial_height=h,
                                                                                first_and_last_tails_barrels=first_and_last_tails_barrels,
                                                                                middle_of_die_edge__at_relative_penetration_percent=30.0)
                else:
                    steps = self._feed_table__automatic_feed__do_not_control_last_feed(initial_length=l,
                                                                                       initial_height=h,
                                                                                       first_and_last_tails_barrels=first_and_last_tails_barrels,
                                                                                       middle_of_die_edge__at_relative_penetration_percent=30.0)

            # =============================== FEED MODE: MANUAL ========================================================
            else:

                # =================================== MANUAL MODE: SINGLE BITE =========================================
                if self._is_single_bite(h, l, step_control):
                    steps = self._feed_table__manual_mode__single_bite(initial_length=l)

                # =================================== MANUAL MODE: MULTIPLE BITES ======================================
                else:  # Two or more bites
                    if step_control == "StepsNum":  # Operation type with Num of bites

                        # ======================================== MULTIPLE BITES:  NUMBER OF BITES ====================
                        steps = self._feed_table__manual_mode__num_of_bites__multiple_bites(initial_length=l,
                                                                                            initial_height=h,
                                                                                            first_and_last_tails_barrels=first_and_last_tails_barrels,
                                                                                            middle_of_die_edge__at_relative_penetration_percent=30.0)
                    else:
                        # ======================================== MULTIPLE BITES:  FEED CONTROL =======================
                        steps = self._feed_table__manual_mode__feed_control__multiple_bites(initial_length=l,
                                                                                            initial_height=h,
                                                                                            first_and_last_tails_barrels=first_and_last_tails_barrels,
                                                                                            middle_of_die_edge__at_relative_penetration_percent=30.0)
            osp |= steps

            # ========================================= ROTATIONS TABLE ================================================
            bites_num_to_skip = self._skip_bites_tuple()
            osp['bites_table'] = self._add_rotations_to_the_feeds_table(steps, bites_num_to_skip)

            # ==================================== ASSERT FEED POINTERS ================================================
            wrong_feed_mode = [bite_row[0] for bite_row in osp['bites_table'] if not isinstance(bite_row[0], str) or bite_row[0] not in config.services['pre']['operations_settings']['prolongation']['allowed_feed_modes']]
            assert not wrong_feed_mode, f"Wrong Feed Mode ({', '.join(wrong_feed_mode)}) used in the Bites Table. Allowed Feed Modes are: {', '.join(config.services['pre']['operations_settings']['prolongation']['allowed_feed_modes'])}"
            wrong_feed_pointers = [bite_row[1] for bite_row in osp['bites_table'] if not isinstance(bite_row[1], str) or bite_row[1] not in config.services['pre']['operations_settings']['prolongation']['allowed_feed_pointers']]
            assert not wrong_feed_pointers, f"Wrong Feed pointers ({', '.join(wrong_feed_pointers)}) used in the Bites Table. Allowed Feed pointers are: {', '.join(config.services['pre']['operations_settings']['prolongation']['allowed_feed_pointers'])}"

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise RuntimeError("Error in calculation of Bites Table")

    def _is_single_bite(self, h, l, step_control):
        is_single_bite = False
        if step_control == "StepsNum":
            if self.get_out('num_of_bites') == 1:
                is_single_bite = True
        else:  # step_control != "StepsNum":
            # Manual forging mode (1 feed)
            single_bite_criteria = config.services['pre']['operations_settings']['prolongation']['single_bite_criteria']
            die_edge_contact_length__full: float = self._contact_length_along_die_edge()

            # ========================= FEED ===================================================================
            nominal_first, _middle, _last = self.output.loc[
                self.eo, ['feed_first', 'feed_middle', 'feed_last']].to_list()
            nominal_last = self.first_non_zero(_last, _middle, nominal_first)
            average_feed = (nominal_first + nominal_last) / 2
            min_feed = min(nominal_first, nominal_last)
            assert min_feed > 0, "First or Last feed is zero or negative"

            # ========================= CRITERIA: IS BILLET TOO SHORT ==========================================
            actual_length_to_feed_ratio = l / nominal_first
            is_billet_too_short = actual_length_to_feed_ratio <= single_bite_criteria['length_to_feed_ratio']

            # ========================= CRITERIA: IS BILLET TOO TALL ===========================================
            actual_height_to_feed_ratio = h / min_feed
            is_billet_too_high = actual_height_to_feed_ratio >= single_bite_criteria['height_to_feed_ratio']
            # is_billet_too_high = False

            # ========================= CRITERIA: THERE IS NO PLACE FOR TWO FEEDS ==============================
            half_billet_length = 0.5 * (l - die_edge_contact_length__full)
            relative_excess_of_billet_length_for_single_bite = (l - nominal_first) / nominal_first
            relative_lack_of_billet_length_for_two_bites = (average_feed - half_billet_length) / average_feed
            is_no_place_for_two_feeds = True if relative_lack_of_billet_length_for_two_bites > relative_excess_of_billet_length_for_single_bite else False

            # ========================= CRITERIA: FINAL ========================================================
            is_single_bite = is_no_place_for_two_feeds or is_billet_too_short or is_billet_too_high  # For Feed Control only
        return is_single_bite

    def row(self, key: str, value):
        self.output.loc[self.eo, key] = value

    def _set_is_press_in_automatic_mode(self, length_excluding_tails: float):
        try:
            if self.type_id in (82, 83, 90):  # Num of Bites
                return False

            press_mode_id = self.output.loc[self.eo, 'press_mode_id']
            max_manual_feed_count = config.lib['press_mode']['automatic_feed_mode_is_on_when_bites_count'][press_mode_id]
            assert max_manual_feed_count >= 0, (f"Parameter of 'automatic_feed_mode_is_on_when_bites_count' "
                                                f"of 'press_mode' should be positive or zero, "
                                                f"but it is = {max_manual_feed_count}")

            approx_feeds_count = self.__evaluate_feed_count_roughly(length_excluding_tails)

            self.output.loc[self.eo, 'is_press_in_automatic_mode'] = (approx_feeds_count > max_manual_feed_count)

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise RuntimeError("Error in calculating a boolean value meaning Automatic feed control of a Press: True=Automatic, False=Manual")

    def assert_allowed_type_ids(self, *args):
        assert self.type_id in args, \
            f"'type_id' '{self.type_id}' is not in allowed 'type_id' list '{', '.join(map(str, args))}'"

    def _skip_bites_tuple(self) -> tuple:
        try:
            if self.type_id == 90:
                skip_bites_string = self.accumulated.loc[self.input_index, 'skip_bites']
                skip_bites: list = []
                error_values: list = []
                for value in [_s.strip() for _s in skip_bites_string.split(",")]:
                    if value.isdigit():
                        skip_bites.append(int(value))
                    else:
                        error_values.append(value)

                assert not error_values, (
                    f"Input filed 'skip_bites'='{skip_bites_string}' should contain single Integer value or Integer "
                    f"values separated by commas, but it contains wrong values: {', '.join(error_values)}")

                return tuple(skip_bites)
            else:
                return tuple()
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise RuntimeError("Error in calculating list of bite numbers which should be skipped")

    def _OBSOLETE_generate_table_of_billet_rotations_and_die_center_positions(self, steps: dict, skip_bites: tuple, length_excluding_tails: float):
        row, i = self.output, self.eo
        try:
            osp = row.at[i, 'operation_specific_parameters']

            counts = self.get_out(
                ('simulation_feed_first_count',
                 'simulation_feed_middle_count',
                 'simulation_feed_before_last_count',
                 'simulation_feed_last_count'))

            feeds = self.get_out(
                ('simulation_feed_first',
                 'simulation_feed_middle',
                 'simulation_feed_before_last',
                 'simulation_feed_last'))

            rotations_per_feed = osp['rotations_count_per_feed_list']
            rotation_per_bite = osp['rotation_per_bite']

            die_length = self._die_straight_length()
            is_control_last_feed = feeds[-1] > 0.0
            total_bite_blocks_num = sum(counts)
            bite_blocks_count = 0
            abs_bites_table = []
            unforged_length_of_billet_left = length_excluding_tails

            def __add_feed_rotation_bite(feed: float, rotation: float):
                nonlocal length_excluding_tails, unforged_length_of_billet_left, abs_bites_table, die_length, is_control_last_feed, total_bite_blocks_num
                """
                
                """
                is_last_controlled_feed = bite_blocks_count == total_bite_blocks_num and is_control_last_feed
                #
                unforged_length_of_billet_left -= (0.5 * feed) if is_last_controlled_feed else feed
                abs_position_of_die_center = unforged_length_of_billet_left if is_last_controlled_feed else (unforged_length_of_billet_left + 0.5 * die_length)
                #
                abs_bites_table.append([rotation, abs_position_of_die_center])

            def __add_bites_blocks(cycles_count, feed, rotations_per_bites_block):
                """
                Bite block consist of:
                    1 x (Feed + Rotation + Bite)
                    N x (Rotation + Bite)
                """
                nonlocal bite_blocks_count, skip_bites

                for _ in range(cycles_count):
                    bite_blocks_count += 1
                    if bite_blocks_count in skip_bites:
                        continue
                    # Calculate first rotation of first block
                    first_rotation = 0.0 if bite_blocks_count == 1 else rotation_per_bite
                    # Add a Bites Block
                    __add_feed_rotation_bite(feed=feed, rotation=first_rotation)
                    if rotations_per_bites_block >= 1:
                        for _ in range(rotations_per_bites_block - 1):
                            __add_feed_rotation_bite(feed=0.0, rotation=rotation_per_bite)

            if total_bite_blocks_num == 1:
                abs_bites_table = [
                    [0.0, 0.5]  # [billet rotation, die center position]
                ]
                if self.get_out('final_length') > die_length:
                    relative_die_length = die_length / length_excluding_tails
                    relative_length_of_each_remaining_unforged_sections = 0.5 * (self.get_out('final_length') - die_length) / length_excluding_tails
                    relative_positions_of_die_center = [
                        relative_length_of_each_remaining_unforged_sections - 0.25 * relative_die_length,
                        (1 - relative_length_of_each_remaining_unforged_sections) + 0.25 * relative_die_length
                    ]
                    abs_bites_table.extend([
                        [0.0, relative_positions_of_die_center[0]],
                        [0.0, relative_positions_of_die_center[1]]
                    ])
            else:
                # FIRST FEED
                __add_bites_blocks(counts[0], feeds[0], rotations_per_feed[0])

                # MIDDLE FEED
                __add_bites_blocks(counts[1], feeds[1], rotations_per_feed[1])

                # BEFORE LAST FEED
                __add_bites_blocks(counts[2], feeds[2], rotations_per_feed[2])

                # LAST FEED
                __add_bites_blocks(counts[3], feeds[3], rotations_per_feed[3])

            relative_bites_table = [[rotation, (abs_position / length_excluding_tails)] for (rotation, abs_position) in abs_bites_table]

            osp['abs_bites_table'] = abs_bites_table
            osp['bites_table'] = relative_bites_table

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()

    def _add_rotations_to_the_feeds_table(self, steps: dict, skip_bites: tuple) -> list:
        row, i = self.output, self.eo
        try:
            osp = row.at[i, 'operation_specific_parameters']

            feeds_table = steps['feeds_table']

            rotation_per_bite = osp['rotation_per_bite']

            # Rotations per feed
            rotations_per_first_feed, rotations_per_middle_feed, rotations_per_last_feed,  = osp['rotations_count_per_feed_list']
            rotations_per_feed_list = [rotations_per_middle_feed] * len(feeds_table)
            rotations_per_feed_list[0] = rotations_per_first_feed
            if len(feeds_table) >= 2:
                rotations_per_feed_list[-1] = rotations_per_last_feed

            # ================================= ABSOLUTE POSITIONS OF DIE CENTER =======================================
            bites_table = []

            """
            Bite block consist of:
                1 x (Feed + Rotation + Bite)
                N x (Rotation + Bite)
            """
            for bite_block_index, rotations_per_bites_block in enumerate(rotations_per_feed_list):
                feed_mode, feed_pointer, feed = feeds_table[bite_block_index]
                if (bite_block_index + 1) in skip_bites:
                    continue
                first_rotation = 0.0 if bite_block_index == 0 else rotation_per_bite  # Calculate first rotation of first block
                bites_table.append([feed_mode, feed_pointer, first_rotation, feed])
                rotations_per_bites_block -= 1
                if rotations_per_bites_block > 0:
                    for _ in range(rotations_per_bites_block):
                        bites_table.append([feed_mode, feed_pointer, rotation_per_bite, 0.0])

            return bites_table

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()

    def _num_of_bites(self):
        row, i = self.output, self.eo
        try:
            if self.type_id == 93:  # Single upsetting
                result = 1
            elif self.type_id == 91:  # Single OR triple upsetting
                if pd.notna(row.at[i, 'feed_middle']) and row.at[i, 'feed_middle'] > 0:
                    result = 3
                else:
                    result = 1
            elif self.type_id == 94:  # Triple upsetting
                result = 3
            elif self.type_id == 92:  # Tail flattening
                billet_width = row.at[i, 'initial_height']
                result = round(billet_width / row.at[i, 'feed_first'])
            elif self.type_id == 100:  # Tail chamfering
                if pd.notna(row.at[i, 'feed_middle']) and row.at[i, 'feed_middle'] > 0:
                    result = 8
                else:
                    result = 4
            elif self.type_id in (46, 50, 51, 57, 64, 80, 82, 95, 96, 83, 90):
                """
                46, 83, 90 - Prolongation (Feed, Num of Bites, Num of Bites Skip Bites),
                50:  # spiral rounding 1 rotation per 1 feed
                50:  # spiral rounding 1 rotation per 1 feed
                80:  (Obsolete) Radial prolongation Feed
                82:  (Obsolete) Radial prolongation Num of Bites
                95:  # Radial prolongation Feed
                96:  # Radial prolongation Num of Bites
                64:  # radial forging (GFM) spiral rounding 1 rotation per 1 feed
                """
                result = len(row.at[i, 'operation_specific_parameters']['bites_table'])
            elif self.type_id == 57:  # Hot Cutting percentage
                pieces_count = int(self.accumulated.loc[self.input_index, 'pieces_count'].item())
                cut_count = pieces_count - 1
                result = cut_count * 4
            elif self.type_id == 86:  # Cold Sawing percentage
                pieces_count = int(self.accumulated.loc[self.input_index, 'pieces_count'].item())
                cut_count = pieces_count - 1
                result = cut_count * 4
            else:
                raise KeyError(f"'type_id' {self.type_id} is not recognized")

            assert isinstance(result, int), f"Type of 'num_of_bites' is not integer, but {type(result)}"
            assert result > 0, f"Value of 'num_of_bites' is not positive, but {result}"

            row.at[i, 'num_of_bites'] = result

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def feed_weighted_arithmetic_mean(self) -> float:
        row, i = self.output, self.eo
        try:
            _first = row.at[i, 'feed_first']
            _middle = row.at[i, 'feed_middle']
            _last = row.at[i, 'feed_last']

            assert _first > 0.0, f"Value of 'feed_first' should be above zero, but {_first}"
            assert _middle >= 0.0, f"Value of 'feed_middle' should be zero or above, but {_middle}"
            assert _last >= 0.0, f"Value of 'feed_last' should be zero or above, but {_last}"

            approx_feeds_count = self.__evaluate_feed_count_roughly(row.at[i, 'initial_length'])

            if approx_feeds_count < 1.0:
                return _first

            last_feed = self.first_non_zero(_last, _middle, _first)
            if approx_feeds_count < 2.0:
                return (_first + last_feed) / 2

            other_feeds = self.first_non_zero(_middle, _first)
            other_feeds_count = approx_feeds_count - 2
            return (_first + last_feed + other_feeds * other_feeds_count) / approx_feeds_count

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _initial_length_of_contact(self):
        """Calculate elongation coefficient"""
        row, i = self.output, self.eo
        try:
            min_straight_length_of_dies = self._die_straight_length()
            billet_width = row.at[i, 'initial_height']

            type_id = row.at[i, 'type_id']
            if type_id in (93, 91, 94):  # 93 - Single upsetting, 91 - Single OR triple upsetting, 94 - Triple upsetting
                result = min(min_straight_length_of_dies, billet_width)
            elif type_id == 92:  # Tail flattening
                radius, _ = self._edge_radius_of_shortest_die()
                half_penetration = row.at[i, 'penetration'] / 2
                # Die impression will exceed the theoretical feed. Depth of die impression at the end of
                # theoretical feed is equal to half of one side penetration.
                ry = half_penetration / 2  # Depth of die impression at the end of theoretical feed
                if ry >= radius:
                    rx = radius
                else:
                    rx = math.sqrt(ry * (2 * radius - ry))  # Length of die radius impression
                result = row.at[i, 'feed_first'] - rx
            elif type_id == 100:  # Tail chamfering
                result = 1.0
            elif type_id in (50, 51,):  # Prolongation
                result = row.at[i, 'feed_first']  # First feed
            elif type_id in (46, 80, 82, 95, 96, 83, 90):
                """
                46 - Axial prolongation
                83 - Axial prolongation Num of Bites
                90 - Axial prolongation Num of Bites, Skip bites
                80 - (Obsolete) Radial prolongation Feed, 
                82 - (Obsolete) Radial prolongation Num of Bites
                95 - Radial prolongation Feed, 
                96 - Radial prolongation Num of Bites
                """
                ini_l = row.at[i, 'initial_length']
                assert ini_l > 0.0, f"Value of 'initial_length' is not positive, but {ini_l}"
                result = min(self.feed_weighted_arithmetic_mean(), ini_l)
            elif type_id == 52:  # Full die
                result = row.at[i, 'initial_length']
            elif type_id == 64:  # Radial forging (GFM)
                result = row.at[i, 'feed_first']  # First feed
            else:
                raise KeyError(f"Unknown 'type_id': {type_id}")

            row.at[i, 'initial_length_of_contact'] = result

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def prolongation_final_length_of_contact(self):
        """Calculate final_length_of_contact"""
        row, i = self.output, self.eo
        try:
            radius_contact_length = self._contact_length_along_die_edge()
            num_of_bites = self.__evaluate_feed_count_roughly(row.at[i, 'initial_length'])
            _first, _middle, _last = row.loc[i, pd.Index(('feed_first', 'feed_middle', 'feed_last'))]
            assert _first > 0.0, f"'feed_first' must be positive and not zero, but {_first}"
            assert _middle >= 0.0, f"'feed_middle' must be positive, but {_middle}"
            assert _last >= 0.0, f"'feed_last' must be positive, but {_last}"

            if _middle > 0.0 and _last > 0.0:
                if num_of_bites < 3:
                    final_length_of_contact = _first + radius_contact_length
                else:
                    _first_and_last = _first + radius_contact_length
                    _middle_bite_count = num_of_bites - 2
                    _middle = _middle + 2 * radius_contact_length
                    total_contact_length = 2 * _first_and_last + _middle_bite_count * _middle
                    final_length_of_contact = total_contact_length / num_of_bites

            elif _middle > 0.0:
                if num_of_bites == 1:
                    final_length_of_contact = _first + radius_contact_length
                else:
                    _middle_bite_count = num_of_bites - 1
                    _middle = _middle + 2 * radius_contact_length
                    total_contact_length = _first + radius_contact_length + _middle_bite_count * _middle
                    final_length_of_contact = total_contact_length / num_of_bites

            else:
                final_length_of_contact = _first + radius_contact_length

            assert final_length_of_contact > 0.0, (f"Value of 'final_length_of_contact' should be above zero, "
                                                   f"but {final_length_of_contact}")
            row.at[i, 'final_length_of_contact'] = final_length_of_contact

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._set_is_ready_false()

    def _upsetting_final_length_of_contact(self):
        """Calculate final_length_of_contact"""
        row, i = self.output, self.eo
        try:
            one_side_penetration = row.at[i, 'penetration'] / 2
            working_length_of_dies = self._actual_working_length_of_dies(one_side_penetration)
            billet_width = row.at[i, 'initial_height']

            match row.at[i, 'type_id']:
                case 93:  # Single upsetting
                    result = min(working_length_of_dies, billet_width)
                case 91:  # Single OR triple upsetting
                    result = min(working_length_of_dies, billet_width)
                case 94:  # Triple upsetting
                    result = min(working_length_of_dies, billet_width)
                case 92:  # Tail flattening
                    radius, _ = self._edge_radius_of_shortest_die()
                    if one_side_penetration >= radius:
                        radius_impression_length = radius
                    else:
                        # Length of die radius impression
                        radius_impression_length = math.sqrt(one_side_penetration * (2 * radius - one_side_penetration))
                    result = row.at[i, 'initial_length_of_contact'] + radius_impression_length
                case 100:  # Tail chamfering
                    result = 1.0
                case _:
                    raise KeyError(f"Unknown 'type_id': {row.at[i, 'type_id']}")

            assert result > 0.0, f"Value of 'final_length_of_contact' is not positive, but {result}"

            row.at[i, 'final_length_of_contact'] = result

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _upsetting_final_width_of_contact(self):
        """Calculate 'final_width_of_contact'"""
        row, i = self.output, self.eo
        try:
            row.at[i, 'final_width_of_contact'] = row.at[i, 'final_width']

            assert row.at[i, 'final_width_of_contact'] > 0.0, f"ValueError: 'final_width_of_contact' is not positive."

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def prolongation_final_strain_height(self):
        """Calculate final strain components for prolongation."""
        row, i = self.output, self.eo
        try:
            initial_height = row.at[i, 'initial_height']
            final_height = row.at[i, 'final_height']

            if final_height > initial_height:
                strain_height = 0.0
                LOGGER.warning(f"'final_height'={final_height:.1f} is bigger than 'initial_height'={initial_height:.1f}, i.e. deformation is zero and 'strain_height' is set to zero")
            else:
                strain_height = math.log(final_height / initial_height)

            row.at[i, 'strain_height'] = strain_height

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._set_is_ready_false()

    def prolongation_final_strain_length_and_strain_width(self):
        """Calculate final strain components for prolongation."""
        row, i = self.output, self.eo
        try:
            initial_cross_section_area = row.at[i, 'initial_cross_section_area']
            final_cross_section_area = row.at[i, 'final_cross_section_area']
            strain_height = row.at[i, 'strain_height']

            assert initial_cross_section_area > 0.0, f"ValueError: 'initial_cross_section_area' should be above zero, but {initial_cross_section_area}."
            assert final_cross_section_area > 0.0, f"ValueError: 'final_cross_section_area' should be above zero, but {final_cross_section_area}."
            assert strain_height <= 0.0, f"ValueError: 'strain_height' should be zero or below zero, but {strain_height}"

            strain_length = math.log(initial_cross_section_area / final_cross_section_area)

            assert strain_length >= 0.0, f"ValueError: 'strain_length' should be positive or zero, but {strain_length}"

            strain_width = 0 - strain_height - strain_length
            max_h_l_strain = max(abs(strain_height), abs(strain_length))

            if max_h_l_strain != 0:
                strain_width_accuracy = 4 + int(abs(math.log10(max_h_l_strain)))
                assert round(strain_width, strain_width_accuracy) >= 0.0, f"ValueError: 'strain_width' should be positive or zero, but {strain_width}"

            row.at[i, 'strain_length'] = strain_length
            row.at[i, 'strain_width'] = strain_width

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _upsetting_final_strain(self):
        """Calculate final strain components for upsetting."""
        row, i = self.output, self.eo
        try:
            strain_length = math.log(row.at[i, 'final_length'] / row.at[i, 'initial_length'])
            initial_width = row.at[i, 'initial_width']
            initial_height = row.at[i, 'initial_height']
            contact_l = row.at[i, 'initial_length_of_contact']
            contact_w = row.at[i, 'initial_width_of_contact']
            _, strain_height = strain_length_based_on_contact_shape(contact_w, contact_l, initial_width, initial_height, strain_length)
            strain_width = 0.0 - strain_length - strain_height

            row.at[i, 'strain_length'] = strain_length
            row.at[i, 'strain_height'] = strain_height
            row.at[i, 'strain_width'] = strain_width

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _die_straight_length(self):
        row, i = self.output, self.eo
        try:
            result = []
            for _id in (row.at[i, 'top_die_id'], row.at[i, 'bottom_die_id']):
                die = config.lib['die']['dimensions'][_id]
                die_straight_length = die['straight_length']
                result.append(die_straight_length)
            min_die_straight_length = min(result)
            return min_die_straight_length
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._set_is_ready_false()

    def _max_working_length_of_dies(self):
        row, i = self.output, self.eo
        try:
            result = []
            for _, _id in row.loc[i, pd.Index(('top_die_id', 'bottom_die_id'))].items():
                die = config.lib['die']['dimensions'][_id]
                length_45_deg_radius = 0.525 * die['edge_radius']
                die_working_length = die['straight_length'] + 2 * length_45_deg_radius
                result.append(die_working_length)
            min_die_working_length = min(result)
            return min_die_working_length
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._set_is_ready_false()

    def _actual_working_length_of_dies(self, one_side_penetration):
        try:
            radius, die_id = self._edge_radius_of_shortest_die()
            if one_side_penetration >= radius:
                rx = radius
            else:
                # Length of die radius impression
                rx = math.sqrt(one_side_penetration * (2 * radius - one_side_penetration))

            straight_length = config.lib['die']['dimensions'][die_id]['straight_length']
            result = straight_length + 2 * rx
            return result
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._set_is_ready_false()

    def _edge_radius_of_shortest_die(self) -> tuple[float, int]:
        row, i = self.output, self.eo
        try:
            result = []
            for _, _id in row.loc[i, pd.Index(('top_die_id', 'bottom_die_id'))].items():
                die = config.lib['die']['dimensions'][_id]
                _r = die['edge_radius']
                working_l = die['straight_length'] + 2 * _r
                result.append({'id': _id, '_r': _r, '_l': working_l})
            if result[0]['_l'] < result[1]['_l']:
                return result[0]['_r'], result[0]['id']
            result = result[1]['_r'], result[1]['id']
            return result
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._set_is_ready_false()

    def _contact_length_along_die_edge(self, at_relative_penetration_percent: float = 100.0) -> float:
        """
        Calculate total length of contact along the die radius.
        But return length of contact corresponding 'at_relative_penetration_percent'.
        For example if:
            'at_relative_penetration_percent' = 50%,
            die radius = 80 mm,
            one side penetration is equal to full height of die radius (80 mm).
        Then Contact length = R * 'contact_length_to_penetration_coef'.
        And 'contact_length_to_penetration_coef' = sin(arccos(1 - P * 'rpp'/ R /100)),
        where:
            'rpp' is equal to 'at_relative_penetration_percent',
            R - die radius,
            P - Penetration (one side penetration).
        So, 'contact_length_to_penetration_coef' = sin(arccos(1 - 50/100)) = sin(60) = 0.866
        Other examples in the table (considering that penetration = die Radius)

                                            at P = k * R:

                                            absolute_contact_length
        penetration              100.0mm          50.0mm          25.0mm          10.0mm           5.0mm           1.0mm
                  100.0%     130.0mm (7)     116.2mm (7)      85.9mm (7)      55.7mm (7)      39.7mm (7)      17.9mm (7)
                   75.0%     130.0mm (7)     102.9mm (7)      75.2mm (7)      48.4mm (7)      34.4mm (7)      15.5mm (7)
                   50.0%     116.2mm (7)      85.9mm (7)      62.0mm (7)      39.7mm (7)      28.2mm (7)      12.6mm (7)
                   40.0%     105.8mm (7)      77.5mm (7)      55.7mm (7)      35.6mm (7)      25.2mm (7)      11.3mm (7)
                   30.0%      93.3mm (7)      67.6mm (7)      48.4mm (7)      30.8mm (7)      21.9mm (7)       9.8mm (7)
                   20.0%      77.5mm (7)      55.7mm (7)      39.7mm (7)      25.2mm (7)      17.9mm (7)       8.0mm (7)
                   10.0%      55.7mm (7)      39.7mm (7)      28.2mm (7)      17.9mm (7)      12.6mm (7)       5.7mm (7)
                    5.0%      39.7mm (7)      28.2mm (7)      20.0mm (7)      12.6mm (7)       8.9mm (7)       4.0mm (7)
                    2.5%      28.2mm (7)      20.0mm (7)      14.1mm (7)       8.9mm (7)       6.3mm (7)       2.8mm (7)
                    1.0%      17.9mm (7)      12.6mm (7)       8.9mm (7)       5.7mm (7)       4.0mm (7)       1.8mm (7)
                    0.5%      12.6mm (7)       8.9mm (7)       6.3mm (7)       4.0mm (7)       2.8mm (7)       1.3mm (7)

                                                 relative_contact_length
        penetration              100.0mm          50.0mm          25.0mm          10.0mm           5.0mm           1.0mm
                  100.0%      100.0% (7)      100.0% (7)      100.0% (7)      100.0% (7)      100.0% (7)      100.0% (7)
                   75.0%      100.0% (7)       88.6% (7)       87.5% (7)       87.0% (7)       86.8% (7)       86.6% (7)
                   50.0%       89.4% (7)       73.9% (7)       72.2% (7)       71.3% (7)       71.0% (7)       70.8% (7)
                   40.0%       81.4% (7)       66.7% (7)       64.8% (7)       63.9% (7)       63.5% (7)       63.3% (7)
                   30.0%       71.7% (7)       58.2% (7)       56.4% (7)       55.4% (7)       55.1% (7)       54.8% (7)
                   20.0%       59.6% (7)       47.9% (7)       46.2% (7)       45.3% (7)       45.0% (7)       44.8% (7)
                   10.0%       42.8% (7)       34.2% (7)       32.8% (7)       32.1% (7)       31.8% (7)       31.7% (7)
                    5.0%       30.5% (7)       24.2% (7)       23.2% (7)       22.7% (7)       22.5% (7)       22.4% (7)
                    2.5%       21.7% (7)       17.2% (7)       16.5% (7)       16.1% (7)       15.9% (7)       15.8% (7)
                    1.0%       13.7% (7)       10.9% (7)       10.4% (7)       10.2% (7)       10.1% (7)       10.0% (7)
                    0.5%        9.7% (7)        7.7% (7)        7.4% (7)        7.2% (7)        7.1% (7)        7.1% (7)
        """
        row, i = self.output, self.eo
        try:
            total_penetration = row.at[i, 'penetration']  # Total penetration = H1 - H0
            assert total_penetration >= 0.0, f"ValueError: 'penetration' should be positive or zero, but it is = {total_penetration}"
            assert 0.0 <= at_relative_penetration_percent <= 100.0, f"ValueError: 'one_side_relative_penetration' should be within 0.0 ... 1.0 range, but it is = {at_relative_penetration_percent}"

            if total_penetration == 0.0 or at_relative_penetration_percent == 0.0:
                return 0.0

            one_side_penetration = 0.5 * total_penetration * at_relative_penetration_percent / 100.0

            die_ids = row.loc[i, pd.Index(('top_die_id', 'bottom_die_id'))].to_list()

            radius_contact_length_list = []
            total_die_contact_length_list = []
            for _id in die_ids:

                # ================================== DIE PARAMETERS ==========================================

                die = config.lib['die']['dimensions'][_id]

                edge_radius = die['edge_radius']
                edge_angle = die['edge_angle']  # Degrees
                edge_angle_radians = math.radians(edge_angle)
                straight_length = die['straight_length']
                radius_height = die['radius_height']
                radius_length = die['radius_length']
                curved_height = die['curved_height']
                curved_length = die['curved_length']
                # is_have_slope = die['is_have_slope']

                assert edge_radius > 0.0, f"ValueError: 'edge_radius' should be positive, but it is = {edge_radius}"
                assert 0.0 <= edge_angle <= 90.0, f"ValueError: 'edge_angle' should be positive within 0 ... 90 degrees, but it is = {edge_angle}"

                theoretical_total_length = 2 * edge_radius + straight_length
                if theoretical_total_length == die['total_length']:
                    assert edge_angle == 90.0, f"ValueError: Impossible geometry of die where die has no slopes (slope angle == 90) and total die length ({die['total_length']}) is not equal to the sum of radii and straight length (2 * R{edge_radius} + {straight_length}) = {theoretical_total_length}"
                if theoretical_total_length < die['total_length']:
                    assert edge_angle < 90.0, f"ValueError: Impossible geometry of die where die has no slopes (slope angle >= 90), but total die length ({die['total_length']}) is bigger than the sum of radii and straight length (2 * R{edge_radius} + {straight_length}) = {theoretical_total_length}"

                # ============================= CONTACT PARAMETERS =======================================

                if one_side_penetration <= radius_height:  # Contact happens with radius only, but not with slope
                    contact_angle = math.acos(1 - one_side_penetration / edge_radius)  # radians
                    contact_length = edge_radius * math.sin(contact_angle)

                elif one_side_penetration < curved_height:  # Penetration does not exceed slope
                    contact_slope_length = (radius_height - one_side_penetration) / math.tan(edge_angle_radians)
                    contact_length = radius_length + contact_slope_length

                else:
                    contact_length = curved_length

                radius_contact_length_list.append(contact_length)

                # ============================ FULL CONTACT LENGTH =======================================

                total_die_contact_length = straight_length + 2 * contact_length
                total_die_contact_length_list.append(total_die_contact_length)

            # ============================================================================================
            # Deformation may be done by two dies with different lengths.
            # It is expected, that billet will bend to the side of shorter die,
            # so there will be no contact with radii of longer die.
            # Then we consider shorter die only.
            # We return Radius contact length of shorter die only.

            selected_die_index = 0
            for i in range(1, len(total_die_contact_length_list)):
                if total_die_contact_length_list[i] < total_die_contact_length_list[selected_die_index]:
                    selected_die_index = i

            return radius_contact_length_list[selected_die_index]
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise RuntimeError("Error calculating contact length along die radius")

    def _final_dimensions(self):
        row, i = self.output, self.eo
        try:
            keys = ['final_length', 'final_width', 'final_height']

            final_trimesh_obj = row.at[i, 'TEMPORARY.final_trimesh_obj_in_initial_basis']
            bounds = final_trimesh_obj.bounds
            row.loc[i, keys] = bounds[1, :] - bounds[0, :]

            negative_keys = [key for key in keys if row.at[i, key] <= 0.0 ]
            assert not negative_keys, f"ValueError: {', '.join(keys)} in self.output[...] are negative."

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _upsetting_final_dimensions(self):
        row, i = self.output, self.eo
        try:
            row.at[i, 'final_length'] = math.exp(row.at[i, 'strain_length']) * row.at[i, 'initial_length']
            row.at[i, 'final_width'] = math.exp(row.at[i, 'strain_width']) * row.at[i, 'initial_width']
            row.at[i, 'final_height'] = math.exp(row.at[i, 'strain_height']) * row.at[i, 'initial_height']

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def initial_cross_section_area(self):
        """Calculate initial and final surface area"""
        row, i = self.output, self.eo
        try:
            initial_cross_section_area = get_cross_section_area(row.at[i, 'TEMPORARY.initial_polygon'])
            assert initial_cross_section_area > 0.0, f"ValueError: 'initial_cross_section_area' should be above zero, but {initial_cross_section_area}."

            row.at[i, 'initial_cross_section_area'] = initial_cross_section_area
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def final_cross_section_area(self):
        """Calculate initial and final surface area"""
        row, i = self.output, self.eo
        try:
            row.at[i, 'final_cross_section_area'] = get_cross_section_area(row.at[i, 'TEMPORARY.final_polygon'])
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def equivalent_diameter(self):
        """Calculate equivalent diameter of the final cross-section"""
        row, i = self.output, self.eo
        try:
            row.at[i, 'equivalent_diameter'] = polygon_to_equivalent_diameter(row.at[i, 'TEMPORARY.final_polygon'])
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def initial_surface_area(self):
        """Calculate initial and final surface area"""
        row, i = self.output, self.eo
        try:
            row.at[i, 'initial_surface_area'] = get_surface_area(
                row.at[i, 'TEMPORARY.initial_polygon'], row.at[i, 'initial_length'])
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def final_surface_area(self):
        """Calculate initial and final surface area"""
        row, i = self.output, self.eo
        try:
            row.at[i, 'final_surface_area'] = get_surface_area(row.at[i, 'TEMPORARY.final_polygon'],
                                                                row.at[i, 'final_length'])
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def initial_volume(self):
        """Calculate initial surface area"""
        row, i = self.output, self.eo
        try:
            row.at[i, 'volume_initial'] = row.at[i - 1, 'volume_final']
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def final_volume(self):
        """Calculate final surface area"""
        row, i = self.output, self.eo
        try:
            # ======================= INITIAL VOLUME ================================
            volume_initial: np.float64 = row.at[i, 'volume_initial']

            # ======================= 3D TRIMESH OBJECT VOLUME ======================
            final_trimesh_obj: Trimesh = row.at[i, 'TEMPORARY.final_trimesh_obj']
            final_trimesh_volume: np.float64 = final_trimesh_obj.volume

            # ======================= ASSERT VOLUME DIFFERENCE ======================
            volume_error_tolerance_percent = 0.01
            volume_difference_percent = abs(1 - volume_initial / final_trimesh_volume) * 100
            assert volume_difference_percent < volume_error_tolerance_percent, f"Difference between Initial Volume and 3D Trimesh Final Volume ({volume_difference_percent:.3f}%) exceeds Volume Error Tolerance ({volume_error_tolerance_percent:.3f}%)."

            row.at[i, 'volume_final'] = volume_initial
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def initial_weight(self):
        """Calculate initial and final surface area"""
        row, i = self.output, self.eo
        try:
            row.at[i, 'initial_weight'] = row.at[i - 1, 'final_weight']
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def final_weight(self):
        """Calculate initial and final surface area"""
        row, i = self.output, self.eo
        try:
            _v = row.at[i, 'volume_final']
            material_id = int(row.at[i, 'material_id'])
            density = config.lib['materials']['density'][material_id]
            row.at[i, 'final_weight'] = density * _v / 1e9
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def elongation_channel(self):
        """Total deformation"""
        row, i = self.output, self.eo
        try:
            length_list = (row.at[i, 'final_length'], row.at[i, 'initial_length'])
            e_long_increment = max(length_list) / min(length_list)
            row.at[i, 'elongation_channel_a'] = row.at[i - 1, 'elongation_channel_a'] * e_long_increment
            row.at[i, 'elongation_channel_b'] = row.at[i - 1, 'elongation_channel_b'] * e_long_increment
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def strain_accumulated_channel(self):
        row, i = self.output, self.eo
        try:
            _ehl = (row.at[i, 'strain_height'] - row.at[i, 'strain_length']) ** 2
            _ewh = (row.at[i, 'strain_width'] - row.at[i, 'strain_height']) ** 2
            _elw = (row.at[i, 'strain_length'] - row.at[i, 'strain_width']) ** 2
            e_increment = math.sqrt(2.0) / 3.0 * math.sqrt(_elw + _ewh + _ehl)
            row.at[i, 'strain_accumulated_channel_a'] = row.at[i - 1, 'strain_accumulated_channel_a'] + e_increment
            row.at[i, 'strain_accumulated_channel_b'] = row.at[i - 1, 'strain_accumulated_channel_b'] + e_increment
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def initial_height_to_width_ratio(self):
        """Calculate initial and final height to width ratio"""
        row, i = self.output, self.eo
        try:
            row.at[i, 'initial_height_to_width_ratio'] = row.at[i, 'initial_height'] / row.at[i, 'initial_width']
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def final_height_to_width_ratio(self):
        """Calculate initial and final height to width ratio"""
        row, i = self.output, self.eo
        try:
            row.at[i, 'final_height_to_width_ratio'] = row.at[i, 'final_height'] / row.at[i, 'final_width']
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def time_before_pass(self):
        """Calculate time before operation"""
        row, i = self.output, self.eo
        try:
            time_before = self.get_time_between_operation()
            manipulator_movement_time = self.time_manipulator_movement()
            time_between_bites = row.at[i, 'time_between_bites']

            row.at[i, 'time_before_pass'] = time_before + manipulator_movement_time - time_between_bites

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def time_manipulator_movement(self):
        row, i = self.output, self.eo
        try:
            is_same_operation_type = row.at[i, 'operation_type'] == row.at[i - 1, 'operation_type']
            if is_same_operation_type:
                t2 = self._feed_direction_changing_time()
                t3 = self._billet_rotation_time()
                result = t2 + t3
            else:
                result = 0.0
            return result
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._set_is_ready_false()

    def get_time_between_operation(self):
        row, i = self.output, self.eo
        try:
            press_id = row.at[i, 'press_id']
            if pd.isna(press_id):
                press_id = 2
            return get_time_between_operations(config.lib, self.type_id, self.previous_type_id, press_id)
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._set_is_ready_false()

    def _feed_direction_changing_time(self):
        """Calculate time for changing direction"""
        row, i = self.output, self.eo
        try:
            is_same_feed_direction = row.at[i, 'feed_direction_id'] == row.at[i - 1, 'feed_direction_id']
            if is_same_feed_direction:
                result = 0.0
            else:
                manipulator_speed = 400.0  # [mm/seconds]
                manipulator_dwell = 2.0  # [seconds]
                travel_time = row.at[i, 'initial_length'] / manipulator_speed
                result = travel_time + manipulator_dwell
            return result
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._set_is_ready_false()

    def _billet_rotation_time(self):
        """Calculate time for billet rotation"""
        row, i = self.output, self.eo
        try:
            is_no_rotation = row.at[i, 'angle'] == 0.0
            if is_no_rotation:
                result = 0.0
            else:
                _id = row.at[i, 'type_id']
                match _id:
                    case 52:  # Full die simple
                        rotation_speed = 0.25  # [seconds/revolution]
                        rotation_dwell = 1.0  # [seconds]
                    case _:
                        rotation_speed = 1.5  # [seconds/revolution]
                        rotation_dwell = 1.0  # [seconds]
                angle = float(row.at[i, 'angle'])  # [degrees]
                rotation_time = angle / 360.0 * rotation_speed
                result = rotation_time + rotation_dwell
            return result
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._set_is_ready_false()

    def time_between_bites(self):
        """Calculate time between bites"""
        row, i = self.output, self.eo
        try:
            press = self.press_parameters()

            row.at[i, 'time_between_bites'] = row.at[i, 'idle_stroke'] / press['idle_speed'] + row.at[i, 'back_stroke'] / press['back_speed']

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def cycle_time(self):
        """Calculate cycle time"""
        row, i = self.output, self.eo
        try:
            row.at[i, 'cycle_time'] = row.at[i, 'time_bite_working'] + row.at[i, 'time_between_bites']

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def time_bite_working(self):
        """Working time of a bite."""
        row, i = self.output, self.eo
        try:
            row.at[i, 'time_bite_working'] = row.at[i, 'working_stroke'] / row.at[i, 'speed']

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def total_time(self):
        """Calculate total_time"""
        row, i = self.output, self.eo
        try:
            total_time_of_previous_pass = row.at[i - 1, 'total_time']
            work_time_bite = row.at[i, 'time_bite_working']
            time_between_bites = row.at[i, 'time_between_bites']
            num_of_bites = row.at[i, 'num_of_bites']
            time_before_pass = row.at[i, 'time_before_pass']
        except KeyError as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

        try:
            total_work_time = work_time_bite * num_of_bites
            total_time_between_bites = time_between_bites * (num_of_bites - 1)
            time_of_pass = total_work_time + total_time_between_bites

            total_time_of_new_pass = time_before_pass + time_of_pass

            row.at[i, 'total_time'] = total_time_of_previous_pass + total_time_of_new_pass

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def total_time_minutes(self):
        """Convert seconds to minutes"""
        row, i = self.output, self.eo
        try:
            row.at[i, 'total_time_minutes'] = row.at[i, 'total_time'] / 60

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def add_missed_keys_from_previous(self):
        """
        Adds missed keys to row from 'config.lib['output_columns']'
        """
        row, i = self.output, self.eo
        try:
            # TODO: There is 'FutureWarning' and not solved
            # row.astype(get_data.dtypes)
            _ffill = row.loc[[i - 1, i]].ffill()
            try:
                row.loc[[i - 1, i]] = _ffill
            except Exception:
                for _name in _ffill.columns:
                    row.loc[[i - 1, i], _name] = _ffill.loc[[i - 1, i], _name]
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self.output.loc[i, 'is_ready'] = False

    def _open_die_height_before_idle_stroke(self):
        row, i = self.output, self.eo
        try:
            row.at[i, 'open_die_height_before_idle_stroke'] = (row.at[i, 'open_die_height_max_before_working_stroke']
                                                               + row.at[i, 'working_approaching_stroke']
                                                               + row.at[i, 'idle_stroke'])
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _open_die_height_max_before_working_stroke(self):
        row, i = self.output, self.eo
        try:
            type_id = row.at[i, 'type_id']
            if type_id == 100:  # Tail chamfering
                op_param = row.at[i, 'operation_specific_parameters']['projections']
                height_start_1 = op_param['height_to_length_projection']['initial_billet_vertical_projection']
                height_start_2 = op_param['width_to_length_projection']['initial_billet_vertical_projection']
                height_start = max(height_start_1, height_start_2)

            elif self.parent_type_id == 37:  # All Upsetting except Operation 100 - Tail chamfering
                height_start = row.at[i, 'initial_length']

            elif type_id in (46, 83, 90, 52, 57, 64, 80, 82, 95, 96):
                """
                46: Axial prolongation, 
                83: Axial prolongation Num of Bites
                90: Axial prolongation Num of Bites, Skip bites
                52:  # Full die simple
                57:  # Cut on {} pieces, keep piece #{} with length ratio {}%
                64:  # Radial forging (GFM)
                80:  (Obsolete)  Radial Prolongation Feed
                82:  (Obsolete)  Radial Prolongation Num of Bites
                95:  # Radial Prolongation Feed
                96:  # Radial Prolongation Num of Bites
                """
                height_start = row.at[i, 'initial_height']

            elif type_id in (50, 51):  # Spiral prolongation<
                height_start = row.at[i, 'operation_specific_parameters']['initial_dies_gap']

            else:
                raise KeyError(
                    f"Function '_open_die_height_max_before_working_stroke' does not have a method "
                    f"for an operations with 'type_id' = {type_id}.")

            row.at[i, 'open_die_height_max_before_working_stroke'] = height_start
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _open_die_height_min_after_working_stroke(self):
        row, i = self.output, self.eo
        try:
            type_id = row.at[i, 'type_id']
            if type_id == 100:  # Tail chamfering
                op_param = row.at[i, 'operation_specific_parameters']['projections']
                height_start_1 = op_param['height_to_length_projection']['final_billet_vertical_projection']
                height_start_2 = op_param['width_to_length_projection']['final_billet_vertical_projection']
                height_finish = min(height_start_1, height_start_2)

            elif self.parent_type_id == 37:  # All Upsetting except Operation 100 = Tail Chamfering
                height_finish = row.at[i, 'final_length']

            elif type_id in (46, 83, 90, 80, 82, 95, 96, 52, 57, 64):
                """
                46: Axial prolongation
                83: Axial prolongation Num of Bites
                90: Axial prolongation Num of Bites, Skip bites 
                80: (Obsolete) Radial Prolongation Feed, 
                82:  (Obsolete) Radial Prolongation Num of Bites
                95: Radial Prolongation Feed, 
                96:  # Radial Prolongation Num of Bites
                52:  # Full die simple
                57:  # Cut on {} pieces, keep piece #{} with length ratio {}%
                64:  # Radial forging (GFM)
                """
                height_finish = row.at[i, 'final_height']

            elif type_id in (50, 51):  # Spiral prolongation
                height_finish = row.at[i, 'operation_specific_parameters']['final_dies_gap']

            else:
                raise KeyError(
                    f"Function '_open_die_height_min_after_working_stroke' does not have a method "
                    f"for an operations with 'type_id' = {type_id}.")

            row.at[i, 'open_die_height_min_after_working_stroke'] = height_finish
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _working_stroke(self):
        row, i = self.output, self.eo
        try:
            type_id = row.at[i, 'type_id']
            if type_id == 100:  # Tail chamfering with rotation
                op_param = row.at[i, 'operation_specific_parameters']['projections']
                penetration_1 = 2 * op_param['height_to_length_projection']['chamfer_vertical_projection']
                penetration_2 = 2 * op_param['width_to_length_projection']['chamfer_vertical_projection']
                stroke = (penetration_1 + penetration_2) / 2
            elif self.parent_type_id == 37 or type_id in (46, 83, 90, 50, 51, 80, 82, 95, 96, 52, 57, 64):  # Upsetting or ...
                """
                91: Single or Triple bites upsetting
                93: Single bite upsetting
                94: Triple bites upsetting
                92: Tail flattening with rotation
                46: Axial prolongation
                83: Axial prolongation Num of Bites
                90: Axial prolongation Num of Bites, Skip bites
                50: Spiral prolongation
                51: Spiral prolongation
                80: (Obsolete) Radial Prolongation Feed
                82: (Obsolete) Radial Prolongation Num of Bites
                95: Radial Prolongation Feed
                96: Radial Prolongation Num of Bites
                52: Full die simple
                57: Cut on {} pieces, keep piece #{} with length ratio {}%
                64: Radial forging GFM
                """
                stroke = row.at[i, 'penetration']
            else:
                raise KeyError(
                    f"Function '_working_stroke' does not have a method for an operations with 'type_id' = {type_id}.")

            row.at[i, 'working_stroke'] = stroke
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _working_approaching_stroke(self):
        row, i = self.output, self.eo
        try:
            press = self.press_parameters()
            row.at[i, 'working_approaching_stroke'] = press['approaching_distance']
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _idle_stroke(self):
        """Back stroke"""
        row, i = self.output, self.eo
        try:
            press = self.press_parameters()
            min_idle_stroke = press['min_idle_stroke']
            max_idle_stroke = press['max_idle_stroke']
            press_open_height = press['open_height_without_dies']
            # press_id = row.at[i, 'press_id']
            # gap = press_open_height - total_die_height - row.at[i, 'initial_height']

            top_die = self.die_parameters_for_top()
            bottom_die = self.die_parameters_for_bottom()
            total_die_height = top_die['height'] + bottom_die['height']

            billet_height_start = row.at[i, 'open_die_height_max_before_working_stroke']
            working_approaching_stroke = row.at[i, 'working_approaching_stroke']

            max_open_height = press_open_height - total_die_height
            relative_required_open_die_height = billet_height_start / max_open_height
            target_idle_stroke = \
                min_idle_stroke + (max_idle_stroke - min_idle_stroke) * relative_required_open_die_height

            available_idle_stroke = max_open_height - billet_height_start - working_approaching_stroke

            row.at[i, 'idle_stroke'] = min(target_idle_stroke, available_idle_stroke)
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _back_stroke(self):
        """Calculate time between bites"""
        row, i = self.output, self.eo
        try:
            row.at[i, 'back_stroke'] = (row.at[i, 'working_stroke']
                                        + row.at[i, 'working_approaching_stroke']
                                        + row.at[i, 'idle_stroke'])
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def limit_speed_by_press_working_speed(self):
        """Calculate actual working speed, accounting set working target_speed and parameters of the press."""
        row, i = self.output, self.eo
        try:
            row.at[i, 'speed'] = min(row.at[i, 'speed'], self.press_parameters()['working_speed'])
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def press_parameters(self) -> dict:
        """Dictionary of press parameters from the Library."""
        row, i = self.output, self.eo
        try:
            press_mode_id = row.at[i, 'press_mode_id']
            return config.lib['press_mode'].loc[press_mode_id]
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._set_is_ready_false()

    def die_parameters_for_top(self) -> dict:
        """Dictionary of die parameters from the Library."""
        row, i = self.output, self.eo
        try:
            _id: int = row.at[i, 'top_die_id']
            return config.lib['die']['dimensions'][_id]
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._set_is_ready_false()

    def die_parameters_for_bottom(self) -> dict:
        """Dictionary of die parameters from the Library."""
        row, i = self.output, self.eo
        try:
            _id: int = row.at[i, 'bottom_die_id']
            return config.lib['die']['dimensions'][_id]
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._set_is_ready_false()

    def press_mode_id(self):
        """Returns 'press_mode_id'."""
        row, i = self.output, self.eo
        try:
            pm = config.lib['press_mode']
            press_id = row.at[i, 'press_id']

            mask = (pm['press_id'] == press_id) & pm['is_default_press_mode']

            assert mask.sum() != 0, (f"Error in 'press_mode' table. There is no default "
                                     f"'press_mode' for 'press_id' = {press_id}.")
            assert mask.sum() == 1, (f"Error in 'press_mode' table. There is more than one "
                                     f"default 'press_mode' for 'press_id' = {press_id}.")

            return pm.loc[mask].index.to_numpy()
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._set_is_ready_false()

    def max_temperature(self):
        """Returns 'max_temperature'."""
        row, i = self.output, self.eo
        try:
            if i == 0:
                return 20.0
            elif self.type_id == 23:
                return self.accumulated.loc[self.input_index, 'temperature']
            else:
                return row.at[i - 1, 'max_temperature']
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._set_is_ready_false()

    def simulation_expected_duration_days_for_operation_23_heat(self):
        """
        Returns expected computer time run time in days.

        return: float - expected computer time run time in days
        """
        row, i = self.output, self.eo
        try:
            total_elem_number = self.mesh_element_number()
            duration_sec = row.at[i, 'control_duration']
            heat_run_time = self.heating_run_time_days(duration_sec, total_elem_number)
            row.at[i, 'simulation_expected_duration_days'] = heat_run_time
        except Exception as _err:
            LOGGER.error(f"Some error: {_err}")
            self._set_is_ready_false()

    def simulation_expected_duration_days_for_prolongation(self):
        """
        Returns expected computer time run time in days.

        return: float - expected computer time run time in days
        """
        row, i = self.output, self.eo
        try:
            total_elem_number = self.mesh_element_number()

            penetration = row.at[i, 'penetration']
            num_of_bites = row.at[i, 'num_of_bites']
            time_before_pass = row.at[i, 'time_before_pass']
            time_between_bites = row.at[i, 'time_between_bites']

            heat_intervals_sec = [time_before_pass] + [time_between_bites] * (num_of_bites - 1)
            heat_run_time = sum(
                [self.heating_run_time_days(_t, total_elem_number) for _t in heat_intervals_sec])

            penetration_intervals = [penetration] * num_of_bites
            deformation_run_time = sum([self.deformation_run_time_days(_p) for _p in penetration_intervals])

            total_run_time_days = heat_run_time + deformation_run_time

            row.at[i, 'simulation_expected_duration_days'] = total_run_time_days

        except Exception as _err:
            LOGGER.error(f"Some error: {_err}")
            raise

    def heating_run_time_days(self, duration_sec: float, total_elem_number: int) -> float:
        try:
            seconds_per_day = 86400
            if duration_sec <= 1.0:
                step_count = 1
            elif duration_sec <= 1000.0:
                step_count = int(duration_sec / 10.0)
            else:
                step_count = int(duration_sec / 50.0)
            run_time_duration_per_step = 4.0E-6 * total_elem_number + 0.1394
            return step_count * run_time_duration_per_step / seconds_per_day

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._set_is_ready_false()
            return 0.0

    def deformation_run_time_days(self, penetration: float) -> float:

        row, i = self.output, self.eo
        try:
            pm = config.lib['press_mode']
            seconds_per_day = 86400

            mesh_elements = row.at[i, 'mesh_elements']
            max_billet_temperature = row.at[i, 'max_temperature']
            average_billet_strain = 0.0

            speed = row.at[i, 'speed']
            material_id = row.at[i, 'material_id']
            press_mode_id = row.at[i, 'press_mode_id']

            press_max_speed = pm.loc[press_mode_id]['working_speed']
            max_press_force = pm.loc[press_mode_id]['max_force']

            average_billet_strain_rate = min(speed, press_max_speed) / row.at[i, 'initial_height']
            contact_area = row.at[i, 'final_length_of_contact'] * row.at[i, 'final_width_of_contact']
            flow_stress = config.lib['material_classes'][material_id].flow_stress(
                average_billet_strain,
                average_billet_strain_rate,
                max_billet_temperature)
            actual_press_force = contact_area * flow_stress
            if actual_press_force >= max_press_force:
                force_coefficient = 0.1
            elif actual_press_force <= 0.0:
                force_coefficient = 1.0
            else:
                force_coefficient = 1.0 - 0.9 * actual_press_force / max_press_force
            size_coefficient = 0.05
            min_element_size_function = self.billet_thickness() / mesh_elements
            step_size = size_coefficient * force_coefficient * min_element_size_function
            step_count = penetration / step_size
            run_time_duration_per_step = 2.5
            return step_count * run_time_duration_per_step / seconds_per_day
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._set_is_ready_false()
            return 0.0

    def mesh_element_number(self) -> int:
        """
        Returns total number of mesh elements.

        return: int - total number of mesh elements
        """
        row, i = self.output, self.eo
        try:
            mesh_elements = row.at[i, 'mesh_elements']
            initial_surface_area = row.at[i, 'initial_surface_area']
            _size_correction_coef = 0.84
            _element_size_ratio = 1.1

            _min_element_size = _size_correction_coef * self.billet_thickness() / mesh_elements
            _length_of_average_element = 0.5 * (1 + _element_size_ratio) * _min_element_size
            _face_area_of_average_element = 0.433 * _length_of_average_element ** 2
            _number_of_surface_elements = int(initial_surface_area / _face_area_of_average_element)
            # _inverse_max_element_size = 1 / (_min_element_size * _element_size_ratio)
            return 4 * _number_of_surface_elements
        except Exception as _err:
            LOGGER.error(f"Some error: {_err}")
            self._set_is_ready_false()
            return 1

    def billet_thickness(self):
        row, i = self.output, self.eo
        try:
            min_thickness = row.loc[i, pd.Index(('initial_height', 'initial_width', 'initial_length', 'final_height', 'final_width', 'final_length'))].min()
            return min_thickness
        except Exception as _err:
            LOGGER.error(f"Some error: {_err}")
            self._set_is_ready_false()
            return 1.0

    def _tail_chamfering_parameters(self,
                                    billet_length_along_axis: float,
                                    billet_width_orthogonal_to_axis: float,
                                    relative_chamfer_leg_orthogonal_to_billet_axis: float) -> dict:
        try:
            _L = billet_length_along_axis
            _H = billet_width_orthogonal_to_axis
            _k = relative_chamfer_leg_orthogonal_to_billet_axis
            chamfer_leg_orthogonal_to_billet_axis = _k * _H
            chamfer_leg_along_billet_axis = 0.5 * (_L - math.sqrt(_L**2 - 4 * _k * _H**2 + 4 * (_k * _H)**2))
            axis_inclination_angle_rad = math.atan(chamfer_leg_along_billet_axis / _k / _H)
            initial_billet_vertical_projection = \
                math.cos(axis_inclination_angle_rad) * _L + math.sin(axis_inclination_angle_rad) * _H
            chamfer_hypotenuse = chamfer_leg_along_billet_axis / math.sin(axis_inclination_angle_rad)
            chamfer_vertical_projection = \
                chamfer_leg_along_billet_axis * chamfer_leg_orthogonal_to_billet_axis / chamfer_hypotenuse
            final_billet_vertical_projection = initial_billet_vertical_projection - 2 * chamfer_vertical_projection
            initial_billet_horizontal_projection = \
                math.sin(axis_inclination_angle_rad) * _L + math.cos(axis_inclination_angle_rad) * _H

            # The following formula is derived from the equation for the relative penetration of the chamfer.
            _p = (4 * _k ** 3 - 6 * _k ** 2 + 3 * _k - 1)
            axial_relative_one_side_penetration = 1 - (math.cbrt(_p) + 1) / (2 * _k)
            axial_virtual_penetration = 2 * chamfer_leg_along_billet_axis * axial_relative_one_side_penetration
            return {
                'axis_inclination_angle': axis_inclination_angle_rad,
                'chamfer_leg_along_billet_axis': chamfer_leg_along_billet_axis,
                'chamfer_leg_orthogonal_to_billet_axis': chamfer_leg_orthogonal_to_billet_axis,
                'chamfer_hypotenuse': chamfer_hypotenuse,
                'chamfer_vertical_projection': chamfer_vertical_projection,
                'initial_billet_vertical_projection': initial_billet_vertical_projection,
                'initial_billet_horizontal_projection': initial_billet_horizontal_projection,
                'final_billet_vertical_projection': final_billet_vertical_projection,
                'axial_virtual_penetration': axial_virtual_penetration
            }
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._set_is_ready_false()

    @property
    def type_id(self) -> int:
        try:
            return self.output.loc[self.eo, 'type_id']
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._set_is_ready_false()

    @property
    def previous_type_id(self) -> int:
        try:
            return self.output.loc[self.eo - 1, 'type_id']
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._set_is_ready_false()

    @property
    def parent_type_id(self) -> int:
        try:
            return config.lib['operations_library'].loc[self.type_id, 'parent_type_id'].item()
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()

    @property
    def previous_parent_type_id(self) -> int:
        try:
            assert self.eo > 0
            return config.lib['operations_library'].loc[self.previous_type_id, 'parent_type_id'].item()
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()

    @property
    def previous_accumulated_type_id(self):
        try:
            return self.accumulated.loc[self.input_index - 1, 'type_id'].item()
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()

    def get_acc(self, variable_name):
        """
        Getter method to retrieve the value of a variable from the accumulated DataFrame.

        Parameters:
        variable_name (str): The name of the column in 'self.accumulated' DataFrame.

        Returns:
        The value at row number 'self.input_index' and column 'variable_name', converted to a built-in Python type.
        """
        try:
            value = self.accumulated.loc[self.input_index, variable_name]
            if pd.isnull(value):
                return None
            elif isinstance(value, np.generic):
                return value.item()
            else:
                return value
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()

    def set_acc(self, variable_name, value):
        """
        Setter method to set the value of a variable in the accumulated DataFrame.

        Parameters:
        variable_name (str): The name of the column in 'self.accumulated' DataFrame.
        value: The value to set at row number 'self.input_index' and column 'variable_name'.
        """
        try:
            self.accumulated.at[self.input_index, variable_name] = value
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()

    def __get_single_previous_out(self, _variable_name):
        try:
            index = self.eo - 1
            assert index >= 0, f"It is requested to reach a row of 'self.output.loc[{index}, '{_variable_name}']' dataframe with negative index {index}."
            value = self.output.loc[index, _variable_name]
            if isinstance(value, np.generic):
                return value.item()
            elif isinstance(value, (list, tuple, set, dict)):
                return value
            elif pd.isna(value):
                return None
            else:
                return value
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()

    def __get_single_out(self, _variable_name):
        try:
            value = self.output.loc[self.eo, _variable_name]
            if isinstance(value, np.generic):
                return value.item()
            elif isinstance(value, (list, tuple, set, dict)):
                return value
            elif pd.isna(value):
                return None
            else:
                return value
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()

    def get_previous_out(self, input_variable):
        """
        Getter method to retrieve the value of a variable from the 'self.output' DataFrame
        for previous row (row with index 'self.eo' - 1).

        Parameters:
        variable_name (str): The name of the column in 'self.output' DataFrame.

        Returns:
        The value at row number ('self.eo' - 1) and column 'variable_name', converted to a built-in Python type.
        """
        try:
            if isinstance(input_variable, (list, tuple)):
                return [self.__get_single_previous_out(var) for var in input_variable]
            else:
                return self.__get_single_previous_out(input_variable)
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()

    def get_out(self, input_variable):
        """
        Getter method to retrieve the value of a variable from the 'self.output' DataFrame.

        Parameters:
        variable_name (str): The name of the column in 'self.output' DataFrame.

        Returns:
        The value at row number 'self.eo' and column 'variable_name', converted to a built-in Python type.
        """
        try:
            if isinstance(input_variable, (list, tuple)):
                return [self.__get_single_out(var) for var in input_variable]
            else:
                return self.__get_single_out(input_variable)
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()

    def set_out(self, variable_name, value):
        """
        Setter method to set the value of a variable in the 'self.output' DataFrame.

        Parameters:
        variable_name (str): The name of the column in 'self.output' DataFrame.
        value: The value to set at row number 'self.eo' and column 'variable_name'.
        """
        try:
            self.output.at[self.eo, variable_name] = value
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            self._stop_calculations()

    def sim_unit_append(self, category: str, type: str, options: dict):
        """Add one simulation unit to the table of sim_units.

        Args:
            category (str): Category of simulation unit. Allowed values are: 'pre', 'sim' and 'post'.
            type (str): Type of simulation unit.
                Allowed types depends on the category:
                Category        Allowed types
                'pre'               -
                'sim'           'heat_transfer', 'bite'
                'post'          'measure_billet'
            options (dict): A dictionary of 'operation' parameters, as defined in SimulationWorker under self.param['operation']

        Raises:
            RuntimeError: If any error occurs under try - exception block.
        """

        try:
            allowed_units = {
                "pre": [],
                "sim": ["heat_transfer", "bite"],
                "post": ["measure_billet"]
            }
            assert isinstance(category, str), f"Unit category shall be type of 'str', but has type '{type(category)}'"

            allowed_categories = list(allowed_units.keys())
            assert category in allowed_categories, f"Wrong unit category ('{category}'). Allowed values are {', '.join(allowed_categories)}."

            allowed_types = allowed_units[category]
            assert type in allowed_types, f"Wrong unit type ('{type}'). Allowed values are {', '.join(allowed_types)}."

            assert isinstance(options, dict), f"Unit options shall be type of 'dict', but have type '{type(options)}'"

            self.sim_units.append(
                {
                    "pvid": self.pvid,
                    "eo": self.eo,
                    "category": category,
                    "type": type,
                    "options": options
                }
            )
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    @property
    def log_id(self):
        duration = str(round(time.monotonic() - self.time_start, 2))
        return f"{self.task_id_name} Duration {duration}s"

    @property
    def task_id_name(self) -> str:
        return f"[{self.pvid}][{self.eo}/{self.eo_last}] Pre #{self.worker_id}"
