import json
import math

from forgelab.sql_setup.insert_or_update_table_from_library import query_insert_or_update_records_from_library
from forgelab.sql_setup.library_dictionary import library


DIE_TYPE_ID_BY_NAME = {
    "flat": 1,
    "v_die": 2,
    "gfm_die": 3,
    "rounding": 4,
    "knife": 5,
}


DIE_TYPE_ROWS = (
    (1, {"EN": "Flat die", "RU": "Плоский боёк", "ZH_HANS": "平砧"}),
    (2, {"EN": "V-die", "RU": "V-образный боёк", "ZH_HANS": "V形砧"}),
    (3, {"EN": "GFM die", "RU": "Боёк GFM", "ZH_HANS": "GFM砧"}),
    (4, {"EN": "Rounding die", "RU": "Радиусный боёк", "ZH_HANS": "圆角砧"}),
    (5, {"EN": "Knife die", "RU": "Ножевой боёк", "ZH_HANS": "刀形砧"}),
)


def _die_type_to_id(value) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value in DIE_TYPE_ID_BY_NAME:
        return DIE_TYPE_ID_BY_NAME[value]
    raise ValueError(f"Unsupported die_type value: {value}")


def _record_die_type_id(record: dict) -> int:
    if "die_type_id" in record:
        return _die_type_to_id(record["die_type_id"])
    if "die_type" in record:
        return _die_type_to_id(record["die_type"])
    raise KeyError("Record is missing both 'die_type_id' and legacy 'die_type' keys")


def _normalize_library_die_types():
    for table_name in ("die", "die_assembly"):
        for record in library.get(table_name, []):
            record["die_type_id"] = _record_die_type_id(record)
            record.pop("die_type", None)


def upsert_die_type_records(cur):
    cur.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_name = 'die_types'
        LIMIT 1;
        """
    )
    if not cur.fetchone():
        return

    for die_type_id, die_type_name in DIE_TYPE_ROWS:
        cur.execute(
            """
            INSERT INTO die_types (id, name)
            VALUES (%s, %s::json)
            ON CONFLICT (id) DO UPDATE
            SET name = EXCLUDED.name;
            """,
            (die_type_id, json.dumps(die_type_name, ensure_ascii=False)),
        )

    cur.execute(
        """
        SELECT setval(
            pg_get_serial_sequence('die_types', 'id'),
            (SELECT COALESCE(MAX(id), 1) FROM die_types),
            TRUE
        );
        """
    )


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


def _normalize_name_key(value):
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _parse_json_text(value):
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except Exception:
        return value


def upsert_die_assembly_records_from_library(cur):
    cur.execute("SELECT id, name::text, die_type_id FROM die_assemblies;")
    result = cur.fetchall()
    sql_assembly_id_by_key = {
        (_normalize_name_key(_parse_json_text(name_text)), die_type_id): die_assembly_id
        for die_assembly_id, name_text, die_type_id in result
    } if result else {}

    update_sql = (
        "UPDATE die_assemblies "
        "SET name = %s::json, die_type_id = %s, is_obsolete = %s, updated_at = NOW() "
        "WHERE id = %s;"
    )
    insert_sql = (
        "INSERT INTO die_assemblies (name, die_type_id, is_obsolete) "
        "VALUES (%s::json, %s, %s);"
    )

    processed_keys = set()
    for die_assembly in library['die_assembly']:
        die_type_id = _record_die_type_id(die_assembly)
        key = (_normalize_name_key(die_assembly['name']), die_type_id)
        if key in processed_keys:
            continue
        processed_keys.add(key)

        values = (
            json.dumps(die_assembly['name'], ensure_ascii=False),
            die_type_id,
            bool(die_assembly.get('is_obsolete', False)),
        )
        die_assembly_id = sql_assembly_id_by_key.get(key)
        if die_assembly_id is None:
            cur.execute(insert_sql, values)
            continue
        cur.execute(update_sql, values + (die_assembly_id,))


def update_die_set_die_assembly_id(cur):
    cur.execute("SELECT id, name::text, die_type_id FROM die_assemblies;")
    result = cur.fetchall()
    sql_assembly_id_by_key = {
        (_normalize_name_key(_parse_json_text(name_text)), die_type_id): die_assembly_id
        for die_assembly_id, name_text, die_type_id in result
    } if result else {}

    lib_assembly_key_by_code = {}
    for die_assembly in library['die_assembly']:
        code = die_assembly.get('die_assembly_name')
        if not code or code in lib_assembly_key_by_code:
            continue
        lib_assembly_key_by_code[code] = (
            _normalize_name_key(die_assembly['name']),
            _record_die_type_id(die_assembly),
        )

    for die in library['die']:
        die_assembly_code = die.get('die_assembly_name')
        assembly_key = lib_assembly_key_by_code.get(die_assembly_code)
        if assembly_key is None:
            continue
        die_assembly_id = sql_assembly_id_by_key.get(assembly_key)
        if die_assembly_id is None:
            continue
        cur.execute("UPDATE dies SET die_assembly_id = %s, updated_at = NOW() WHERE die_template_file_name = %s;",
                    (die_assembly_id, die['die_template_file_name']))


def insert_die_records_from_library(cur):
    _normalize_library_die_types()
    upsert_die_type_records(cur)
    _extend_die_parameters(library['die'])
    upsert_die_assembly_records_from_library(cur)

    query_insert_or_update_records_from_library(cur,
                                                table_name='dies',
                                                library_key='die',
                                                column_name_of_unique_name='die_template_file_name',
                                                exclude_columns=[],
                                                is_convert_dict_to_json_str=True,
                                                json_columns=['name'])
    update_die_set_die_assembly_id(cur)
