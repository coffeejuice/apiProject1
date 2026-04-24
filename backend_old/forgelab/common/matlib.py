import logging
import math
import os
from functools import reduce
from sys import platform

from numpy import array, log
from numpy import delete as np_delete
from scipy.interpolate import RegularGridInterpolator
from scipy.interpolate import interp1d


LOGGER = logging.getLogger(__name__)


class Material:
    """Import and Calculate material properties."""
    units = dict(
        International=False,
        British=False
    )
    name = ""
    name_decoded_from_file_name = ""
    path_to_source_file = ""
    source_file_name = ""
    standard_name_data = dict(
        USA="",
        Japan="",
        German="",
        International="",
        European="",
        Russian="",
        British="",
        Korean="",
        China=""
    )
    mech_to_heat = dict(
        style="",
        deform_key="",
        material_num=int(),
        data_txt=[],
        value=[]
    )
    body_force_data = dict(
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        time=[],
        body_force=[],
        centrifugal_force=[]
    )
    damage_data = dict(
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[]
    )
    flow_stress_data = dict(
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        coef={},
        strain=[],
        srate=[],
        temperature=[],
        stress=[],
        process_flags=dict(
            cold_forging=None,
            hot_forging=None,
            ht=None,
            machining=None
        )
    )
    young_data = dict(
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        coef={},
        temperature=[],
        density=[],
        atom=[],
        young=[]
    )
    poison_data = dict(
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        coef={},
        temperature=[],
        density=[],
        atom=[],
        poison=[]
    )
    thermal_expansion_data = dict(
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        coef={},
        temperature=[],
        density=[],
        atom=[],
        thermal_expansion=[]
    )
    conductivity_data = dict(
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        coef={},
        temperature=[],
        density=[],
        atom=[],
        conductivity=[]
    )
    heat_capacity_data = dict(
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        coef={},
        temperature=[],
        density=[],
        atom=[],
        heat_capacity=[]
    )
    mass_density_data = dict(
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        coef={},
        temperature=[],
        density=[],
        atom=[],
        mass_density=[]
    )
    alpha_coarsening_data = dict(
        style="",
        deform_key="",
        material_num=int(),
        coarsening_type=int(),
        ftype=int(),
        ftype_txt="Not defined",
        data_txt=[],
        coef={},
        temperature=[],
        srate=[],
        alpha_coarsening=[]
    )
    diffusion_bonding_data = dict(
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        coef={},
        temperature=[],
        pressure=[],
        time=[]
    )
    emissivity_data = dict(
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        coef={},
        temperature=[],
        emissivity=[]
    )
    hardness_data = dict(
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        coef={},
        temperature=[],
        density=[],
        atom=[],
        hardness=[]
    )
    mixture_material_data = dict(
        style="",
        deform_key="",
        material_num=int(),
        is_mixture=bool(),
        data_txt=[],
        dependent_phases=[]
    )
    creep_data = dict(
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        coef={},
        temperature=[],
        strain=[],
        stress=[],
        time=[],
        srate=[],
        grain_size=[],
        precipitate_size=[],
        precipitate_shape=[],
        precipitate_volume_fraction=[],
        creep=[]
    )
    carburization_data = dict(
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        coef={},
        temperature=[],
        atom=[],
        carburization=[]
    )
    resistivity_data = dict(
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        coef={},
        temperature=[],
        density=[],
        resistivity=[]
    )
    ultimate_strength_data = dict(
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        coef={},
        temperature=[],
        density=[],
        ultimate_strength=[]
    )
    hardening_rule_data = dict(
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[]
    )
    magnetic_permeability_data = dict(
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        coef={},
        temperature=[],
        density=[],
        magnetic_intensity=[],
        magnetic_permeability=[]
    )
    magnetic_permitivity_data = dict(
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        coef={},
        temperature=[],
        density=[],
        magnetic_intensity=[],
        magnetic_permitivity=[]
    )
    burgers_data = dict(
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        coef={},
        temperature=[],
        stress=[],
        concentration=[],
        burgers=[]
    )
    dislocation_alpha_data = dict(
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        coef={},
        temperature=[],
        srate=[],
        dislocation_alpha=[]
    )
    dislocations_number_data = dict(
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        coef={},
        temperature=[],
        srate=[],
        dislocations_number=[]
    )
    recovery_data = dict(
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        coef={},
        temperature=[],
        srate=[],
        recovery=[]
    )
    particle_mode_data = dict(
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[]
    )
    texture_data = dict(
        style="",
        deform_key="",
        material_num=int(),
        crystal_type=int(),
        crystal_type_txt="",
        texture_type=int(),
        texture_mesh_type=int(),
        data_txt=[]
    )
    grain_boundary_energy_data = dict(
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        temperature=[],
        grain_boundary_energy=[]
    )
    grain_boundary_mobility_data = dict(
        style="",
        deform_key="",
        material_num=int(),
        data_txt=[],
        coef={}
    )
    nuclei_size_data = dict(
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        temperature=[],
        nuclei_size=[]
    )

    def __init__(self, file):
        """Constructor"""
        super().__init__()
        self._lines = []
        self.deform_import_key_file(file)

    @staticmethod
    def deform_get_installation_path():
        """
        Return installation path of DEFORM. Normally it returns 'C:\\Program files\\SFTC\\DEFORM'
        :return: string: Full path of DEFORM installation directory
        """
        path: str = ""
        if platform == 'win32':
            program_dir = os.environ['PROGRAMFILES']
            path = os.path.join(program_dir, "SFTC", "DEFORM")
        return path if os.path.exists(path) else ""

    @staticmethod
    def deform_find_key_files(deform_library_path=""):
        """
        Search for KEY-files in Root folder and subfolders
        :param deform_library_path: Root folder name
        :return: list: list of tuples (str: full path to directory to file storage, str: KEY-file name)
        """
        files: list = []
        if os.path.exists(deform_library_path):
            root: str
            for root, dirs, files in os.walk(deform_library_path, topdown=True, onerror=None, followlinks=False):
                if files:
                    filename: str
                    for filename in files:
                        if filename.endswith('.key'):
                            files.append([root, filename])
        return files

    def deform_import_key_file(self, file, target_material_number=1):
        """
        Load DEFORM KEY-file and fill properties of self.flow_stress_data, self.heat_transfer_data, etc.
        :param target_material_number:
        :param file:
        :return:
        """
        file: str
        target_material_number: int
        with open(file, 'r') as data:
            self._lines = data.readlines()
        if not self._lines:
            return
        self._deform_decode_filename(file)
        self._deform_load_decode_std_file()
        while self._lines:
            line = self._lines.pop(0).strip().split()
            if isinstance(line, list) and len(line) >= 2 and line[1].isdigit():
                # Looks like this line contains KEY-word
                key = line[0]
                first_parameter = int(line[1])
                if first_parameter == target_material_number and key != "UNIT":
                    if key == "MTNAME":
                        second_line = self._lines.pop(0).strip()
                        self.name = second_line
                    elif key == "FRAE2H":
                        self._deform_decode_mech_to_heat(line)
                    # elif key == "FPERV":
                    # TODO: Mistake in self._deform_decode_body_force(line). Temporary turned off. Fix it.
                    #     self._deform_decode_body_force(line)
                    elif key == "FRCMOD":
                        self._deform_decode_damage(line)
                    elif key == "FSTRES":
                        self._deform_decode_flow_stress(line)
                    elif key == "YOUNG":
                        self._deform_decode_young(line)
                    elif key == "POISON":
                        self._deform_decode_poison(line)
                    elif key == "EXPAND":
                        self._deform_decode_thermal_expansion(line)
                    elif key == "THRCND":
                        self._deform_decode_conductivity(line)
                    elif key == "HEATCP":
                        self._deform_decode_heat_capacity(line)
                    elif key == "MASDEN":
                        self._deform_decode_mass_density(line)
                    elif key == "COARSE":
                        self._deform_decode_alpha_coarsening(line)
                    elif key == "DIFBND":
                        self._deform_decode_diffusion_bonding(line)
                    elif key == "EMSVTY":
                        self._deform_decode_emissivity(line)
                    elif key == "HDNPHA":
                        self._deform_decode_hardness(line)
                    elif key == "MSTMTR":
                        self._deform_decode_mixture_material(line)
                    elif key == "CREEP":
                        self._deform_decode_creep(line)
                    elif key == "DIFCOE":
                        self._deform_decode_carburization(line)
                    elif key == "ELRST":
                        self._deform_decode_resistivity(line)
                    elif key == "UTSDAT":
                        self._deform_decode_ultimate_strength(line)
                    elif key == "HDNRUL":
                        self._deform_decode_hardening_rule(line)
                    elif key == "PMEAB":
                        self._deform_decode_magnetic_permeability(line)
                    elif key == "PMITT":
                        self._deform_decode_magnetic_permitivity(line)
                    elif key == "BURGRS":
                        self._deform_decode_burgers(line)
                    elif key == "ALPHA":
                        self._deform_decode_dislocation_alpha(line)
                    elif key == "NDISFM":
                        self._deform_decode_dislocations_number(line)
                    elif key == "RECVRY":
                        self._deform_decode_recovery(line)
                    elif key == "SIZEMD":
                        self._deform_decode_particle_mode(line)
                    elif key == "TXTURE":
                        self._deform_decode_texture(line)
                    elif key == "GBENGY":
                        self._deform_decode_grain_boundary_energy(line)
                    elif key == "GBMOBI":
                        self._deform_decode_grain_boundary_mobility(line)
                    elif key == "NUCSIZ":
                        self._deform_decode_nuclei_size(line)
                elif key == "UNIT":
                    unit_system = int(line[1])
                    if unit_system == 1:
                        self.units['International'] = True
                        self.units['British'] = False
                    elif unit_system == 2:
                        self.units['International'] = False
                        self.units['British'] = True

    def _deform_decode_filename(self, file):
        filename = os.path.basename(file)
        self.source_file_name = filename
        self.path_to_source_file = os.path.dirname(file)
        if len(filename) > 12:
            separator = filename[-12:-10:]
            if separator == "_s":
                proc_type = filename[-10:-4:]
                if proc_type.isdigit() and int(proc_type, 16) < 16:
                    self.flow_stress_data['process_flags']['machining'], residual = divmod(int(proc_type, 16), 8)
                    self.flow_stress_data['process_flags']['ht'], residual = divmod(residual, 4)
                    self.flow_stress_data['process_flags']['hot_forging'], residual = divmod(residual, 2)
                    self.flow_stress_data['process_flags']['cold_forging'], residual = divmod(residual, 1)
                    self.name_decoded_from_file_name = filename[:-12:]

    def _deform_load_decode_std_file(self):
        """
        USA std. (AISI, ASM, ASTM) (line 1)
        Japan std.(JIS) (line 2)
        German std.(DIN) (line 3)
        International std. (ISO) (line 4)
        European std.(EN) (line 5)
        Russian std. (GOST) (line 6)
        British std. (BS) (line 7)
        Korean std. (KS) (line 8)
        :param
        :return:
        """
        filename = os.path.join(self.path_to_source_file, self.name_decoded_from_file_name + ".std")
        if os.path.exists(filename):
            with open(filename, 'r') as data:
                strings_list = data.readlines()
            if strings_list:
                # 1st line is name of alloy according to "USA" standard
                self.standard_name_data['USA'] = strings_list.pop(0).strip()
            if strings_list:
                # 2nd line is name of alloy according to "Japan" standard
                self.standard_name_data['Japan'] = strings_list.pop(0).strip()
            if strings_list:
                # 3rd line is name of alloy according to "German" standard
                self.standard_name_data['German'] = strings_list.pop(0).strip()
            if strings_list:
                # 4th line is name of alloy according to "International" standard
                self.standard_name_data['International'] = strings_list.pop(0).strip()
            if strings_list:
                # 5th line is name of alloy according to "European" standard
                self.standard_name_data['European'] = strings_list.pop(0).strip()
            if strings_list:
                # 6th line is name of alloy according to "Russian" standard
                self.standard_name_data['Russian'] = strings_list.pop(0).strip()
            if strings_list:
                # 7th line is name of alloy according to "British" standard
                self.standard_name_data['British'] = strings_list.pop(0).strip()
            if strings_list:
                # 8th line is name of alloy according to "Korean" standard
                self.standard_name_data['Korean'] = strings_list.pop(0).strip()

    def _deform_decode_mech_to_heat(self, line):
        """
        style="",
        deform_key="",
        material_num=int(),
        data_txt=[],
        value=[]
        :param line:
        :return:
        """
        self.mech_to_heat['style'] = "deform"
        self.mech_to_heat['deform_key'] = line[0]
        self.mech_to_heat['material_num'] = int(line[1])
        self.mech_to_heat['data_txt'] = [line]
        self.mech_to_heat['value'] = [float(line[2])]

    def _deform_decode_body_force(self, line):  # sourcery skip: extract-method
        """
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        time=[],
        body_force=[],
        centrifugal_force=[]
        :param line:
        :return:
        """
        ftype_body_force = int(line[3])
        ftype_centrifugal_force = int(line[5])
        self.body_force_data['style'] = "deform"
        self.body_force_data['deform_key'] = line[0]
        self.body_force_data['material_num'] = int(line[1])
        self.body_force_data['data_txt'] = [line]
        self.body_force_data['ftype_body_force'] = ftype_body_force
        self.body_force_data['ftype_centrifugal_force'] = ftype_centrifugal_force
        self.body_force_data['time'] = []
        self.body_force_data['body_force'] = []
        self.body_force_data['centrifugal_force'] = []
        if ftype_body_force == 0 and ftype_centrifugal_force == 0:
            self.body_force_data['body_force'] = [float(line[2])]
            self.body_force_data['centrifugal_force'] = [float(line[4])]
        elif ftype_body_force == 0 and ftype_centrifugal_force == 1:
            self.body_force_data['body_force'] = [float(line[2])]
            n_data_cf = int(line[4])
            self.young_data['time'], self.young_data['centrifugal_force'], lines = \
                self._deform_decode_1d_table(n_data_cf)
            self.mech_to_heat['data_txt'].append(lines)
        elif ftype_body_force == 1 and ftype_centrifugal_force == 0:
            self.body_force_data['centrifugal_force'] = [float(line[4])]
            n_data_bf = int(line[2])
            self.body_force_data['time'], self.body_force_data['body_force'], lines = \
                self._deform_decode_1d_table(n_data_bf)
            self.mech_to_heat['data_txt'].append(lines)
        elif ftype_body_force == 1 and ftype_centrifugal_force == 1:
            n_data_bf = int(line[2])
            n_data_cf = int(line[4])
            self.body_force_data['time'], self.body_force_data['body_force'], lines = \
                self._deform_decode_1d_table(n_data_bf)
            self.mech_to_heat['data_txt'].append(lines)
            self.young_data['time'], self.young_data['centrifugal_force'], lines = \
                self._deform_decode_1d_table(n_data_cf)
            self.mech_to_heat['data_txt'].append(lines)

    def _deform_decode_damage(self, line):
        """
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[]
        :param line:
        :return:
        """
        material_num = int(line[1])
        ftype = int(line[2])
        self.damage_data['style'] = "deform"
        self.damage_data['deform_key'] = line[0]
        self.damage_data['material_num'] = material_num
        self.damage_data['ftype'] = ftype
        self.damage_data['data_txt'] = [line]
        # if ftype in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 13, 14, 15, 16]:
        if ftype == 11:
            second_line = self._lines.pop(0).strip().split()
            self.damage_data['data_txt'].extend(second_line)
        elif ftype in {12, 17}:
            if float(line[4]) > 0.0:
                n_rows = int(line[4])
                for _ in range(n_rows):
                    next_line = self._lines.pop(0).strip().split()
                    self.damage_data['data_txt'].extend(next_line)

    def _deform_decode_flow_stress(self, line):
        """
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        coef={},
        strain=[],
        srate=[],
        temperature=[],
        stress=[],
        process_flags=dict(
            cold_forging=None,
            hot_forging=None,
            ht=None,
            machining=None
        )
        """
        ftype = int(line[2])
        self.flow_stress_data['style'] = "deform"
        self.flow_stress_data['deform_key'] = line[0]
        self.flow_stress_data['material_num'] = int(line[1])
        self.flow_stress_data['ftype'] = ftype
        self.flow_stress_data['data_txt'] = [line]
        if ftype == 1:
            self._deform_decode_flow_stress_ftype_1()
        if ftype in {2, 3}:
            self._deform_decode_flow_stress_ftype_2_3(ftype)

    def _deform_decode_flow_stress_ftype_1(self):
        second_line = self._lines.pop(0).strip().split()
        c, n, m, y = map(float, second_line)
        self.flow_stress_data['data_txt'].append(second_line)
        self.flow_stress_data['ftype_txt'] = "cmny"
        self.flow_stress_data['coef']['c'] = c
        self.flow_stress_data['coef']['n'] = n
        self.flow_stress_data['coef']['m'] = m
        self.flow_stress_data['coef']['y'] = y

    def _deform_decode_flow_stress_ftype_2_3(self, ftype):
        second_line = self._lines.pop(0).strip().split()
        self.flow_stress_data['data_txt'].append(second_line)
        n_strain, n_srate, n_temp = map(int, second_line)
        n_values_total = n_strain + n_srate + n_temp + n_strain * n_srate * n_temp
        n_current = 0
        values_final = []
        while n_current < n_values_total:
            next_line = self._lines.pop(0).strip().split()
            self.flow_stress_data['data_txt'].append(next_line)
            values_of_new_line = [float(x) for x in next_line]
            values_final.extend(values_of_new_line)
            n_current = len(values_final)
        strain_list = [values_final.pop(0) for _ in range(n_strain)]
        srate_list = [values_final.pop(0) for _ in range(n_srate)]
        temp_list = [values_final.pop(0) for _ in range(n_temp)]
        size = (n_temp, n_srate, n_strain)
        stress_list = list(reduce(lambda x, y: map(tuple, zip(*y * (x,))), (iter(values_final), *size[:0:-1])))
        self.flow_stress_data['ftype_txt'] = "tabular_log" if ftype == 2 else "tabular_linear"
        self.flow_stress_data['strain'] = strain_list
        self.flow_stress_data['srate'] = srate_list
        self.flow_stress_data['temperature'] = temp_list
        self.flow_stress_data['stress'] = stress_list

    def _deform_decode_young(self, line):
        # sourcery skip: extract-method, switch
        """
        young_data = dict(
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        coef={},
        temperature=[],
        density=[],
        atom=[],
        young=[]
        :param line:
        :return:
        """
        material_num = int(line[1])
        ftype = int(line[2])
        self.young_data['style'] = "deform"
        self.young_data['deform_key'] = line[0]
        self.young_data['material_num'] = material_num
        self.young_data['ftype'] = ftype
        self.young_data['data_txt'] = [line]
        self.young_data['temperature'] = []
        self.young_data['density'] = []
        self.young_data['atom'] = []
        self.young_data['young'] = []
        if ftype == 0:
            value = float(line[3])
            self.young_data['young'] = [value]
        elif ftype == 1:
            self.young_data['temperature'], self.young_data['young'], lines = self._deform_decode_1d_table(int(line[3]))
            self.young_data['data_txt'].extend(lines)
        elif ftype == 2:
            self.young_data['density'], self.young_data['young'], lines = self._deform_decode_1d_table(int(line[3]))
            self.young_data['data_txt'].extend(lines)
        elif ftype == 3:
            self.young_data['atom'], self.young_data['young'], lines = self._deform_decode_1d_table(int(line[3]))
            self.young_data['data_txt'].extend(lines)
        elif ftype == 4:
            n_temp = int(line[3])
            n_atom = int(line[4])
            temp_list, atom_list, young_list, lines = self._deform_decode_2d_table(n_temp, n_atom)
            self.young_data['atom'] = atom_list
            self.young_data['temperature'] = temp_list
            self.young_data['young'] = young_list
            self.young_data['data_txt'].extend(lines)
            self.young_data['ftype_txt'] = "microstructure"

    def _deform_decode_poison(self, line):
        # sourcery skip: extract-method, switch
        """
        young_data = dict(
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        coef={},
        temperature=[],
        density=[],
        atom=[],
        poison=[]
        :param line:
        :return:
        """
        material_num = int(line[1])
        ftype = int(line[2])
        self.poison_data['style'] = "deform"
        self.poison_data['deform_key'] = line[0]
        self.poison_data['material_num'] = material_num
        self.poison_data['ftype'] = ftype
        self.poison_data['data_txt'] = [line]
        self.poison_data['temperature'] = []
        self.poison_data['density'] = []
        self.poison_data['atom'] = []
        self.poison_data['poison'] = []
        if ftype == 0:
            value = float(line[3])
            self.poison_data['poison'] = [value]
        elif ftype == 1:
            self.poison_data['temperature'], self.poison_data['poison'], lines = \
                self._deform_decode_1d_table(int(line[3]))
            self.poison_data['data_txt'].extend(lines)
        elif ftype == 2:
            self.poison_data['density'], self.poison_data['poison'], lines = \
                self._deform_decode_1d_table(int(line[3]))
            self.poison_data['data_txt'].extend(lines)
        elif ftype == 3:
            self.poison_data['atom'], self.poison_data['poison'], lines = \
                self._deform_decode_1d_table(int(line[3]))
            self.poison_data['data_txt'].extend(lines)
        elif ftype == 4:
            n_temp = int(line[3])
            n_atom = int(line[4])
            n_values_total = n_atom + n_temp + n_atom * n_temp
            n_current = 0
            values_final = []
            while n_current < n_values_total:
                next_line = self._lines.pop(0).strip().split()
                self.poison_data['data_txt'].append(next_line)
                values_of_new_line = [float(x) for x in next_line]
                values_final.extend(values_of_new_line)
                n_current = len(values_final)
            temp_list = [values_final.pop(0) for _ in range(n_temp)]
            atom_list = [values_final.pop(0) for _ in range(n_atom)]
            # poison_array = reshape(array(values_final), (n_temp, n_atom)).tolist()
            size = (n_temp, n_atom)
            poison_list = list(reduce(lambda x, y: map(tuple, zip(*y * (x,))), (iter(values_final), *size[:0:-1])))
            self.poison_data['ftype_txt'] = "microstructure"
            self.poison_data['atom'] = atom_list
            self.poison_data['temperature'] = temp_list
            self.poison_data['poison'] = poison_list

    def _deform_decode_thermal_expansion(self, line):
        # sourcery skip: extract-method, switch
        """
        young_data = dict(
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        coef={},
        temperature=[],
        density=[],
        atom=[],
        thermal_expansion=[]
        :param line:
        :return:
        """
        material_num = int(line[1])
        ftype = int(line[2])
        self.thermal_expansion_data['style'] = "deform"
        self.thermal_expansion_data['deform_key'] = line[0]
        self.thermal_expansion_data['material_num'] = material_num
        self.thermal_expansion_data['ftype'] = ftype
        self.thermal_expansion_data['data_txt'] = [line]
        self.thermal_expansion_data['temperature'] = []
        self.thermal_expansion_data['density'] = []
        self.thermal_expansion_data['atom'] = []
        self.thermal_expansion_data['thermal_expansion'] = []
        if ftype == 0:
            value = float(line[3])
            self.thermal_expansion_data['thermal_expansion'] = [value]
        elif ftype == 1:
            self.thermal_expansion_data['temperature'], self.thermal_expansion_data['thermal_expansion'], lines = \
                self._deform_decode_1d_table(int(line[3]))
            self.thermal_expansion_data['data_txt'].extend(lines)
        elif ftype == 2:
            self.thermal_expansion_data['density'], self.thermal_expansion_data['thermal_expansion'], lines = \
                self._deform_decode_1d_table(int(line[3]))
            self.thermal_expansion_data['data_txt'].extend(lines)
        elif ftype == 3:
            self.thermal_expansion_data['atom'], self.thermal_expansion_data['thermal_expansion'], lines = \
                self._deform_decode_1d_table(int(line[3]))
            self.thermal_expansion_data['data_txt'].extend(lines)
        elif ftype == 4:
            n_temp = int(line[3])
            n_atom = int(line[4])
            n_values_total = n_atom + n_temp + n_atom * n_temp
            n_current = 0
            values_final = []
            while n_current < n_values_total:
                next_line = self._lines.pop(0).strip().split()
                self.thermal_expansion_data['data_txt'].append(next_line)
                values_of_new_line = [float(x) for x in next_line]
                values_final.extend(values_of_new_line)
                n_current = len(values_final)
            temp_list = [values_final.pop(0) for _ in range(n_temp)]
            atom_list = [values_final.pop(0) for _ in range(n_atom)]
            # thermal_expansion_array = reshape(array(values_final), (n_temp, n_atom)).tolist()
            size = (n_temp, n_atom)
            thermal_expansion_list = list(
                reduce(lambda x, y: map(tuple, zip(*y * (x,))), (iter(values_final), *size[:0:-1]))
            )
            self.thermal_expansion_data['ftype_txt'] = "microstructure"
            self.thermal_expansion_data['atom'] = atom_list
            self.thermal_expansion_data['temperature'] = temp_list
            self.thermal_expansion_data['thermal_expansion'] = thermal_expansion_list

    def _deform_decode_conductivity(self, line):
        # sourcery skip: extract-method, switch
        """
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        coef={},
        temperature=[],
        density=[],
        atom=[],
        conductivity=[]
        :param line:
        :return:
        """
        material_num = int(line[1])
        ftype = int(line[2])
        self.conductivity_data['style'] = "deform"
        self.conductivity_data['deform_key'] = line[0]
        self.conductivity_data['material_num'] = material_num
        self.conductivity_data['ftype'] = ftype
        self.conductivity_data['data_txt'] = [line]
        self.conductivity_data['temperature'] = []
        self.conductivity_data['density'] = []
        self.conductivity_data['atom'] = []
        self.conductivity_data['conductivity'] = []
        if ftype == 0:
            value = float(line[3])
            self.conductivity_data['conductivity'] = [value]
        elif ftype == 1:
            self.conductivity_data['temperature'], self.conductivity_data['conductivity'], lines = \
                self._deform_decode_1d_table(int(line[3]))
            self.conductivity_data['data_txt'].extend(lines)
        elif ftype == 2:
            self.conductivity_data['density'], self.conductivity_data['conductivity'], lines = \
                self._deform_decode_1d_table(int(line[3]))
            self.conductivity_data['data_txt'].extend(lines)
        elif ftype == 3:
            self.conductivity_data['atom'], self.conductivity_data['conductivity'], lines = \
                self._deform_decode_1d_table(int(line[3]))
            self.conductivity_data['data_txt'].extend(lines)
        elif ftype == 4:
            n_temp = int(line[3])
            n_atom = int(line[4])
            n_values_total = n_atom + n_temp + n_atom * n_temp
            n_current = 0
            values_final = []
            while n_current < n_values_total:
                next_line = self._lines.pop(0).strip().split()
                self.conductivity_data['data_txt'].append(next_line)
                values_of_new_line = [float(x) for x in next_line]
                values_final.extend(values_of_new_line)
                n_current = len(values_final)
            temp_list = [values_final.pop(0) for _ in range(n_temp)]
            atom_list = [values_final.pop(0) for _ in range(n_atom)]
            # conductivity_array = reshape(array(values_final), (n_temp, n_atom)).tolist()
            size = (n_temp, n_atom)
            conductivity_list = list(
                reduce(lambda x, y: map(tuple, zip(*y * (x,))), (iter(values_final), *size[:0:-1]))
            )
            self.conductivity_data['ftype_txt'] = "microstructure"
            self.conductivity_data['atom'] = atom_list
            self.conductivity_data['temperature'] = temp_list
            self.conductivity_data['conductivity'] = conductivity_list

    def _deform_decode_heat_capacity(self, line):
        # sourcery skip: extract-method, switch
        """
        young_data = dict(
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        coef={},
        temperature=[],
        density=[],
        atom=[],
        heat_capacity=[]
        :param line:
        :return:
        """
        material_num = int(line[1])
        ftype = int(line[2])
        self.heat_capacity_data['style'] = "deform"
        self.heat_capacity_data['deform_key'] = line[0]
        self.heat_capacity_data['material_num'] = material_num
        self.heat_capacity_data['ftype'] = ftype
        self.heat_capacity_data['data_txt'] = [line]
        self.heat_capacity_data['temperature'] = []
        self.heat_capacity_data['density'] = []
        self.heat_capacity_data['atom'] = []
        self.heat_capacity_data['heat_capacity'] = []
        if ftype == 0:
            value = float(line[3])
            self.heat_capacity_data['heat_capacity'] = [value]
        elif ftype == 1:
            self.heat_capacity_data['temperature'], self.heat_capacity_data['heat_capacity'], lines = \
                self._deform_decode_1d_table(int(line[3]))
            self.heat_capacity_data['data_txt'].extend(lines)
        elif ftype == 2:
            self.heat_capacity_data['density'], self.heat_capacity_data['heat_capacity'], lines = \
                self._deform_decode_1d_table(int(line[3]))
            self.heat_capacity_data['data_txt'].extend(lines)
        elif ftype == 3:
            self.heat_capacity_data['atom'], self.heat_capacity_data['heat_capacity'], lines = \
                self._deform_decode_1d_table(int(line[3]))
            self.heat_capacity_data['data_txt'].extend(lines)
        elif ftype == 4:
            n_temp = int(line[3])
            n_atom = int(line[4])
            n_values_total = n_atom + n_temp + n_atom * n_temp
            n_current = 0
            values_final = []
            while n_current < n_values_total:
                next_line = self._lines.pop(0).strip().split()
                self.heat_capacity_data['data_txt'].append(next_line)
                values_of_new_line = [float(x) for x in next_line]
                values_final.extend(values_of_new_line)
                n_current = len(values_final)
            temp_list = [values_final.pop(0) for _ in range(n_temp)]
            atom_list = [values_final.pop(0) for _ in range(n_atom)]
            # heat_capacity_array = reshape(array(values_final), (n_temp, n_atom)).tolist()
            size = (n_temp, n_atom)
            heat_capacity_list = list(
                reduce(lambda x, y: map(tuple, zip(*y * (x,))), (iter(values_final), *size[:0:-1]))
            )
            self.heat_capacity_data['ftype_txt'] = "microstructure"
            self.heat_capacity_data['atom'] = atom_list
            self.heat_capacity_data['temperature'] = temp_list
            self.heat_capacity_data['heat_capacity'] = heat_capacity_list

    def _deform_decode_mass_density(self, line):
        """
        young_data = dict(
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        coef={},
        temperature=[],
        density=[],
        atom=[],
        mass_density=[]
        :param line:
        :return:
        """
        material_num = int(line[1])
        ftype = int(line[2])
        self.mass_density_data['style'] = "deform"
        self.mass_density_data['deform_key'] = line[0]
        self.mass_density_data['material_num'] = material_num
        self.mass_density_data['ftype'] = ftype
        self.mass_density_data['data_txt'] = [line]
        self.mass_density_data['temperature'] = []
        self.mass_density_data['density'] = []
        self.mass_density_data['atom'] = []
        self.mass_density_data['mass_density'] = []
        if ftype == 0:
            value = float(line[3])
            self.mass_density_data['mass_density'] = [value]
        elif ftype == 1:
            self.mass_density_data['temperature'], self.mass_density_data['mass_density'], lines = \
                self._deform_decode_1d_table(int(line[3]))
            self.mass_density_data['data_txt'].extend(lines)
        elif ftype == 2:
            self.mass_density_data['density'], self.mass_density_data['mass_density'], lines = \
                self._deform_decode_1d_table(int(line[3]))
            self.mass_density_data['data_txt'].extend(lines)
        elif ftype == 3:
            self.mass_density_data['atom'], self.mass_density_data['mass_density'], lines = \
                self._deform_decode_1d_table(int(line[3]))
            self.mass_density_data['data_txt'].extend(lines)

    def _deform_decode_alpha_coarsening(self, line):
        # sourcery skip: extract-method, switch
        """
        style="",
        deform_key="",
        material_num=int(),
        coarsening_type=int(),
        ftype=int(),
        ftype_txt="Not defined",
        data_txt=[],
        coef={},
        temperature=[],
        srate=[],
        alpha_coarsening=[]
        :param line:
        :return:
        """
        material_num = int(line[1])
        coarsening_type = int(line[2])
        self.alpha_coarsening_data['style'] = "deform"
        self.alpha_coarsening_data['deform_key'] = line[0]
        self.alpha_coarsening_data['material_num'] = material_num
        self.alpha_coarsening_data['coarsening_type'] = coarsening_type
        self.alpha_coarsening_data['data_txt'] = [line]
        self.alpha_coarsening_data['temperature'] = []
        self.alpha_coarsening_data['srate'] = []
        self.alpha_coarsening_data['alpha_coarsening'] = []
        if coarsening_type == 1:
            second_line = self._lines.pop(0).strip().split()
            ftype = int(second_line[0])
            self.alpha_coarsening_data['ftype'] = ftype
            self.alpha_coarsening_data['data_txt'].extend(second_line)
            if ftype == 0:
                self.alpha_coarsening_data['alpha_coarsening'] = [float(second_line[1])]
                self.alpha_coarsening_data['ftype_txt'] = "Constant"
            elif ftype == 5:
                n_temp = int(second_line[1])
                n_srate = int(second_line[2])
                n_values_total = n_srate + n_temp + n_srate * n_temp
                n_current = 0
                values_final = []
                while n_current < n_values_total:
                    next_line = self._lines.pop(0).strip().split()
                    self.alpha_coarsening_data['data_txt'].append(next_line)
                    values_of_new_line = [float(x) for x in next_line]
                    values_final.extend(values_of_new_line)
                    n_current = len(values_final)
                temp_list = [values_final.pop(0) for _ in range(n_temp)]
                srate_list = [values_final.pop(0) for _ in range(n_srate)]
                # alpha_coarsening_array = reshape(array(values_final), (n_temp, n_atom)).tolist()
                size = (n_temp, n_srate)
                alpha_coarsening_list = list(
                    reduce(lambda x, y: map(tuple, zip(*y * (x,))), (iter(values_final), *size[:0:-1]))
                )
                self.alpha_coarsening_data['ftype_txt'] = "f(temperature, strain_rate)"
                self.alpha_coarsening_data['srate'] = srate_list
                self.alpha_coarsening_data['temperature'] = temp_list
                self.alpha_coarsening_data['alpha_coarsening'] = alpha_coarsening_list

    def _deform_decode_diffusion_bonding(self, line):
        # sourcery skip: extract-method, switch
        """
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        coef={},
        temperature=[],
        pressure=[],
        time=[]
        :param line:
        :return:
        """
        material_num = int(line[1])
        ftype = int(line[2])
        self.diffusion_bonding_data['style'] = "deform"
        self.diffusion_bonding_data['deform_key'] = line[0]
        self.diffusion_bonding_data['material_num'] = material_num
        self.diffusion_bonding_data['ftype'] = ftype
        self.diffusion_bonding_data['data_txt'] = [line]
        self.diffusion_bonding_data['temperature'] = []
        self.diffusion_bonding_data['pressure'] = []
        self.diffusion_bonding_data['time'] = []
        if ftype == 0:
            diffusion_bonding_time = float(line[3])
            self.diffusion_bonding_data['time'] = [diffusion_bonding_time]
            self.diffusion_bonding_data['ftype_txt'] = "Constant"
        elif ftype == 7:
            n_temp = int(line[3])
            n_pressure = int(line[4])
            n_values_total = n_pressure + n_temp + n_pressure * n_temp
            n_current = 0
            values_final = []
            while n_current < n_values_total:
                next_line = self._lines.pop(0).strip().split()
                self.diffusion_bonding_data['data_txt'].append(next_line)
                values_of_new_line = [float(x) for x in next_line]
                values_final.extend(values_of_new_line)
                n_current = len(values_final)
            temp_list = [values_final.pop(0) for _ in range(n_temp)]
            pressure_list = [values_final.pop(0) for _ in range(n_pressure)]
            # diffusion_bonding_array = reshape(array(values_final), (n_temp, n_atom)).tolist()
            size = (n_temp, n_pressure)
            diffusion_bonding_time_list = list(
                reduce(lambda x, y: map(tuple, zip(*y * (x,))), (iter(values_final), *size[:0:-1]))
            )
            self.diffusion_bonding_data['ftype_txt'] = "f(temperature, strain_rate)"
            self.diffusion_bonding_data['pressure'] = pressure_list
            self.diffusion_bonding_data['temperature'] = temp_list
            self.diffusion_bonding_data['time'] = diffusion_bonding_time_list

    def _deform_decode_emissivity(self, line):
        """
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        coef={},
        temperature=[],
        emissivity=[]
        :param line:
        :return:
        """
        material_num = int(line[1])
        ftype = int(line[2])
        self.emissivity_data['style'] = "deform"
        self.emissivity_data['deform_key'] = line[0]
        self.emissivity_data['material_num'] = material_num
        self.emissivity_data['ftype'] = ftype
        self.emissivity_data['data_txt'] = [line]
        self.emissivity_data['temperature'] = []
        self.emissivity_data['emissivity'] = []
        if ftype == 0:
            value = float(line[3])
            self.emissivity_data['emissivity'] = [value]
        elif ftype == 1:
            self.emissivity_data['temperature'], self.emissivity_data['emissivity'], lines = \
                self._deform_decode_1d_table(int(line[3]))
            self.emissivity_data['data_txt'].extend(lines)

    def _deform_decode_hardness(self, line):
        # sourcery skip: extract-method, switch
        """
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        coef={},
        temperature=[],
        density=[],
        atom=[],
        hardness=[]
        :param line:
        :return:
        """
        material_num = int(line[1])
        ftype = int(line[2])
        self.hardness_data['style'] = "deform"
        self.hardness_data['deform_key'] = line[0]
        self.hardness_data['material_num'] = material_num
        self.hardness_data['ftype'] = ftype
        self.hardness_data['data_txt'] = [line]
        self.hardness_data['temperature'] = []
        self.hardness_data['density'] = []
        self.hardness_data['atom'] = []
        self.hardness_data['hardness'] = []
        if ftype == 0:
            value = float(line[3])
            self.hardness_data['hardness'] = [value]
        elif ftype == 1:
            self.hardness_data['atom'], self.hardness_data['hardness'], lines = \
                self._deform_decode_1d_table(int(line[3]))
            self.hardness_data['data_txt'].extend(lines)
        elif ftype == 2:
            self.hardness_data['temperature'], self.hardness_data['hardness'], lines = \
                self._deform_decode_1d_table(int(line[3]))
            self.hardness_data['data_txt'].extend(lines)
        elif ftype == 3:
            self.hardness_data['density'], self.hardness_data['hardness'], lines = \
                self._deform_decode_1d_table(
                    int(line[3]))
            self.hardness_data['data_txt'].extend(lines)
        elif ftype == 4:
            n_temp = int(line[3])
            n_atom = int(line[4])
            n_values_total = n_atom + n_temp + n_atom * n_temp
            n_current = 0
            values_final = []
            while n_current < n_values_total:
                next_line = self._lines.pop(0).strip().split()
                self.hardness_data['data_txt'].append(next_line)
                values_of_new_line = [float(x) for x in next_line]
                values_final.extend(values_of_new_line)
                n_current = len(values_final)
            temp_list = [values_final.pop(0) for _ in range(n_temp)]
            atom_list = [values_final.pop(0) for _ in range(n_atom)]
            # hardness_array = reshape(array(values_final), (n_temp, n_atom)).tolist()
            size = (n_temp, n_atom)
            hardness_list = list(reduce(lambda x, y: map(tuple, zip(*y * (x,))), (iter(values_final), *size[:0:-1])))
            self.hardness_data['ftype_txt'] = "microstructure"
            self.hardness_data['atom'] = atom_list
            self.hardness_data['temperature'] = temp_list
            self.hardness_data['hardness'] = hardness_list

    def _deform_decode_mixture_material(self, line):
        """
        style="",
        deform_key="",
        material_num=int(),
        is_mixture=bool(),
        data_txt=[],
        dependent_phases=[]
        :param line:
        :return:
        """
        material_num = int(line[1])
        number_of_dependent_phases = int(line[2])
        self.mixture_material_data['style'] = "deform"
        self.mixture_material_data['deform_key'] = line[0]
        self.mixture_material_data['material_num'] = material_num
        self.mixture_material_data['data_txt'] = [line]
        self.mixture_material_data['dependent_phases'] = []
        if number_of_dependent_phases == 0:
            self.mixture_material_data['is_mixture'] = False
        else:
            self.mixture_material_data['is_mixture'] = True
            for _ in range(number_of_dependent_phases):
                line = self._lines.pop(0).strip()
                self.mixture_material_data['dependent_phases'].append(line)
                self.mixture_material_data['data_txt'].append(line)

    def _deform_decode_creep(self, line):
        # sourcery skip: extract-duplicate-method, switch
        """
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        coef={},
        temperature=[],
        strain=[],
        stress=[],
        time=[],
        srate=[],
        grain_size=[],
        precipitate_size=[],
        precipitate_shape=[],
        precipitate_volume_fraction=[],
        creep=[]
        """
        ftype = int(line[2])
        self.creep_data['style'] = "deform"
        self.creep_data['deform_key'] = line[0]
        self.creep_data['material_num'] = int(line[1])
        self.creep_data['ftype'] = ftype
        self.creep_data['data_txt'] = [line]
        if ftype == 0:
            self.creep_data['ftype_txt'] = "None"
        if ftype == 1:
            self.creep_data['ftype_txt'] = "Prezyna model"
            coef_table = self._deform_decode_coef_table_1d(int(line[3]), False)
            self.creep_data['temperature'] = [x[0] for x in coef_table]
            self.creep_data['coef']['gamma'] = [x[1] for x in coef_table]
            self.creep_data['coef']['m'] = [x[2] for x in coef_table]
        elif ftype == 2:
            self.creep_data['ftype_txt'] = "Power law without yielding"
            coef_table = self._deform_decode_coef_table_1d(int(line[3]), False)
            self.creep_data['temperature'] = [x[0] for x in coef_table]
            self.creep_data['coef']['gamma'] = [x[1] for x in coef_table]
            self.creep_data['coef']['m'] = [x[2] for x in coef_table]
        elif ftype == 3:
            self.creep_data['ftype_txt'] = "Baily-Norton model"
            coef_table = self._deform_decode_coef_table_1d(int(line[3]), False)
            self.creep_data['temperature'] = [x[0] for x in coef_table]
            self.creep_data['coef']['k'] = [x[1] for x in coef_table]
            self.creep_data['coef']['n'] = [x[2] for x in coef_table]
            self.creep_data['coef']['m'] = [x[3] for x in coef_table]
            self.creep_data['coef']['q'] = [x[4] for x in coef_table]
            self.creep_data['coef']['r'] = [x[5] for x in coef_table]
        elif ftype == 4:
            self.creep_data['ftype_txt'] = "Soderberg model"
            coef_table = self._deform_decode_coef_table_1d(int(line[3]), False)
            self.creep_data['temperature'] = [x[0] for x in coef_table]
            self.creep_data['coef']['k'] = [x[1] for x in coef_table]
            self.creep_data['coef']['n'] = [x[2] for x in coef_table]
            self.creep_data['coef']['c'] = [x[3] for x in coef_table]
        elif ftype == 5:
            self.creep_data['ftype_txt'] = "f(temperature, stress, strain)"
            list_x, list_y, list_z, list_values, lines = self._deform_decode_3d_table()
            self.creep_data['temperature'] = list_x
            self.creep_data['stress'] = list_y
            self.creep_data['strain'] = list_z
            self.creep_data['creep'] = list_values
            self.creep_data['data_txt'].extend(lines)
        elif ftype == 6:
            self.creep_data['ftype_txt'] = "f(temperature, stress, time)"
            list_x, list_y, list_z, list_values, lines = self._deform_decode_3d_table()
            self.creep_data['temperature'] = list_x
            self.creep_data['stress'] = list_y
            self.creep_data['time'] = list_z
            self.creep_data['creep'] = list_values
            self.creep_data['data_txt'].extend(lines)
        elif ftype == 7:
            self.creep_data['ftype_txt'] = "Table analytical_solution with linear interpolation"
            self._deform_decode_creep_ftype_78()
        elif ftype == 8:
            self.creep_data['ftype_txt'] = "Table analytical_solution with log interpolation"
            self._deform_decode_creep_ftype_78()

    def _deform_decode_creep_ftype_78(self):
        # sourcery skip: extract-duplicate-method, merge-nested-ifs, swap-nested-ifs, switch
        """
        Read dimensions of analytical_solution.
        Codes:
        1: temperature=[],
        2: strain=[],
        3: stress=[],
        4: time=[],
        5: srate=[],
        6: grain_size=[],
        7: precipitate_size=[],
        8: precipitate_shape=[],
        9: precipitate_volume_fraction=[],
        """
        second_line = self._lines.pop(0).strip()
        lines = [second_line]
        n_vars = int(second_line)
        dimensions = self._deform_decode_coef_table_1d(n_vars, True)
        # Calculate total number of values
        size = [x[0] for x in dimensions]
        n_values_total = sum(size) + math.prod(size)
        # Read values of Dimensions into corresponding lists
        n_current = 0
        values_final = []
        variables_order = []
        variables_list = []
        is_not_strictly_ascending_index_list = []
        while n_current < n_values_total:
            next_line = self._lines.pop(0).strip().split()
            lines.append(next_line)
            values_of_new_line = [float(x) for x in next_line]
            values_final.extend(values_of_new_line)
            n_current = len(values_final)
        for i in range(len(dimensions)):
            variable_type = dimensions[i][1]
            variable_size = dimensions[i][0]
            values_of_variable = [values_final.pop(0) for _ in range(variable_size)]
            # Create list of flags; Flag == True if variable is strictly ascending;
            is_strictly_ascending = False
            if len(values_of_variable) >= 2:
                if values_of_variable == sorted(list(set(values_of_variable))):  # True if ascending and no duplicates
                    is_strictly_ascending = True
            is_not_strictly_ascending_index_list.append(i) if not is_strictly_ascending else None
            # Fill variables axes
            if is_strictly_ascending:
                if variable_type == 1:
                    self.creep_data['temperature'] = values_of_variable
                    variables_list.append(values_of_variable)
                    variables_order.append("temperature")
                elif variable_type == 2:
                    self.creep_data['strain'] = values_of_variable
                    variables_list.append(values_of_variable)
                    variables_order.append("strain")
                elif variable_type == 3:
                    self.creep_data['stress'] = values_of_variable
                    variables_list.append(values_of_variable)
                    variables_order.append("stress")
                elif variable_type == 4:
                    self.creep_data['time'] = values_of_variable
                    variables_list.append(values_of_variable)
                    variables_order.append("time")
                elif variable_type == 5:
                    self.creep_data['srate'] = values_of_variable
                    variables_list.append(values_of_variable)
                    variables_order.append("srate")
                elif variable_type == 6:
                    self.creep_data['grain_size'] = values_of_variable
                    variables_list.append(values_of_variable)
                    variables_order.append("grain_size")
                elif variable_type == 7:
                    self.creep_data['precipitate_size'] = values_of_variable
                    variables_list.append(values_of_variable)
                    variables_order.append("precipitate_size")
                elif variable_type == 8:
                    self.creep_data['precipitate_shape'] = values_of_variable
                    variables_list.append(values_of_variable)
                    variables_order.append("precipitate_shape")
                elif variable_type == 9:
                    self.creep_data['precipitate_volume_fraction'] = values_of_variable
                    variables_list.append(values_of_variable)
                    variables_order.append("precipitate_volume_fraction")
        creep_list = list(reduce(lambda x, y: map(tuple, zip(*y * (x,))), (iter(values_final), *size[:0:-1])))
        # Delete axes which are not strictly ascending
        if is_not_strictly_ascending_index_list:
            creep_arr = array(creep_list)
            for i in sorted(is_not_strictly_ascending_index_list, reverse=True):
                variable_size = dimensions[i][0]
                if variable_size >= 2:
                    creep_arr = np_delete(creep_arr, list(range(1, variable_size)), axis=i)
                del dimensions[i]
            self.creep_data['creep'] = creep_arr.squeeze().tolist()
        else:
            self.creep_data['creep'] = creep_list
        self.creep_data['data_txt'].extend(lines)
        self.creep_data['coef']['dimensions'] = dimensions
        self.creep_data['coef']['variables_order'] = variables_order
        self.creep_data['coef']['variables_list'] = variables_list

    def _deform_decode_carburization(self, line):
        # sourcery skip: extract-duplicate-method, extract-method, switch
        """
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        coef={},
        temperature=[],
        atom=[],
        carburization=[]
        :param line:
        :return:
        """
        material_num = int(line[1])
        ftype = int(line[2])
        self.carburization_data['style'] = "deform"
        self.carburization_data['deform_key'] = line[0]
        self.carburization_data['material_num'] = material_num
        self.carburization_data['ftype'] = ftype
        self.carburization_data['data_txt'] = [line]
        self.carburization_data['temperature'] = []
        self.carburization_data['atom'] = []
        self.carburization_data['carburization'] = []
        if ftype == 0:
            value = float(line[3])
            self.carburization_data['carburization'] = [value]
        elif ftype == 1:
            n_temp = int(line[3])
            n_atom = int(line[4])
            temp_list, atom_list, carburization_list, lines = self._deform_decode_2d_table(n_temp, n_atom)
            self.carburization_data['atom'] = atom_list
            self.carburization_data['temperature'] = temp_list
            self.carburization_data['carburization'] = carburization_list
            self.carburization_data['data_txt'].extend(lines)
            self.carburization_data['ftype_txt'] = "f(temperature, atom)"
        elif ftype == 2:
            n_rows = int(line[3])
            coef_list, lines = self._deform_decode_1dxn_table(n_rows)
            self.carburization_data['coef']['c1'] = coef_list[1]
            self.carburization_data['coef']['c2'] = coef_list[2]
            self.carburization_data['temperature'] = coef_list[0]
            self.carburization_data['data_txt'].extend(lines)
            self.carburization_data['ftype_txt'] = "=C1(T)exp((C2(T)*A)"
        elif ftype == 3:
            n_rows = int(line[3])
            coef_list, lines = self._deform_decode_1dxn_table(n_rows)
            self.carburization_data['coef']['c1'] = coef_list[1]
            self.carburization_data['coef']['c2'] = coef_list[2]
            self.carburization_data['atom'] = coef_list[0]
            self.carburization_data['data_txt'].extend(lines)
            self.carburization_data['ftype_txt'] = "=C1(A)exp((C2(A)/T)"

    def _deform_decode_resistivity(self, line):
        # sourcery skip: extract-duplicate-method, switch
        """
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        coef={},
        temperature=[],
        density=[],
        resistivity=[]
        :param line:
        :return:
        """
        material_num = int(line[1])
        ftype = int(line[2])
        self.resistivity_data['style'] = "deform"
        self.resistivity_data['deform_key'] = line[0]
        self.resistivity_data['material_num'] = material_num
        self.resistivity_data['ftype'] = ftype
        self.resistivity_data['data_txt'] = [line]
        self.resistivity_data['temperature'] = []
        self.resistivity_data['density'] = []
        self.resistivity_data['resistivity'] = []
        if ftype == 0:
            value = float(line[3])
            self.resistivity_data['resistivity'] = [value]
            self.resistivity_data['ftype_txt'] = "constant"
        elif ftype == 1:
            self.resistivity_data['temperature'], self.resistivity_data['resistivity'], lines = \
                self._deform_decode_1d_table(int(line[3]))
            self.resistivity_data['data_txt'].extend(lines)
            self.resistivity_data['ftype_txt'] = "f(temperature)"
        elif ftype == 2:
            self.resistivity_data['density'], self.resistivity_data['resistivity'], lines = \
                self._deform_decode_1d_table(int(line[3]))
            self.resistivity_data['data_txt'].extend(lines)
            self.resistivity_data['ftype_txt'] = "f(density)"

    def _deform_decode_ultimate_strength(self, line):
        """
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        coef={},
        temperature=[],
        ultimate_strength=[]
        :param line:
        :return:
        """
        material_num = int(line[1])
        ftype = int(line[2])
        self.ultimate_strength_data['style'] = "deform"
        self.ultimate_strength_data['deform_key'] = line[0]
        self.ultimate_strength_data['material_num'] = material_num
        self.ultimate_strength_data['ftype'] = ftype
        self.ultimate_strength_data['data_txt'] = [line]
        self.ultimate_strength_data['temperature'] = []
        self.ultimate_strength_data['ultimate_strength'] = []
        if ftype == 0:
            value = float(line[3])
            self.ultimate_strength_data['ultimate_strength'] = [value]
            self.ultimate_strength_data['ftype_txt'] = "constant"
        elif ftype == 1:
            self.ultimate_strength_data['temperature'], self.ultimate_strength_data['ultimate_strength'], lines = \
                self._deform_decode_1d_table(int(line[3]))
            self.ultimate_strength_data['data_txt'].extend(lines)
            self.ultimate_strength_data['ftype_txt'] = "f(temperature)"

    def _deform_decode_hardening_rule(self, line):
        """
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[]
        :param line:
        :return:
        """
        material_num = int(line[1])
        ftype = int(line[2])
        self.hardening_rule_data['style'] = "deform"
        self.hardening_rule_data['deform_key'] = line[0]
        self.hardening_rule_data['material_num'] = material_num
        self.hardening_rule_data['ftype'] = ftype
        self.hardening_rule_data['data_txt'] = [line]
        if ftype == 0:
            self.hardening_rule_data['ftype_txt'] = "Isotropic"
        elif ftype == 1:
            self.hardening_rule_data['ftype_txt'] = "Kinematic"

    def _deform_decode_magnetic_permeability(self, line):
        """
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        coef={},
        temperature=[],
        density=[],
        magnetic_intensity=[],
        magnetic_permeability=[]
        :param line:
        :return:
        """
        material_num = int(line[1])
        ftype = int(line[2])
        self.magnetic_permeability_data['style'] = "deform"
        self.magnetic_permeability_data['deform_key'] = line[0]
        self.magnetic_permeability_data['material_num'] = material_num
        self.magnetic_permeability_data['ftype'] = ftype
        self.magnetic_permeability_data['data_txt'] = [line]
        self.magnetic_permeability_data['temperature'] = []
        self.magnetic_permeability_data['density'] = []
        self.magnetic_permeability_data['magnetic_intensity'] = []
        self.magnetic_permeability_data['magnetic_permeability'] = []
        if ftype == 0:
            value = float(line[3])
            self.magnetic_permeability_data['magnetic_permeability'] = [value]
        elif ftype == 1:
            temp_list, magnetic_permeability_list, lines = self._deform_decode_1d_table(int(line[3]))
            self.magnetic_permeability_data['temperature'] = temp_list
            self.magnetic_permeability_data['magnetic_permeability'] = magnetic_permeability_list
            self.magnetic_permeability_data['data_txt'].extend(lines)
            self.magnetic_permeability_data['ftype_txt'] = "f(temperature)"
        elif ftype == 2:
            density_list, magnetic_permeability_list, lines = self._deform_decode_1d_table(int(line[3]))
            self.magnetic_permeability_data['density'] = density_list
            self.magnetic_permeability_data['magnetic_permeability'] = magnetic_permeability_list
            self.magnetic_permeability_data['data_txt'].extend(lines)
            self.magnetic_permeability_data['ftype_txt'] = "f(density)"
        elif ftype == 4:
            n_temp = int(line[3])
            n_magnetic_intensity = int(line[4])
            temp_list, magnetic_intensity_list, magnetic_permeability_list, lines = \
                self._deform_decode_2d_table(n_temp, n_magnetic_intensity)
            self.magnetic_permeability_data['temperature'] = temp_list
            self.magnetic_permeability_data['magnetic_intensity'] = magnetic_intensity_list
            self.magnetic_permeability_data['magnetic_permeability'] = magnetic_permeability_list
            self.magnetic_permeability_data['data_txt'].extend(lines)
            self.magnetic_permeability_data['ftype_txt'] = "f(temperature, magnetic_intensity)"

    def _deform_decode_magnetic_permitivity(self, line):
        # sourcery skip: extract-duplicate-method, switch
        """
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        coef={},
        temperature=[],
        density=[],
        magnetic_permitivity=[]
        :param line:
        :return:
        """
        material_num = int(line[1])
        ftype = int(line[2])
        self.magnetic_permitivity_data['style'] = "deform"
        self.magnetic_permitivity_data['deform_key'] = line[0]
        self.magnetic_permitivity_data['material_num'] = material_num
        self.magnetic_permitivity_data['ftype'] = ftype
        self.magnetic_permitivity_data['data_txt'] = [line]
        self.magnetic_permitivity_data['temperature'] = []
        self.magnetic_permitivity_data['density'] = []
        self.magnetic_permitivity_data['magnetic_permitivity'] = []
        if ftype == 0:
            value = float(line[3])
            self.magnetic_permitivity_data['magnetic_permitivity'] = [value]
        elif ftype == 1:
            temp_list, magnetic_permitivity_list, lines = self._deform_decode_1d_table(int(line[3]))
            self.magnetic_permitivity_data['temperature'] = temp_list
            self.magnetic_permitivity_data['magnetic_permitivity'] = magnetic_permitivity_list
            self.magnetic_permitivity_data['data_txt'].extend(lines)
            self.magnetic_permitivity_data['ftype_txt'] = "f(temperature)"
        elif ftype == 2:
            density_list, magnetic_permitivity_list, lines = self._deform_decode_1d_table(int(line[3]))
            self.magnetic_permitivity_data['density'] = density_list
            self.magnetic_permitivity_data['magnetic_permitivity'] = magnetic_permitivity_list
            self.magnetic_permitivity_data['data_txt'].extend(lines)
            self.magnetic_permitivity_data['ftype_txt'] = "f(density)"

    def _deform_decode_burgers(self, line):
        """
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        coef={},
        temperature=[],
        stress=[],
        concentration=[],
        burgers=[]
        :param line:
        :return:
        """
        material_num = int(line[1])
        ftype = int(line[2])
        self.burgers_data['style'] = "deform"
        self.burgers_data['deform_key'] = line[0]
        self.burgers_data['material_num'] = material_num
        self.burgers_data['ftype'] = ftype
        self.burgers_data['data_txt'] = [line]
        self.burgers_data['temperature'] = []
        self.burgers_data['stress'] = []
        self.burgers_data['concentration'] = []
        self.burgers_data['burgers'] = []
        if ftype == 0:
            value = float(line[3])
            self.burgers_data['burgers'] = [value]
        elif ftype == 1:
            temp_list, burgers_list, lines = self._deform_decode_1d_table(int(line[3]))
            self.burgers_data['temperature'] = temp_list
            self.burgers_data['burgers'] = burgers_list
            self.burgers_data['data_txt'].extend(lines)
            self.burgers_data['ftype_txt'] = "f(temperature)"
        elif ftype == 2:
            stress_list, burgers_list, lines = self._deform_decode_1d_table(int(line[3]))
            self.burgers_data['stress'] = stress_list
            self.burgers_data['burgers'] = burgers_list
            self.burgers_data['data_txt'].extend(lines)
            self.burgers_data['ftype_txt'] = "f(stress)"
        elif ftype == 3:
            concentration_list, burgers_list, lines = self._deform_decode_1d_table(int(line[3]))
            self.burgers_data['concentration'] = concentration_list
            self.burgers_data['burgers'] = burgers_list
            self.burgers_data['data_txt'].extend(lines)
            self.burgers_data['ftype_txt'] = "f(concentration)"
        elif ftype == 4:
            n_temp = int(line[3])
            n_stress = int(line[4])
            temp_list, stress_list, burgers_list, lines = \
                self._deform_decode_2d_table(n_temp, n_stress)
            self.burgers_data['temperature'] = temp_list
            self.burgers_data['stress'] = stress_list
            self.burgers_data['burgers'] = burgers_list
            self.burgers_data['data_txt'].extend(lines)
            self.burgers_data['ftype_txt'] = "f(temperature, stress)"
        elif ftype == 5:
            n_temp = int(line[3])
            n_concentration = int(line[4])
            temp_list, concentration_list, burgers_list, lines = \
                self._deform_decode_2d_table(n_temp, n_concentration)
            self.burgers_data['temperature'] = temp_list
            self.burgers_data['concentration'] = concentration_list
            self.burgers_data['burgers'] = burgers_list
            self.burgers_data['data_txt'].extend(lines)
            self.burgers_data['ftype_txt'] = "f(temperature, concentration)"
        elif ftype == 6:
            n_stress = int(line[3])
            n_concentration = int(line[4])
            stress_list, concentration_list, burgers_list, lines = \
                self._deform_decode_2d_table(n_stress, n_concentration)
            self.burgers_data['stress'] = stress_list
            self.burgers_data['concentration'] = concentration_list
            self.burgers_data['burgers'] = burgers_list
            self.burgers_data['data_txt'].extend(lines)
            self.burgers_data['ftype_txt'] = "f(stress, concentration)"
        elif ftype == 7:
            list_x, list_y, list_z, list_values, lines = self._deform_decode_3d_table()
            self.burgers_data['temperature'] = list_x
            self.burgers_data['stress'] = list_y
            self.burgers_data['concentration'] = list_z
            self.burgers_data['burgers'] = list_values
            self.burgers_data['data_txt'].extend(lines)
            self.burgers_data['ftype_txt'] = "f(temperature, stress, concentration)"

    def _deform_decode_dislocation_alpha(self, line):
        """
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        coef={},
        temperature=[],
        srate=[],
        dislocation_alpha=[]
        :param line:
        :return:
        """
        material_num = int(line[1])
        ftype = int(line[2])
        self.dislocation_alpha_data['style'] = "deform"
        self.dislocation_alpha_data['deform_key'] = line[0]
        self.dislocation_alpha_data['material_num'] = material_num
        self.dislocation_alpha_data['ftype'] = ftype
        self.dislocation_alpha_data['data_txt'] = [line]
        self.dislocation_alpha_data['temperature'] = []
        self.dislocation_alpha_data['srate'] = []
        self.dislocation_alpha_data['dislocation_alpha'] = []
        if ftype == 0:
            value = float(line[3])
            self.dislocation_alpha_data['dislocation_alpha'] = [value]
        elif ftype == 1:
            temp_list, dislocation_alpha_list, lines = self._deform_decode_1d_table(int(line[3]))
            self.dislocation_alpha_data['temperature'] = temp_list
            self.dislocation_alpha_data['dislocation_alpha'] = dislocation_alpha_list
            self.dislocation_alpha_data['data_txt'].extend(lines)
            self.dislocation_alpha_data['ftype_txt'] = "f(temperature)"
        elif ftype == 2:
            srate_list, dislocation_alpha_list, lines = self._deform_decode_1d_table(int(line[3]))
            self.dislocation_alpha_data['srate'] = srate_list
            self.dislocation_alpha_data['dislocation_alpha'] = dislocation_alpha_list
            self.dislocation_alpha_data['data_txt'].extend(lines)
            self.dislocation_alpha_data['ftype_txt'] = "f(strain rate)"
        elif ftype == 3:
            n_temp = int(line[3])
            n_srate = int(line[4])
            temp_list, srate_list, dislocation_alpha_list, lines = \
                self._deform_decode_2d_table(n_temp, n_srate)
            self.dislocation_alpha_data['temperature'] = temp_list
            self.dislocation_alpha_data['srate'] = srate_list
            self.dislocation_alpha_data['dislocation_alpha'] = dislocation_alpha_list
            self.dislocation_alpha_data['data_txt'].extend(lines)
            self.dislocation_alpha_data['ftype_txt'] = "f(temperature, strain rate)"

    def _deform_decode_dislocations_number(self, line):
        """
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        coef={},
        temperature=[],
        srate=[],
        dislocations_number=[]
        :param line:
        :return:
        """
        material_num = int(line[1])
        ftype = int(line[2])
        self.dislocations_number_data['style'] = "deform"
        self.dislocations_number_data['deform_key'] = line[0]
        self.dislocations_number_data['material_num'] = material_num
        self.dislocations_number_data['ftype'] = ftype
        self.dislocations_number_data['data_txt'] = [line]
        self.dislocations_number_data['temperature'] = []
        self.dislocations_number_data['srate'] = []
        self.dislocations_number_data['dislocations_number'] = []
        if ftype == 0:
            value = float(line[3])
            self.dislocations_number_data['dislocations_number'] = [value]
        elif ftype == 1:
            temp_list, dislocations_number_list, lines = self._deform_decode_1d_table(int(line[3]))
            self.dislocations_number_data['temperature'] = temp_list
            self.dislocations_number_data['dislocations_number'] = dislocations_number_list
            self.dislocations_number_data['data_txt'].extend(lines)
            self.dislocations_number_data['ftype_txt'] = "f(temperature)"
        elif ftype == 2:
            srate_list, dislocations_number_list, lines = self._deform_decode_1d_table(int(line[3]))
            self.dislocations_number_data['srate'] = srate_list
            self.dislocations_number_data['dislocations_number'] = dislocations_number_list
            self.dislocations_number_data['data_txt'].extend(lines)
            self.dislocations_number_data['ftype_txt'] = "f(strain rate)"
        elif ftype == 3:
            n_temp = int(line[3])
            n_srate = int(line[4])
            temp_list, srate_list, dislocations_number_list, lines = \
                self._deform_decode_2d_table(n_temp, n_srate)
            self.dislocations_number_data['temperature'] = temp_list
            self.dislocations_number_data['srate'] = srate_list
            self.dislocations_number_data['dislocations_number'] = dislocations_number_list
            self.dislocations_number_data['data_txt'].extend(lines)
            self.dislocations_number_data['ftype_txt'] = "f(temperature, strain rate)"

    def _deform_decode_recovery(self, line):
        """
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        coef={},
        temperature=[],
        srate=[],
        recovery=[]
        :param line:
        :return:
        """
        material_num = int(line[1])
        ftype = int(line[2])
        self.recovery_data['style'] = "deform"
        self.recovery_data['deform_key'] = line[0]
        self.recovery_data['material_num'] = material_num
        self.recovery_data['ftype'] = ftype
        self.recovery_data['data_txt'] = [line]
        self.recovery_data['temperature'] = []
        self.recovery_data['srate'] = []
        self.recovery_data['recovery'] = []
        if ftype == 0:
            value = float(line[3])
            self.recovery_data['recovery'] = [value]
        elif ftype == 1:
            temp_list, recovery_list, lines = self._deform_decode_1d_table(int(line[3]))
            self.recovery_data['temperature'] = temp_list
            self.recovery_data['recovery'] = recovery_list
            self.recovery_data['data_txt'].extend(lines)
            self.recovery_data['ftype_txt'] = "f(temperature)"
        elif ftype == 2:
            srate_list, recovery_list, lines = self._deform_decode_1d_table(int(line[3]))
            self.recovery_data['srate'] = srate_list
            self.recovery_data['recovery'] = recovery_list
            self.recovery_data['data_txt'].extend(lines)
            self.recovery_data['ftype_txt'] = "f(strain rate)"
        elif ftype == 3:
            n_temp = int(line[3])
            n_srate = int(line[4])
            temp_list, srate_list, recovery_list, lines = \
                self._deform_decode_2d_table(n_temp, n_srate)
            self.recovery_data['temperature'] = temp_list
            self.recovery_data['srate'] = srate_list
            self.recovery_data['recovery'] = recovery_list
            self.recovery_data['data_txt'].extend(lines)
            self.recovery_data['ftype_txt'] = "f(temperature, strain rate)"

    def _deform_decode_particle_mode(self, line):
        """
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[]
        :param line:
        :return:
        """
        material_num = int(line[1])
        ftype = int(line[2])
        self.particle_mode_data['style'] = "deform"
        self.particle_mode_data['deform_key'] = line[0]
        self.particle_mode_data['material_num'] = material_num
        self.particle_mode_data['ftype'] = ftype
        self.particle_mode_data['data_txt'] = [line]
        if ftype == 0:
            self.particle_mode_data['ftype_txt'] = "No particle size mode model"
        elif ftype == 1:
            self.particle_mode_data['ftype_txt'] = "Spherical particles"
        elif ftype == 2:
            self.particle_mode_data['ftype_txt'] = "Secondary alpha lath"
        elif ftype == 3:
            self.particle_mode_data['ftype_txt'] = "Grain boundary alpha"
        elif ftype == 4:
            self.particle_mode_data['ftype_txt'] = "Side plate alpha"
        elif ftype == 5:
            self.particle_mode_data['ftype_txt'] = "Gamma prime Nickel"

    def _deform_decode_texture(self, line):
        """
        style="",
        deform_key="",
        material_num=int(),
        crystal_type=int(),
        crystal_type_txt="",
        texture_type=int(),
        texture_mesh_type=int(),
        data_txt=[]
        :param line:
        :return:
        """
        material_num = int(line[1])
        crystal_type = int(line[2])
        texture_type = int(line[3])
        texture_mesh_type = int(line[4])
        crystal_type_names = [
            "Not defined",
            "Body Centered Cubic (BCC)",
            "Face Centered Cubic (FCC)",
            "Hexagonal Close Packed (HCP)"
        ]
        bcc_fcc_mesh_names = [
            "",
            "Mesh 1(26 nodes, 36 elements, 7 independent nodes)",
            "Mesh 2(111 nodes, 288 elements, 50 independent nodes)",
            "Mesh 3(605 nodes, 2304 elements, 388 independent nodes)",
            "Mesh 4(3897 nodes, 18432 elements, 3080 independent nodes)"
        ]
        hcp_mesh_names = [
            "",
            "Mesh 1(31 nodes, 56 elements, 10 independent nodes)",
            "Mesh 2(145 nodes, 448 elements, 76 independent nodes)",
            "Mesh 3(849 nodes, 3584 elements, 600 independent nodes)",
            "Mesh 4(5729 nodes, 28672 elements, 4784 independent nodes)"
        ]
        if crystal_type in {1, 2}:
            mesh = bcc_fcc_mesh_names[texture_mesh_type]
        elif crystal_type == 3:
            mesh = hcp_mesh_names[texture_mesh_type]
        else:
            mesh = " no mesh analytical_solution"
        self.texture_data['style'] = "deform"
        self.texture_data['deform_key'] = line[0]
        self.texture_data['material_num'] = material_num
        self.texture_data['crystal_type'] = crystal_type
        self.texture_data['crystal_type_txt'] = crystal_type_names[crystal_type] + " with " + mesh[texture_mesh_type]
        self.texture_data['texture_type'] = texture_type
        self.texture_data['texture_mesh_type'] = texture_mesh_type
        self.texture_data['data_txt'] = [line]

    def _deform_decode_grain_boundary_energy(self, line):
        """
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        temperature=[],
        grain_boundary_energy=[]
        :param line:
        :return:
        """
        material_num = int(line[1])
        ftype = int(line[2])
        self.grain_boundary_energy_data['style'] = "deform"
        self.grain_boundary_energy_data['deform_key'] = line[0]
        self.grain_boundary_energy_data['material_num'] = material_num
        self.grain_boundary_energy_data['ftype'] = ftype
        self.grain_boundary_energy_data['data_txt'] = [line]
        self.grain_boundary_energy_data['temperature'] = []
        self.grain_boundary_energy_data['grain_boundary_energy'] = []
        if ftype == 0:
            value = float(line[3])
            self.grain_boundary_energy_data['grain_boundary_energy'] = [value]
        elif ftype == 1:
            temp_list, grain_boundary_energy_list, lines = self._deform_decode_1d_table(int(line[3]))
            self.grain_boundary_energy_data['temperature'] = temp_list
            self.grain_boundary_energy_data['grain_boundary_energy'] = grain_boundary_energy_list
            self.grain_boundary_energy_data['data_txt'].extend(lines)
            self.grain_boundary_energy_data['ftype_txt'] = "f(temperature)"

    def _deform_decode_grain_boundary_mobility(self, line):
        """
        style="",
        deform_key="",
        material_num=int(),
        data_txt=[],
        coef={},
        :param line:
        :return:
        """
        material_num = int(line[1])
        m0 = float(line[2])
        q = float(line[3])
        self.grain_boundary_mobility_data['style'] = "deform"
        self.grain_boundary_mobility_data['deform_key'] = line[0]
        self.grain_boundary_mobility_data['material_num'] = material_num
        self.grain_boundary_mobility_data['data_txt'] = [line]
        self.grain_boundary_mobility_data['coef']['m0'] = m0
        self.grain_boundary_mobility_data['coef']['q'] = q

    def _deform_decode_nuclei_size(self, line):
        """
        style="",
        deform_key="",
        material_num=int(),
        ftype=int(),
        ftype_txt="",
        data_txt=[],
        temperature=[],
        nuclei_size=[]
        :param line:
        :return:
        """
        material_num = int(line[1])
        ftype = int(line[2])
        self.nuclei_size_data['style'] = "deform"
        self.nuclei_size_data['deform_key'] = line[0]
        self.nuclei_size_data['material_num'] = material_num
        self.nuclei_size_data['ftype'] = ftype
        self.nuclei_size_data['data_txt'] = [line]
        self.nuclei_size_data['temperature'] = []
        self.nuclei_size_data['nuclei_size'] = []
        if ftype == 0:
            value = float(line[3])
            self.nuclei_size_data['nuclei_size'] = [value]
        elif ftype == 1:
            temp_list, nuclei_size_list, lines = self._deform_decode_1d_table(int(line[3]))
            self.nuclei_size_data['temperature'] = temp_list
            self.nuclei_size_data['nuclei_size'] = nuclei_size_list
            self.nuclei_size_data['data_txt'].extend(lines)
            self.nuclei_size_data['ftype_txt'] = "f(temperature)"

    def flow_stress(self, strain, srate, temperature):
        flow_stress_value = None
        style = self.flow_stress_data['style']
        if style == "deform":
            ftype = self.flow_stress_data['ftype']
            if ftype == 1:
                c = self.flow_stress_data['coef']['c']
                n = self.flow_stress_data['coef']['n']
                m = self.flow_stress_data['coef']['m']
                y = self.flow_stress_data['coef']['y']
                flow_stress_value = c * pow(strain, n) * pow(srate, m) + y
            elif ftype == 2:
                strain_min = min(i for i in self.flow_stress_data['strain'] if i > 0)
                if strain < strain_min:
                    flow_stress_value = self._deform_calculate_flow_stress_ftype_3(strain, srate, temperature)
                else:
                    flow_stress_value = self._deform_calculate_flow_stress_ftype_2(strain, srate, temperature)
            elif ftype == 3:
                flow_stress_value = self._deform_calculate_flow_stress_ftype_3(strain, srate, temperature)
        return flow_stress_value

    def _deform_calculate_flow_stress_ftype_2(self, strain, srate, temperature):
        strain_index_to_delete = self.flow_stress_data['strain'].index(0.0)
        srate_log_arr = log(array(self.flow_stress_data['srate'], dtype=float))
        temperature_arr = array(self.flow_stress_data['temperature'], dtype=float)
        if strain_index_to_delete == 0:
            strain_log_arr = log(array(self.flow_stress_data['strain'][1::], dtype=float))
            flow_stress_log_arr = log(np_delete(array(self.flow_stress_data['stress'], dtype=float), 0, axis=2))
        else:
            strain_log_arr = log(array(self.flow_stress_data['strain'], dtype=float))
            flow_stress_log_arr = log(array(self.flow_stress_data['stress'], dtype=float))
        my_interpolating_function = RegularGridInterpolator(
            (temperature_arr, srate_log_arr, strain_log_arr),
            flow_stress_log_arr,
            method='linear',
            bounds_error=False,
            fill_value=None
        )
        point = array([temperature, math.log(srate), math.log(strain)]).T
        return math.exp(float(my_interpolating_function(point)))

    def _deform_calculate_flow_stress_ftype_3(self, strain, srate, temperature):
        strain_arr = array(self.flow_stress_data['strain'], dtype=float)
        srate_arr = array(self.flow_stress_data['srate'], dtype=float)
        temperature_arr = array(self.flow_stress_data['temperature'], dtype=float)
        flow_stress_arr = array(self.flow_stress_data['stress'], dtype=float)
        my_interpolating_function = RegularGridInterpolator(
            (temperature_arr, srate_arr, strain_arr),
            flow_stress_arr,
            method='linear',
            bounds_error=False,
            fill_value=None
        )
        point = array([temperature, srate, strain]).T
        return float(my_interpolating_function(point))

    def young(self, temperature=20, density=1, atom=0):
        young = None
        style = self.young_data['style']
        if style == "deform":
            ftype = self.young_data['ftype']
            if ftype == 0:
                young = self.young_data['young'][0]
            elif ftype == 1:
                young = self._deform_linear_1d_interpolation(
                    self.young_data['temperature'],
                    self.young_data['young'],
                    temperature)
            elif ftype == 2:
                young = self._deform_linear_1d_interpolation(
                    self.young_data['density'],
                    self.young_data['young'],
                    density)
            elif ftype == 3:
                young = self._deform_linear_1d_interpolation(
                    self.young_data['atom'],
                    self.young_data['young'],
                    atom)
            elif ftype == 4:
                young = self._deform_linear_2d_interpolation(
                    self.young_data['temperature'],
                    self.young_data['atom'],
                    self.young_data['young'],
                    temperature,
                    atom)
        return young

    def poison(self, temperature=20, density=1, atom=0):
        poison = None
        style = self.poison_data['style']
        if style == "deform":
            ftype = self.poison_data['ftype']
            if ftype == 0:
                poison = self.poison_data['poison'][0]
            elif ftype == 1:
                poison = self._deform_linear_1d_interpolation(
                    self.poison_data['temperature'],
                    self.poison_data['poison'],
                    temperature)
            elif ftype == 2:
                poison = self._deform_linear_1d_interpolation(
                    self.poison_data['density'],
                    self.poison_data['poison'],
                    density)
            elif ftype == 3:
                poison = self._deform_linear_1d_interpolation(
                    self.poison_data['atom'],
                    self.poison_data['poison'],
                    atom)
            elif ftype == 4:
                poison = self._deform_linear_2d_interpolation(
                    self.poison_data['temperature'],
                    self.poison_data['atom'],
                    self.poison_data['poison'],
                    temperature,
                    atom)
        return poison

    def thermal_expansion(self, temperature=20, density=1, atom=0):
        thermal_expansion = None
        style = self.thermal_expansion_data['style']
        if style == "deform":
            ftype = self.thermal_expansion_data['ftype']
            if ftype == 0:
                thermal_expansion = self.thermal_expansion_data['thermal_expansion'][0]
            elif ftype == 1:
                thermal_expansion = self._deform_linear_1d_interpolation(
                    self.thermal_expansion_data['temperature'],
                    self.thermal_expansion_data['thermal_expansion'],
                    temperature)
            elif ftype == 2:
                thermal_expansion = self._deform_linear_1d_interpolation(
                    self.thermal_expansion_data['density'],
                    self.thermal_expansion_data['thermal_expansion'],
                    density)
            elif ftype == 3:
                thermal_expansion = self._deform_linear_1d_interpolation(
                    self.thermal_expansion_data['atom'],
                    self.thermal_expansion_data['thermal_expansion'],
                    atom)
            elif ftype == 4:
                thermal_expansion = self._deform_linear_2d_interpolation(
                    self.thermal_expansion_data['temperature'],
                    self.thermal_expansion_data['atom'],
                    self.thermal_expansion_data['thermal_expansion'],
                    temperature,
                    atom)
        return thermal_expansion

    def conductivity(self, temperature=20, density=1, atom=0):
        conductivity = None
        style = self.conductivity_data['style']
        if style == "deform":
            ftype = self.conductivity_data['ftype']
            if ftype == 0:
                conductivity = self.conductivity_data['conductivity'][0]
            elif ftype == 1:
                conductivity = self._deform_linear_1d_interpolation(
                    self.conductivity_data['temperature'],
                    self.conductivity_data['conductivity'],
                    temperature)
            elif ftype == 2:
                conductivity = self._deform_linear_1d_interpolation(
                    self.conductivity_data['density'],
                    self.conductivity_data['conductivity'],
                    density)
            elif ftype == 3:
                conductivity = self._deform_linear_1d_interpolation(
                    self.conductivity_data['atom'],
                    self.conductivity_data['conductivity'],
                    atom)
            elif ftype == 4:
                conductivity = self._deform_linear_2d_interpolation(
                    self.conductivity_data['temperature'],
                    self.conductivity_data['atom'],
                    self.conductivity_data['conductivity'],
                    temperature,
                    atom)
        return conductivity

    def heat_capacity(self, temperature=20, density=1, atom=0):
        heat_capacity = None
        style = self.heat_capacity_data['style']
        if style == "deform":
            ftype = self.heat_capacity_data['ftype']
            if ftype == 0:
                heat_capacity = self.heat_capacity_data['heat_capacity'][0]
            elif ftype == 1:
                heat_capacity = self._deform_linear_1d_interpolation(
                    self.heat_capacity_data['temperature'],
                    self.heat_capacity_data['heat_capacity'],
                    temperature)
            elif ftype == 2:
                heat_capacity = self._deform_linear_1d_interpolation(
                    self.heat_capacity_data['density'],
                    self.heat_capacity_data['heat_capacity'],
                    density)
            elif ftype == 3:
                heat_capacity = self._deform_linear_1d_interpolation(
                    self.heat_capacity_data['atom'],
                    self.heat_capacity_data['heat_capacity'],
                    atom)
            elif ftype == 4:
                heat_capacity = self._deform_linear_2d_interpolation(
                    self.heat_capacity_data['temperature'],
                    self.heat_capacity_data['atom'],
                    self.heat_capacity_data['heat_capacity'],
                    temperature,
                    atom)
        return heat_capacity

    def mass_density(self, temperature=20, density=1, atom=0):
        mass_density = None
        style = self.mass_density_data['style']
        if style == "deform":
            # material_num = self.mass_density_data['material_num']
            ftype = self.mass_density_data['ftype']
            if ftype == 0:
                mass_density = self.mass_density_data['mass_density'][0]
            elif ftype == 1:
                mass_density = self._deform_linear_1d_interpolation(
                    self.mass_density_data['temperature'],
                    self.mass_density_data['mass_density'],
                    temperature)
            elif ftype == 2:
                mass_density = self._deform_linear_1d_interpolation(
                    self.mass_density_data['density'],
                    self.mass_density_data['mass_density'],
                    density)
            elif ftype == 3:
                mass_density = self._deform_linear_1d_interpolation(
                    self.mass_density_data['atom'],
                    self.mass_density_data['mass_density'],
                    atom)
        return mass_density

    def alpha_coarsening(self, temperature=950, srate=0.02):
        alpha_coarsening = None
        style = self.alpha_coarsening_data['style']
        if style == "deform":
            coarsening_type = self.alpha_coarsening_data['coarsening_type']
            ftype = self.alpha_coarsening_data['ftype']
            if coarsening_type == 0:
                alpha_coarsening = None
            elif alpha_coarsening == 1:
                if ftype == 0:
                    alpha_coarsening = self.alpha_coarsening_data['alpha_coarsening'][0]
                elif ftype == 5:
                    alpha_coarsening = self._deform_linear_2d_interpolation(
                        self.alpha_coarsening_data['temperature'],
                        self.alpha_coarsening_data['srate'],
                        self.alpha_coarsening_data['alpha_coarsening'],
                        temperature,
                        srate)
        return alpha_coarsening

    def diffusion_bonding(self, temperature=950, pressure=0.02):
        diffusion_bonding_time = None
        style = self.diffusion_bonding_data['style']
        if style == "deform":
            ftype = self.diffusion_bonding_data['ftype']
            if ftype == 0:
                diffusion_bonding_time = self.diffusion_bonding_data['time'][0]
            elif ftype == 7:
                diffusion_bonding_time = self._deform_linear_2d_interpolation(
                    self.diffusion_bonding_data['temperature'],
                    self.diffusion_bonding_data['pressure'],
                    self.diffusion_bonding_data['time'],
                    temperature,
                    pressure)
        return diffusion_bonding_time

    def emissivity(self, temperature=20):
        emissivity = None
        style = self.emissivity_data['style']
        if style == "deform":
            ftype = self.emissivity_data['ftype']
            if ftype == 0:
                emissivity = self.emissivity_data['emissivity'][0]
            elif ftype == 1:
                emissivity = self._deform_linear_1d_interpolation(
                    self.emissivity_data['temperature'],
                    self.emissivity_data['emissivity'],
                    temperature)
        return emissivity

    def hardness(self, temperature=20, density=1, atom=0):
        hardness = None
        style = self.hardness_data['style']
        if style == "deform":
            ftype = self.hardness_data['ftype']
            if ftype == 0:
                hardness = self.hardness_data['hardness'][0]
            elif ftype == 1:
                hardness = self._deform_linear_1d_interpolation(
                    self.hardness_data['temperature'],
                    self.hardness_data['hardness'],
                    temperature)
            elif ftype == 2:
                hardness = self._deform_linear_1d_interpolation(
                    self.hardness_data['density'],
                    self.hardness_data['hardness'],
                    density)
            elif ftype == 3:
                hardness = self._deform_linear_1d_interpolation(
                    self.hardness_data['atom'],
                    self.hardness_data['hardness'],
                    atom)
            elif ftype == 4:
                hardness = self._deform_linear_2d_interpolation(
                    self.hardness_data['temperature'],
                    self.hardness_data['atom'],
                    self.hardness_data['hardness'],
                    temperature,
                    atom)
        return hardness

    def mixture_material(self):
        """
        style="",
        deform_key="",
        material_num=int(),
        is_mixture=bool(),
        data_txt=[],
        dependent_phases=[]
        """
        is_mixture = False
        dependent_phases = []
        style = self.mixture_material_data['style']
        if style == "deform":
            is_mixture = self.mixture_material_data['is_mixture']
            if is_mixture:
                dependent_phases = self.mixture_material_data['dependent_phases']
        return is_mixture, dependent_phases

    def creep(
            self,
            temperature=None,
            strain=None,
            stress=None,
            time=None,
            srate=None,
            grain_size=None,
            precipitate_size=None,
            precipitate_shape=None,
            precipitate_volume_fraction=None
    ):  # sourcery skip: extract-method, switch
        creep_value = None
        style = self.creep_data['style']
        if style == "deform":
            ftype = self.creep_data['ftype']
            if ftype == 1:
                # Model: Prezyna model
                # Input: temperature, strain, srate, stress
                gamma = self._deform_linear_1d_interpolation(
                    self.creep_data['temperature'],
                    self.creep_data['coef']['gamma'],
                    temperature
                )
                m = self._deform_linear_1d_interpolation(
                    self.creep_data['temperature'],
                    self.creep_data['coef']['m'],
                    temperature
                )
                flow_stress = self.flow_stress(strain=strain, srate=srate, temperature=temperature)
                creep_value = gamma * pow((stress / flow_stress - 1), m)
            elif ftype == 2:
                # Model: Power law without yielding
                # Input: temperature, strain, srate, stress
                gamma = self._deform_linear_1d_interpolation(
                    self.creep_data['temperature'],
                    self.creep_data['coef']['gamma'],
                    temperature
                )
                m = self._deform_linear_1d_interpolation(
                    self.creep_data['temperature'],
                    self.creep_data['coef']['m'],
                    temperature
                )
                flow_stress = self.flow_stress(strain=strain, srate=srate, temperature=temperature)
                creep_value = gamma * pow(stress / flow_stress, m)
            elif ftype == 3:
                # Model: Baily-Norton model
                # Input: temperature, stress, time
                k = self._deform_linear_1d_interpolation(
                    self.creep_data['temperature'], self.creep_data['coef']['k'], temperature)
                n = self._deform_linear_1d_interpolation(
                    self.creep_data['temperature'], self.creep_data['coef']['n'], temperature)
                m = self._deform_linear_1d_interpolation(
                    self.creep_data['temperature'], self.creep_data['coef']['m'], temperature)
                q = self._deform_linear_1d_interpolation(
                    self.creep_data['temperature'], self.creep_data['coef']['q'], temperature)
                r = self._deform_linear_1d_interpolation(
                    self.creep_data['temperature'], self.creep_data['coef']['r'], temperature)
                creep_value = k * m * pow(stress, n) * pow(time, m - 1) + q * pow(stress, r)
            elif ftype == 4:
                # Model: Soderberg model
                # Input: temperature, stress, time
                k = self._deform_linear_1d_interpolation(
                    self.creep_data['temperature'], self.creep_data['coef']['k'], temperature)
                n = self._deform_linear_1d_interpolation(
                    self.creep_data['temperature'], self.creep_data['coef']['n'], temperature)
                c = self._deform_linear_1d_interpolation(
                    self.creep_data['temperature'], self.creep_data['coef']['c'], temperature)
                creep_value = k * pow(stress, n) * math.exp(-c / (temperature + 273.15))
            elif ftype == 5:
                creep_value = self._deform_linear_3d_interpolation(
                    self.flow_stress_data['temperature'],
                    self.flow_stress_data['stress'],
                    self.flow_stress_data['strain'],
                    self.flow_stress_data['creep'],
                    temperature,
                    stress,
                    strain
                )
            elif ftype == 6:
                creep_value = self._deform_linear_3d_interpolation(
                    self.flow_stress_data['temperature'],
                    self.flow_stress_data['stress'],
                    self.flow_stress_data['time'],
                    self.flow_stress_data['creep'],
                    temperature,
                    stress,
                    time
                )
            elif ftype == 7:
                variables_order = self.creep_data['coef']['variables_order']
                variables_arr = tuple(array(x, dtype=float) for x in self.creep_data['coef']['variables_list'])
                creep_arr = array(self.creep_data['creep'], dtype=float)
                my_interpolating_function = RegularGridInterpolator(
                    variables_arr,
                    creep_arr,
                    method='linear',
                    bounds_error=False,
                    fill_value=None
                )
                point_coordinates = []
                for variable in variables_order:
                    if variable == "temperature":
                        point_coordinates.append(temperature)
                    elif variable == "strain":
                        point_coordinates.append(strain)
                    elif variable == "stress":
                        point_coordinates.append(stress)
                    elif variable == "time":
                        point_coordinates.append(time)
                    elif variable == "srate":
                        point_coordinates.append(srate)
                    elif variable == "grain_size":
                        point_coordinates.append(grain_size)
                    elif variable == "precipitate_size":
                        point_coordinates.append(precipitate_size)
                    elif variable == "precipitate_shape":
                        point_coordinates.append(precipitate_shape)
                    elif variable == "precipitate_volume_fraction":
                        point_coordinates.append(precipitate_volume_fraction)
                point = array(point_coordinates).T
                creep_value = float(my_interpolating_function(point))
        return creep_value

    def carburization(self, temperature=None, atom=None):
        carburization = None
        style = self.carburization_data['style']
        if style == "deform":
            ftype = self.carburization_data['ftype']
            if ftype == 0:
                carburization = self.carburization_data['carburization'][0]
            elif ftype == 1:
                carburization = self._deform_linear_2d_interpolation(
                    self.carburization_data['temperature'],
                    self.carburization_data['atom'],
                    self.carburization_data['carburization'],
                    temperature,
                    atom)
            elif ftype == 2:
                c1 = self._deform_linear_1d_interpolation(
                    self.creep_data['temperature'],
                    self.creep_data['coef']['c1'],
                    temperature
                )
                c2 = self._deform_linear_1d_interpolation(
                    self.creep_data['temperature'],
                    self.creep_data['coef']['c2'],
                    temperature
                )
                carburization = c1 * math.exp(c2 * atom)
            elif ftype == 3:
                c1 = self._deform_linear_1d_interpolation(
                    self.creep_data['atom'],
                    self.creep_data['coef']['c1'],
                    temperature
                )
                c2 = self._deform_linear_1d_interpolation(
                    self.creep_data['atom'],
                    self.creep_data['coef']['c2'],
                    temperature
                )
                carburization = c1 * math.exp(c2 * temperature)
        return carburization

    def resistivity(self, temperature=None, density=None):
        resistivity = None
        style = self.resistivity_data['style']
        if style == "deform":
            ftype = self.resistivity_data['ftype']
            if ftype == 0:
                resistivity = self.resistivity_data['resistivity'][0]
            elif ftype == 1:
                resistivity = self._deform_linear_1d_interpolation(
                    self.resistivity_data['temperature'],
                    self.resistivity_data['resistivity'],
                    temperature)
            elif ftype == 2:
                resistivity = self._deform_linear_1d_interpolation(
                    self.resistivity_data['density'],
                    self.resistivity_data['resistivity'],
                    density)
        return resistivity

    def ultimate_strength(self, temperature=None):
        ultimate_strength = None
        style = self.ultimate_strength_data['style']
        if style == "deform":
            ftype = self.ultimate_strength_data['ftype']
            if ftype == 0:
                ultimate_strength = self.ultimate_strength_data['ultimate_strength'][0]
            elif ftype == 1:
                ultimate_strength = self._deform_linear_1d_interpolation(
                    self.ultimate_strength_data['temperature'],
                    self.ultimate_strength_data['ultimate_strength'],
                    temperature)
        return ultimate_strength

    def hardening_rule(self):
        style = self.hardening_rule_data['style']
        if style == "deform":
            return self.hardening_rule_data['ftype_txt']
        else:
            return None

    def magnetic_permeability(self, temperature=None, density=None, magnetic_intensity=None):
        magnetic_permeability = None
        style = self.magnetic_permeability_data['style']
        if style == "deform":
            ftype = self.magnetic_permeability_data['ftype']
            if ftype == 0:
                magnetic_permeability = self.magnetic_permeability_data['magnetic_permeability'][0]
            elif ftype == 1:
                magnetic_permeability = self._deform_linear_1d_interpolation(
                    self.magnetic_permeability_data['temperature'],
                    self.magnetic_permeability_data['magnetic_permeability'],
                    temperature)
            elif ftype == 2:
                magnetic_permeability = self._deform_linear_1d_interpolation(
                    self.magnetic_permeability_data['density'],
                    self.magnetic_permeability_data['magnetic_permeability'],
                    density)
            elif ftype == 4:
                magnetic_permeability = self._deform_linear_2d_interpolation(
                    self.magnetic_permeability_data['temperature'],
                    self.magnetic_permeability_data['magnetic_intensity'],
                    self.magnetic_permeability_data['magnetic_permeability'],
                    temperature,
                    magnetic_intensity)
        return magnetic_permeability

    def magnetic_permitivity(self, temperature=None, density=None):
        magnetic_permitivity = None
        style = self.magnetic_permitivity_data['style']
        if style == "deform":
            ftype = self.magnetic_permitivity_data['ftype']
            if ftype == 0:
                magnetic_permitivity = self.magnetic_permitivity_data['magnetic_permitivity'][0]
            elif ftype == 1:
                magnetic_permitivity = self._deform_linear_1d_interpolation(
                    self.magnetic_permitivity_data['temperature'],
                    self.magnetic_permitivity_data['magnetic_permitivity'],
                    temperature)
            elif ftype == 2:
                magnetic_permitivity = self._deform_linear_1d_interpolation(
                    self.magnetic_permitivity_data['density'],
                    self.magnetic_permitivity_data['magnetic_permitivity'],
                    density)
        return magnetic_permitivity

    def burgers(self, temperature=None, stress=None, concentration=None):
        burgers = None
        style = self.burgers_data['style']
        if style == "deform":
            ftype = self.burgers_data['ftype']
            if ftype == 0:
                burgers = self.burgers_data['burgers'][0]
            elif ftype == 1:
                burgers = self._deform_linear_1d_interpolation(
                    self.burgers_data['temperature'],
                    self.burgers_data['burgers'],
                    temperature)
            elif ftype == 2:
                burgers = self._deform_linear_1d_interpolation(
                    self.burgers_data['stress'],
                    self.burgers_data['burgers'],
                    stress)
            elif ftype == 3:
                burgers = self._deform_linear_1d_interpolation(
                    self.burgers_data['concentration'],
                    self.burgers_data['burgers'],
                    concentration)
            elif ftype == 4:
                burgers = self._deform_linear_2d_interpolation(
                    self.burgers_data['temperature'],
                    self.burgers_data['stress'],
                    self.burgers_data['burgers'],
                    temperature,
                    stress)
            elif ftype == 5:
                burgers = self._deform_linear_2d_interpolation(
                    self.burgers_data['temperature'],
                    self.burgers_data['concentration'],
                    self.burgers_data['burgers'],
                    temperature,
                    concentration)
            elif ftype == 6:
                burgers = self._deform_linear_2d_interpolation(
                    self.burgers_data['stress'],
                    self.burgers_data['concentration'],
                    self.burgers_data['burgers'],
                    stress,
                    concentration)
            elif ftype == 7:
                burgers = self._deform_linear_3d_interpolation(
                    self.burgers_data['temperature'],
                    self.burgers_data['stress'],
                    self.burgers_data['concentration'],
                    self.burgers_data['burgers'],
                    temperature,
                    stress,
                    concentration
                )
        return burgers

    def dislocation_alpha(self, temperature=None, srate=None):
        dislocation_alpha = None
        style = self.dislocation_alpha_data['style']
        if style == "deform":
            ftype = self.dislocation_alpha_data['ftype']
            if ftype == 0:
                dislocation_alpha = self.dislocation_alpha_data['dislocation_alpha'][0]
            elif ftype == 1:
                dislocation_alpha = self._deform_linear_1d_interpolation(
                    self.dislocation_alpha_data['temperature'],
                    self.dislocation_alpha_data['dislocation_alpha'],
                    temperature)
            elif ftype == 2:
                dislocation_alpha = self._deform_linear_1d_interpolation(
                    self.dislocation_alpha_data['srate'],
                    self.dislocation_alpha_data['dislocation_alpha'],
                    srate)
            elif ftype == 3:
                dislocation_alpha = self._deform_linear_2d_interpolation(
                    self.dislocation_alpha_data['temperature'],
                    self.dislocation_alpha_data['srate'],
                    self.dislocation_alpha_data['dislocation_alpha'],
                    temperature,
                    srate)
        return dislocation_alpha

    def dislocations_number(self, temperature=None, srate=None):
        dislocations_number = None
        style = self.dislocations_number_data['style']
        if style == "deform":
            ftype = self.dislocations_number_data['ftype']
            if ftype == 0:
                dislocations_number = self.dislocations_number_data['dislocations_number'][0]
            elif ftype == 1:
                dislocations_number = self._deform_linear_1d_interpolation(
                    self.dislocations_number_data['temperature'],
                    self.dislocations_number_data['dislocations_number'],
                    temperature)
            elif ftype == 2:
                dislocations_number = self._deform_linear_1d_interpolation(
                    self.dislocations_number_data['srate'],
                    self.dislocations_number_data['dislocations_number'],
                    srate)
            elif ftype == 3:
                dislocations_number = self._deform_linear_2d_interpolation(
                    self.dislocations_number_data['temperature'],
                    self.dislocations_number_data['srate'],
                    self.dislocations_number_data['dislocations_number'],
                    temperature,
                    srate)
        return dislocations_number

    def recovery(self, temperature=None, srate=None):
        recovery = None
        style = self.recovery_data['style']
        if style == "deform":
            ftype = self.recovery_data['ftype']
            if ftype == 0:
                recovery = self.recovery_data['recovery'][0]
            elif ftype == 1:
                recovery = self._deform_linear_1d_interpolation(
                    self.recovery_data['temperature'],
                    self.recovery_data['recovery'],
                    temperature)
            elif ftype == 2:
                recovery = self._deform_linear_1d_interpolation(
                    self.recovery_data['srate'],
                    self.recovery_data['recovery'],
                    srate)
            elif ftype == 3:
                recovery = self._deform_linear_2d_interpolation(
                    self.recovery_data['temperature'],
                    self.recovery_data['srate'],
                    self.recovery_data['recovery'],
                    temperature,
                    srate)
        return recovery

    def particle_mode(self):
        style = self.particle_mode_data['style']
        if style == "deform":
            return self.particle_mode_data['ftype_txt']
        else:
            return None

    def texture(self):
        style = self.texture_data['style']
        if style == "deform":
            return self.texture_data['crystal_type_txt']
        else:
            return None

    def grain_boundary_energy(self, temperature=None):
        grain_boundary_energy = None
        style = self.grain_boundary_energy_data['style']
        if style == "deform":
            ftype = self.grain_boundary_energy_data['ftype']
            if ftype == 0:
                grain_boundary_energy = self.grain_boundary_energy_data['grain_boundary_energy'][0]
            elif ftype == 1:
                grain_boundary_energy = self._deform_linear_1d_interpolation(
                    self.grain_boundary_energy_data['temperature'],
                    self.grain_boundary_energy_data['grain_boundary_energy'],
                    temperature)
        return grain_boundary_energy

    def grain_boundary_mobility(self, temperature=None):
        grain_boundary_mobility = None
        style = self.grain_boundary_mobility_data['style']
        if style == "deform":
            m0 = self.grain_boundary_mobility_data['coef']['m0']
            q = self.grain_boundary_mobility_data['coef']['q']
            universal_gas_constant = 8.3144e+03  # (N-mm/g-mole/K)
            grain_boundary_mobility = m0 * math.exp(-q / (universal_gas_constant * temperature))
        return grain_boundary_mobility

    def nuclei_size(self, temperature=None):
        nuclei_size = None
        style = self.nuclei_size_data['style']
        if style == "deform":
            ftype = self.nuclei_size_data['ftype']
            if ftype == 0:
                nuclei_size = self.nuclei_size_data['nuclei_size'][0]
            elif ftype == 1:
                nuclei_size = self._deform_linear_1d_interpolation(
                    self.nuclei_size_data['temperature'],
                    self.nuclei_size_data['nuclei_size'],
                    temperature)
        return nuclei_size

    def _deform_decode_coef_table_1d(self, n_data, is_integer):
        is_integer: bool
        table = []
        lines = []
        for _ in range(n_data):
            line = self._lines.pop(0).strip().split()
            values = [int(x) for x in line] if is_integer else [float(x) for x in line]
            lines.append(line)
            table.append(values)
        self.creep_data['data_txt'].extend(lines)
        return table

    def _deform_decode_1d_table(self, n_rows):
        values_1 = []
        values_2 = []
        lines = []
        for _ in range(n_rows):
            line = self._lines.pop(0).strip().split()
            v_1, v_2 = map(float, list(line))
            values_1.append(v_1)
            values_2.append(v_2)
            lines.append(line)
        return values_1, values_2, lines

    def _deform_decode_1dxn_table(self, n_rows):
        values = []
        lines = []
        for _ in range(n_rows):
            line = self._lines.pop(0).strip().split()
            values.append([float(x) for x in line])
            lines.append(line)
        transposed = self.transpose1(values)
        return transposed, lines

    def _deform_decode_2d_table(self, n_1, n_2):
        lines = []
        n_values_total = n_2 + n_1 + n_2 * n_1
        n_current = 0
        values_final = []
        while n_current < n_values_total:
            next_line = self._lines.pop(0).strip().split()
            lines.append(next_line)
            values_of_new_line = [float(x) for x in next_line]
            values_final.extend(values_of_new_line)
            n_current = len(values_final)
        n1_list = [values_final.pop(0) for _ in range(n_1)]
        n2_list = [values_final.pop(0) for _ in range(n_2)]
        size = (n_1, n_2)
        values_list = list(reduce(lambda x, y: map(tuple, zip(*y * (x,))), (iter(values_final), *size[:0:-1])))
        return n1_list, n2_list, values_list, lines

    def _deform_decode_3d_table(self):
        second_line = self._lines.pop(0).strip().split()
        lines = [second_line]
        n_1, n_2, n_3 = map(int, second_line)
        n_values_total = n_1 + n_2 + n_3 + n_1 * n_2 * n_3
        n_current = 0
        values_final = []
        while n_current < n_values_total:
            next_line = self._lines.pop(0).strip().split()
            lines.append(next_line)
            values = [float(x) for x in next_line]
            values_final.extend(values)
            n_current = len(values_final)
        list_x = [values_final.pop(0) for _ in range(n_1)]
        list_y = [values_final.pop(0) for _ in range(n_2)]
        list_z = [values_final.pop(0) for _ in range(n_3)]
        size = (n_3, n_2, n_1)
        values_list = list(reduce(lambda x, y: map(tuple, zip(*y * (x,))), (iter(values_final), *size[:0:-1])))
        return list_x, list_y, list_z, values_list, lines

    @staticmethod
    def _deform_linear_1d_interpolation(x_list, y_list, x_point):
        my_interpolating_function = interp1d(
            array(x_list),
            array(y_list),
            kind='linear',
            axis=- 1,
            copy=False,
            bounds_error=None,
            fill_value="extrapolate",
            assume_sorted=True
        )
        point = array([x_point])
        return float(my_interpolating_function(point))

    @staticmethod
    def _deform_linear_2d_interpolation(x_list, y_list, z_list, x_point, y_point):
        my_interpolating_function = RegularGridInterpolator(
            (array(x_list), array(y_list)),
            array(z_list),
            method='linear',
            bounds_error=False,
            fill_value=None
        )
        point = array([x_point, y_point]).T
        return float(my_interpolating_function(point))

    @staticmethod
    def _deform_linear_3d_interpolation(x_list, y_list, z_list, xyz_list, x_point, y_point, z_point):
        my_interpolating_function = RegularGridInterpolator(
            (array(x_list, dtype=float), array(y_list, dtype=float), array(z_list, dtype=float)),
            array(xyz_list, dtype=float),
            method='linear',
            bounds_error=False,
            fill_value=None
        )
        point = array([x_point, y_point, z_point]).T
        return float(my_interpolating_function(point))

    @staticmethod
    def transpose1(lst):
        new_list = []
        for i in range(len(lst)):
            vector = [lst[j][i] for j in range(len(lst))]
            new_list.append(vector)
        return new_list

    @staticmethod
    def transpose2(matrix):
        rows = len(matrix)
        cols = len(matrix[0])
        transposed = []
        while len(transposed) < cols:
            transposed.append([])
            while len(transposed[-1]) < rows:
                transposed[-1].append(0)
        for i in range(rows):
            for j in range(cols):
                transposed[j][i] = matrix[i][j]
        return transposed
