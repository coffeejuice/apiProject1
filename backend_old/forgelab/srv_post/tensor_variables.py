from math import pi
import numpy as np


def root3_if_positive_q(a, r2, q, rq, arq):
    # if arq > 1. and arq <= 1. + 1e-6:
    #     if rq > 1.:
    #         rq = np.full(a.shape, 1.)
    #     else:
    #         rq = np.full(a.shape, -1.)
    rq_plus_minus_ones = np.where(rq > 1., np.full(a.shape, 1.), np.full(a.shape, -1.))
    condition = np.logical_and(arq > 1., arq <= 1. + 1e-6)
    rq = np.where(condition, rq_plus_minus_ones, rq)

    th = np.arccos(rq)
    t3 = th / 3.
    a3 = a / 3.
    qr = -2. * np.sqrt(q)
    p23 = 2. * pi / 3.
    x = np.array([
        qr * np.cos(t3) - a3,
        qr * np.cos(t3 + p23) - a3,
        qr * np.cos(t3 - p23) - a3])
    r1 = -1e8 * np.ones(a.shape)
    r3 = 1e8 * np.ones(a.shape)
    mx = np.full(a.shape, -1)
    mn = np.full(a.shape, -1)
    for i, xi in enumerate(x):
        ith = np.full(a.shape, i)
        mx = np.where(xi > r1, ith, mx)
        r1 = np.where(xi > r1, xi, r1)
        mn = np.where(xi < r3, ith, mn)
        r3 = np.where(xi < r3, xi, r3)
    pass_trigger = np.full(a.shape, True)
    for i, xi in enumerate(x):
        ith = np.full(a.shape, i)
        condition = np.logical_and(ith != mx, ith != mn)
        r2 = np.where(np.logical_and(condition, pass_trigger), xi, r2)
        pass_trigger = np.where(condition, False, pass_trigger)
    return r1, r2, r3


def root3(a, b, c):
    i_flag = np.zeros(a.shape)
    a2 = a * a
    a3 = a2 * a
    q = (a2 - 3. * b) / 9.
    r = (2. * a3 - 9. * a * b + 27. * c) / 54.

    allow_changing_trigger = np.full(a.shape, True)

    condition_0 = q < 0.
    i_flag = np.where(condition_0, 1, i_flag)
    allow_changing_trigger = np.logical_and(allow_changing_trigger, np.logical_not(condition_0))

    condition_1 = q == 0.
    allow_condition = np.logical_and(condition_1, allow_changing_trigger)
    allow_changing_trigger = np.logical_and(allow_changing_trigger, np.logical_not(condition_1))

    a13 = a / -3.
    r1 = np.where(allow_condition, a13, 0.)
    r2 = np.where(allow_condition, a13, 0.)
    r3 = np.where(allow_condition, a13, 0.)
    q3 = np.power(q, 3)
    sq = np.sqrt(q3)
    rq = np.divide(r, sq, out=np.zeros_like(r), where=(sq != 0.0))
    arq = np.abs(rq)

    # if arq > 1. + 1e-6:
    #     i_flag = np.ones(a.shape)
    condition_2 = arq > 1. + 1.e-6
    allow_condition = np.logical_and(condition_2, allow_changing_trigger)
    i_flag = np.where(allow_condition, 1, i_flag)
    allow_changing_trigger = np.logical_and(allow_changing_trigger, np.logical_not(condition_2))

    r1_q_pos, r2_q_pos, r3_q_pos = root3_if_positive_q(a, r2, q, rq, arq)
    r1 = np.where(allow_changing_trigger, r1_q_pos, r1)
    r2 = np.where(allow_changing_trigger, r2_q_pos, r2)
    r3 = np.where(allow_changing_trigger, r3_q_pos, r3)

    return np.stack([r1, r2, r3], axis=1), i_flag


def principal_values(t):
    t0 = t[:, 0]
    t1 = t[:, 1]
    t2 = t[:, 2]
    t3 = t[:, 3]
    t4 = t[:, 4]
    t5 = t[:, 5]
    txy2 = np.square(t[:, 3])
    tyz2 = np.square(t[:, 4])
    tzx2 = np.square(t[:, 5])
    a = -1. * np.sum(t[:, [0, 1, 2]], axis=1)
    b = t0 * t1 + t1 * t2 + t2 * t0 - (txy2 + tyz2 + tzx2)
    c = t0 * tyz2 + t1 * tzx2 + t2 * txy2 - (t0 * t1 * t2 + 2. * t3 * t4 * t5)
    _principal_vectors, i_flag = root3(a, b, c)
    return _principal_vectors


def vector_to_scalar_magnitude(vector):
    return np.linalg.norm(vector, axis=1, ord=2)


def vector_to_vector_x_projection(vector):
    vector[:, [1, 2]] = 0.
    return vector


def vector_to_vector_y_projection(vector):
    vector[:, [0, 2]] = 0.
    return vector


def vector_to_vector_z_projection(vector):
    vector[:, [0, 1]] = 0.
    return vector


def tensor_to_scalar_max_principal(tensor):
    return principal_values(tensor)[:, 0]


def tensor_to_scalar_inter_principal(tensor):
    return principal_values(tensor)[:, 1]


def tensor_to_scalar_min_principal(tensor):
    return principal_values(tensor)[:, 2]


def tensor_to_vector_min_principal(tensor):
    # TODO: Min principal is not finished
    return tensor_to_vector_x_projection(tensor)


def tensor_to_vector_max_principal(tensor):
    # TODO: Max principal is not finished
    return tensor_to_vector_x_projection(tensor)


def tensor_to_vector_x_projection(tensor):
    vector = tensor[:, [0, 1, 2]]
    vector[:, [1, 2]] = 0.
    return vector


def tensor_to_vector_y_projection(tensor):
    vector = tensor[:, [0, 1, 2]]
    vector[:, [0, 2]] = 0.
    return vector


def tensor_to_vector_z_projection(tensor):
    # tensor[x, y, z, xy, yz, zx]
    vector = tensor[:, [0, 1, 2]]
    vector[:, [0, 1]] = 0.
    return vector


def tensor_to_scalar_mean(tensor):
    return np.sum(tensor[:, [0, 1, 2]], axis=1) / 3.


def tensor_to_scalar_equivalent(t):
    return np.sqrt(
        0.5 * (
                np.square(t[:, 0] - t[:, 1]) +
                np.square(t[:, 1] - t[:, 2]) +
                np.square(t[:, 2] - t[:, 0]) +
                6. * (np.square(t[:, 3]) + np.square(t[:, 4]) + np.square(t[:, 5]))
        )
    )


def get_variables_list(data):
    return [
        {
            'var_type': 'none',
            'variable': None,
            'title': 'Surface only'},
        {
            'var_type': 'nodal',
            'data_type': 'scalar',
            'variable': data['nodal_scalar_temperature'],
            'title': 'Temperature'},
        {
            'var_type': 'nodal',
            'data_type': 'scalar',
            'variable': data['nodal_scalar_user_1'],
            'title': 'User 1 Temperature'},
        {
            'var_type': 'nodal',
            'data_type': 'scalar',
            'variable': data['nodal_scalar_user_2'],
            'title': 'User 2 Temperature'},

        {
            'var_type': 'nodal',
            'data_type': 'vector',
            'variable': data['nodal_vector_speed'],
            'title': 'Speed Vectors'},

        {
            'var_type': 'element',
            'data_type': 'scalar',
            'variable': data['element_scalar_strain'],
            'title': 'Strain Elemental'},
        {
            'var_type': 'element',
            'data_type': 'scalar',
            'variable': data['element_scalar_damage'],
            'title': 'Damage Elemental'},
        {
            'var_type': 'element',
            'data_type': 'scalar',
            'variable': data['element_scalar_user_1'],
            'title': 'User 1 Strain Elemental'},
        {
            'var_type': 'element',
            'data_type': 'scalar',
            'variable': data['element_scalar_user_2'],
            'title': 'User 2 Strain Elemental'},
        {
            'var_type': 'element',
            'data_type': 'scalar',
            'variable': tensor_to_scalar_equivalent(data['element_tensor6_strain']),
            'title': 'Strain Equivalent'},

        {
            'var_type': 'element',
            'data_type': 'scalar',
            'variable': tensor_to_scalar_mean(data['element_tensor6_strain']),
            'title': 'Strain Mean'},
        {
            'var_type': 'element',
            'data_type': 'scalar',
            'variable': tensor_to_scalar_mean(data['element_tensor6_stress']),
            'title': 'Stress Mean'},

        {
            'var_type': 'element',
            'data_type': 'vector',
            'variable': tensor_to_vector_x_projection(data['element_tensor6_stress']),
            'title': 'Strain Total X Vectors'},

        {
            'var_type': 'element',
            'data_type': 'vector',
            'variable': tensor_to_vector_y_projection(data['element_tensor6_stress']),
            'title': 'Strain Total Y Vectors'},

        {
            'var_type': 'element',
            'data_type': 'vector',
            'variable': tensor_to_vector_z_projection(data['element_tensor6_stress']),
            'title': 'Strain Total Z Vectors'},

        {
            'var_type': 'element',
            'data_type': 'vector',
            'variable': tensor_to_vector_min_principal(data['element_tensor6_strain']),
            'title': 'Strain Min Principal Vectors'},
        {
            'var_type': 'element',
            'data_type': 'vector',
            'variable': tensor_to_vector_min_principal(data['element_tensor6_stress']),
            'title': 'Stress Min Principal Vectors'},

        {
            'var_type': 'element',
            'data_type': 'vector',
            'variable': tensor_to_vector_max_principal(data['element_tensor6_strain']),
            'title': 'Strain Max Principal Vectors'},
        {
            'var_type': 'element',
            'data_type': 'vector',
            'variable': tensor_to_vector_max_principal(data['element_tensor6_stress']),
            'title': 'Stress Max Principal Vectors'},
        {
            'var_type': 'element',
            'data_type': 'scalar',
            'variable': tensor_to_scalar_max_principal(data['element_tensor6_strain']),
            'title': 'Strain Max Principal scalar'},
        {
            'var_type': 'element',
            'data_type': 'scalar',
            'variable': tensor_to_scalar_inter_principal(data['element_tensor6_strain']),
            'title': 'Strain Inter Principal scalar'},
        {
            'var_type': 'element',
            'data_type': 'scalar',
            'variable': tensor_to_scalar_min_principal(data['element_tensor6_strain']),
            'title': 'Strain Min Principal scalar'},
        {
            'var_type': 'element',
            'data_type': 'scalar',
            'variable': tensor_to_scalar_max_principal(data['element_tensor6_stress']),
            'title': 'Stress Max Principal scalar'},
        {
            'var_type': 'element',
            'data_type': 'scalar',
            'variable': tensor_to_scalar_inter_principal(data['element_tensor6_stress']),
            'title': 'Stress Inter Principal scalar'},
        {
            'var_type': 'element',
            'data_type': 'scalar',
            'variable': tensor_to_scalar_min_principal(data['element_tensor6_stress']),
            'title': 'Stress Min Principal scalar'},
    ]
