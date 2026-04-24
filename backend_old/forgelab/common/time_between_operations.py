import logging

import pandas as pd

# create logger
LOGGER = logging.getLogger(__name__)


def get_time_between_operations(_lib: dict, first_operation_type_id, second_operation_type_id, press_id) -> float:
    """Reads ['lib']['time_between_operations'] and returns time_mean."""
    try:
        tbo: pd.DataFrame = _lib['time_between_operations']
        # TODO: check type of variable passing to .all(axis=1)
        mask = (
                (tbo[['first_operation_type_id']] == first_operation_type_id) &
                (tbo[['second_operation_type_id']] == second_operation_type_id) &
                (tbo[['press_id']] == press_id)
                ).all(axis=1)
        time_record = tbo.loc[mask.loc[mask].index]

        assert time_record.shape[0] != 0, (f"Error in 'time_between_operations' table. There is no any record "
                                           f"where 'first_operation_type_id' = {first_operation_type_id}, "
                                           f"'second_operation_type_id' = {second_operation_type_id} "
                                           f"and 'press_id' = {press_id}.")

        assert time_record.shape[0] == 1, (f"Error in 'time_between_operations' table. There are "
                                           f"{time_record.shape[0]} "
                                           f"duplicates where 'first_operation_type_id' = {first_operation_type_id}, "
                                           f"'second_operation_type_id' = {second_operation_type_id} "
                                           f"and 'press_id' = {press_id}.")

        _time = time_record['time_mean'].item()

        assert _time >= 0.0, f"Time between operations is {_time} seconds, but must be positive value"

    except AssertionError as _err:
        LOGGER.error(_err)
    except Exception as _err:
        LOGGER.error(_err)
    else:
        return _time
    raise
