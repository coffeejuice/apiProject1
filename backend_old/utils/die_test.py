import math


def _extend_die_parameters(input_die_parameters: dict) -> dict:

    output_die_parameters = {}
    for _id, input_die in input_die_parameters.items():

        # ================================== DIE PARAMETERS ==========================================

        die = input_die.copy()
        edge_radius = die['edge_radius']
        edge_angle = die['edge_angle']  # Degrees
        edge_angle_radians = math.radians(edge_angle)
        straight_length = die['straight_length']

        assert edge_radius > 0.0, f"ValueError: 'edge_radius' should be positive, but it is = {edge_radius}"
        assert 0.0 <= edge_angle <= 90.0, f"ValueError: 'edge_angle' should be positive within 0 ... 90 degrees, but it is = {edge_angle}"

        theoretical_total_length = 2 * edge_radius + straight_length
        if theoretical_total_length == die['total_length']:
            assert edge_angle == 90.0, f"ValueError: Impossible geometry of die where die has no slopes (slope angle == 90) and total die length ({die['total_length']}) is not equal to the sum of radii and straight length (2 * R{edge_radius} + {straight_length}) = {theoretical_total_length}"
        if theoretical_total_length < die['total_length']:
            assert edge_angle < 90.0, f"ValueError: Impossible geometry of die where die has no slopes (slope angle >= 90), but total die length ({die['total_length']}) is bigger than the sum of radii and straight length (2 * R{edge_radius} + {straight_length}) = {theoretical_total_length}"

        # Total Length of curved part of die (die radius + die slope)
        curved_length = 0.5 * (die['total_length'] - die['straight_length'])

        is_have_slope = False

        if edge_angle == 90.0 and theoretical_total_length == die['total_length']:  # Old style dies (rounded edges)
            radius_height = edge_radius
            radius_length = edge_radius
            curved_height = edge_radius

        else:  # radius_value > curved_l
            max_edge_angle_radians = math.asin(
                curved_length / edge_radius)  # in case there is no slope, but only radius
            max_edge_angle = math.degrees(max_edge_angle_radians)

            if edge_angle >= max_edge_angle:  # Die does not have slope, but only radius
                die['edge_angle'] = max_edge_angle
                radius_height = edge_radius * (1 - math.cos(max_edge_angle_radians))
                radius_length = curved_length
                curved_height = radius_height

            else:  # Die has slope
                is_have_slope = True
                radius_length = edge_radius * math.sin(edge_angle_radians)
                radius_height = edge_radius * (1 - math.cos(edge_angle_radians))
                slope_height = (curved_length - radius_length) * math.tan(edge_angle_radians)
                curved_height = radius_height + slope_height


        die['radius_height'] = radius_height
        die['radius_length'] = radius_length
        die['curved_height'] = curved_height
        die['curved_length'] = curved_length
        die['is_have_slope'] = is_have_slope

        output_die_parameters[_id] = die

    return output_die_parameters


def _calculate_radius_contact_length(dies: dict, die_ids: list, total_penetration: float, at_relative_penetration_percent: float = 100.0) -> tuple[int, float]:

    """
    """
    assert total_penetration >= 0.0, f"ValueError: 'penetration' should be positive or zero, but it is = {total_penetration}"
    assert 0.0 <= at_relative_penetration_percent <= 100.0, f"ValueError: 'one_side_relative_penetration' should be within 0.0 ... 1.0 range, but it is = {at_relative_penetration_percent}"

    if total_penetration == 0.0 or at_relative_penetration_percent == 0.0:
        return 0, 0.0

    # assert absolute_one_side_penetration >= 0.0, f"ValueError: 'absolute_one_side_penetration' should be positive or zero, but it is = {absolute_one_side_penetration}"

    one_side_penetration = 0.5 * total_penetration * at_relative_penetration_percent / 100.0

    radius_contact_length_list = []
    total_die_contact_length_list = []
    for _, _id in die_ids:

        # ================================== DIE PARAMETERS ==========================================

        die = dies[_id]
        edge_radius = die['edge_radius']
        edge_angle = die['edge_angle']  # Degrees
        edge_angle_radians = math.radians(edge_angle)
        straight_length = die['straight_length']
        radius_height = die['radius_height']
        radius_length = die['radius_length']
        curved_height = die['curved_height']
        curved_length = die['curved_length']
        is_have_slope = die['is_have_slope']

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

    return die_ids[selected_die_index][1], radius_contact_length_list[selected_die_index]


die_ids = [(0, 5), (0, 7)]

dies = {
    5: dict(
        total_length = 900.0,
        total_width = 1500.0,
        height = 1200.0,
        straight_length = 500.0,
        edge_radius = 250.0,
        edge_angle = 90.0,
    ),
    7: dict(
        total_length=650.0,
        total_width=2200.0,
        height=1200.0,
        straight_length=390.0,
        edge_radius=160.0,
        edge_angle=90.0,
    )
}

extended_dies = _extend_die_parameters(dies)

for _id, param in extended_dies.items():
    print(f"DIE ID: {_id}")
    for param_name, param_value in param.items():
        if isinstance(param_value, bool):
            print(f"{param_name:>20s}: {str(param_value):<10s}")
        else:
            print(f"{param_name:>20s}: {param_value:<10.2f}")

penetrations = [200, 100, 50, 20, 10, 2]
s = f"{'penetration':^20s}"
for penetration in penetrations:
    s += f"{penetration/2:14.1f}mm"
print(s)
for percent in [100.0, 75.0, 50.0, 40.0, 30.0, 20.0, 10.0, 5.0, 2.5, 1.0, 0.5]:
    s = f"{percent:19.1f}%"
    for penetration in penetrations:
        die_index, _contact_length = _calculate_radius_contact_length(extended_dies, die_ids, penetration, percent)
        s += f"{_contact_length:10.1f}mm ({die_index})"
    print(s)

s = f"{'penetration':^20s}"
for penetration in penetrations:
    s += f"{penetration/2:14.1f}mm"
print(s)
for percent in [100.0, 75.0, 50.0, 40.0, 30.0, 20.0, 10.0, 5.0, 2.5, 1.0, 0.5]:
    s = f"{percent:19.1f}%"
    for penetration in penetrations:
        die_index, percent_contact_length = _calculate_radius_contact_length(extended_dies, die_ids, penetration, percent)
        _, full_contact_length = _calculate_radius_contact_length(extended_dies, die_ids, penetration, 100.0)
        s += f"{100*percent_contact_length/full_contact_length:11.1f}% ({die_index})"
    print(s)
