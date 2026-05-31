import os
import json
import numpy as np
import pandas as pd

from forgelab.common.library_sql_query import sorting_generator


def convert_operations_to_dict(records: list[tuple], lib) -> list[dict]:
    return [
        {column_name: operation[index] for index, column_name in enumerate(lib['operations_columns'])}
        for operation in records
    ]


def designate_root_as_0(records_dict):
    """Finds where 'parent_type_id' is None and substitute None with 0."""
    for record_dict in records_dict:
        if pd.isna(record_dict['parent_id']):
            record_dict['parent_id'] = 0


def build_library_dict(records_dict: list[dict], lib) -> dict:
    result = {column_name: {} for column_name in lib['operations_columns']}
    for record_dict in records_dict:
        _id: int = record_dict.get('id')
        for column_name in lib['operations_columns']:
            result[column_name][_id] = record_dict.get(column_name)
    return result


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


def reorder_by_row_for_flat_tree(input_ids: dict, row_dict: dict) -> dict:
    """Reorder 'child_type_ids' by 'row' in 'lib' in place."""
    result = {}
    for parent_id, children_ids in input_ids.items():
        children_ids: list
        row_list = [row_dict[child] for child in children_ids]
        result[parent_id] = [x for x in sorting_generator(children_ids, row_list)]
    return result


def build_tree_for_flat_tree(input_dict: dict):
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


def calculate_accumulation_trigger(ol_flat_tree) -> pd.DataFrame:
    start_accumulating_with_type_id = {
        "billet": 2,
        "heating": 3,
        "forming": 4
    }
    stop_accumulating_with_type_id = {
        "billet": 7,
        "heating": 11,
        "forming": 25
    }
    _start_trigger_type_ids = list(start_accumulating_with_type_id.values())
    _stop_trigger_type_ids = list(stop_accumulating_with_type_id.values())

    is_start: bool = False
    len_ol = len(ol_flat_tree)
    is_initialize = [False] * len_ol
    is_accumulate = [False] * len_ol
    is_keep = [False] * len_ol

    _accumulation_trigger = []

    for _i, (_, _type_id) in enumerate(ol_flat_tree):
        is_previous_start = is_start

        if _type_id in _start_trigger_type_ids:
            is_start = True
        elif _type_id in _stop_trigger_type_ids:
            is_start = False

        is_stop = not is_start
        is_previous_stop = not is_previous_start

        if is_start:
            if is_previous_stop:
                _accumulation_trigger.append('initialize')
                is_initialize[_i] = True
            elif is_previous_start:
                _accumulation_trigger.append('accumulate')
                is_accumulate[_i] = True
        elif is_stop:
            _accumulation_trigger.append('keep')
            is_keep[_i] = True

    data = {
        'trigger': _accumulation_trigger,
        'trigger_is_initialize': is_initialize,
        'trigger_is_accumulate': is_accumulate,
        'trigger_is_keep': is_keep
    }
    _accumulation_trigger = pd.DataFrame(data=data, index=np.arange(len(ol_flat_tree)))

    return _accumulation_trigger


def add_attributes_to_operations_json(ol: pd.DataFrame, _lib: dict):
    # Flatten tree of 'operations' SQL table
    # column_indices = [ol_columns.index(column) for column in columns]
    _sparse_ol_records = ol.loc[:, ['type_id', 'parent_type_id', 'type_id', 'row']].to_numpy().tolist()
    operations_list_of_dicts = convert_operations_to_dict(_sparse_ol_records, _lib)
    designate_root_as_0(operations_list_of_dicts)
    operations_dict_of_lists = build_library_dict(operations_list_of_dicts.copy(), _lib)
    parent_children = find_child_ids(operations_list_of_dicts)
    child_ids = reorder_by_row_for_flat_tree(parent_children.copy(), operations_dict_of_lists['row'])
    tree = build_tree_for_flat_tree(child_ids.copy())
    flat_tree = convert_tree_to_flat(tree.copy(), operations_dict_of_lists['type_id'])
    _lib['accumulation_trigger'] = calculate_accumulation_trigger(flat_tree)

    # read json file 'operations_old.json'
    with open(os.path.join(os.path.dirname(__file__), 'operations_old.json'), 'r', encoding='utf-8') as _file:
        _json = json.load(_file)

    new_operations = {}
    for _i, (_, type_id) in enumerate(flat_tree):
        _operation = _json.get(str(type_id))
        _operation.update(
            {
                'trigger': _lib['accumulation_trigger']['trigger'][_i],  # 'initialize', 'accumulate', 'keep'
                'is_initialize': _lib['accumulation_trigger']['trigger_is_initialize'][_i].item(),
                'is_accumulate': _lib['accumulation_trigger']['trigger_is_accumulate'][_i].item(),
                'is_keep': _lib['accumulation_trigger']['trigger_is_keep'][_i].item()
            }
        )
        new_operations[type_id] = _operation

    _json = json.dumps(new_operations, indent=4, ensure_ascii=False)
    with open(os.path.join(os.path.dirname(__file__), 'operations.json'), 'w', encoding='utf-8') as _file:
        _file.write(_json)
