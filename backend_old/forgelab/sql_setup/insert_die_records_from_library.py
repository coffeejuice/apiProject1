import math

from forgelab.sql_setup.insert_or_update_table_from_library import query_insert_or_update_records_from_library
from forgelab.sql_setup.library_dictionary import library


def _extend_die_parameters(input_die_parameters: list):  # -> list:

    output_die_parameters = []
    for input_die in input_die_parameters:

        if 'empty_record' in input_die['die_name']:
            continue

        # ================================== DIE PARAMETERS ==========================================

        dim = input_die['dimensions'].copy()
        edge_radius = dim['edge_radius']
        edge_angle = dim['edge_angle']  # Degrees
        edge_angle_radians = math.radians(edge_angle)
        straight_length = dim['straight_length']

        assert edge_radius > 0.0, f"ValueError: 'edge_radius' should be positive, but it is = {edge_radius}"
        assert 0.0 <= edge_angle <= 90.0, f"ValueError: 'edge_angle' should be positive within 0 ... 90 degrees, but it is = {edge_angle}"

        theoretical_total_length = 2 * edge_radius + straight_length
        if theoretical_total_length == dim['total_length']:
            assert edge_angle == 90.0, f"ValueError: Impossible geometry of die where die has no slopes (slope angle == 90) and total die length ({dim['total_length']}) is not equal to the sum of radii and straight length (2 * R{edge_radius} + {straight_length}) = {theoretical_total_length}"
        if theoretical_total_length < dim['total_length']:
            assert edge_angle < 90.0, f"ValueError: Impossible geometry of die where die has no slopes (slope angle >= 90), but total die length ({dim['total_length']}) is bigger than the sum of radii and straight length (2 * R{edge_radius} + {straight_length}) = {theoretical_total_length}"

        # Total Length of curved part of die (die radius + die slope)
        curved_length = 0.5 * (dim['total_length'] - dim['straight_length'])

        is_have_slope = False

        if edge_angle == 90.0 and theoretical_total_length == dim['total_length']:  # Old style dies (rounded edges)
            radius_height = edge_radius
            radius_length = edge_radius
            curved_height = edge_radius

        else:  # radius_value > curved_l
            theoretical_radius_length = edge_radius * math.sin(edge_angle_radians)
            is_have_slope = theoretical_radius_length < curved_length

            if is_have_slope:  # Die has slope
                radius_length = edge_radius * math.sin(edge_angle_radians)
                radius_height = edge_radius * (1 - math.cos(edge_angle_radians))
                slope_height = (curved_length - radius_length) * math.tan(edge_angle_radians)
                curved_height = radius_height + slope_height

            else:  # Die does not have slope, but only radius
                max_edge_angle_radians = math.asin(curved_length / edge_radius)  # in case there is no slope, but only radius
                max_edge_angle = math.degrees(max_edge_angle_radians)
                radius_height = edge_radius * (1 - math.cos(max_edge_angle_radians))
                radius_length = curved_length
                curved_height = radius_height
                dim['edge_angle'] = max_edge_angle

        dim['radius_height'] = radius_height
        dim['radius_length'] = radius_length
        dim['curved_height'] = curved_height
        dim['curved_length'] = curved_length
        dim['is_have_slope'] = is_have_slope

        input_die['dimensions'] = dim
        # output_die_parameters.append(dim)

    # return output_die_parameters


def update_die_set_die_assembly_id(cur):
    cur.execute("SELECT die_assembly_name, id FROM die_assembly;")
    sql_die_assembly = cur.fetchall()
    if sql_die_assembly:
        for die in library['die']:
            for die_assembly_name, die_assembly_id in sql_die_assembly:
                if die['die_assembly_name'] == die_assembly_name:
                    cur.execute("UPDATE die SET die_assembly_id = %s, updated_at = NOW() WHERE die_name = %s;",
                                (die_assembly_id, die['die_name']))


def insert_die_records_from_library(cur):
    _extend_die_parameters(library['die'])
    query_insert_or_update_records_from_library(cur,
                                                table_name='die_assembly',
                                                column_name_of_unique_name='die_assembly_name',
                                                exclude_columns=[],
                                                is_convert_dict_to_json_str=True)

    query_insert_or_update_records_from_library(cur,
                                                table_name='die',
                                                column_name_of_unique_name='die_name',
                                                exclude_columns=[],
                                                is_convert_dict_to_json_str=True)
    update_die_set_die_assembly_id(cur)
