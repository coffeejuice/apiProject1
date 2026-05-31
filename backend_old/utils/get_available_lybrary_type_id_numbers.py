import os
from pathlib import Path

from forgelab.sql_setup.connections import is_postgresql_db_exists, load_config, select_configuration, connect_to_db
from forgelab.sql_setup.query_operation import get_type_ids

# print(f'__file__={__file__:<35} | __name__={__name__:<25} | __package__={str(__package__):<25}')


# Drop db
_p = Path(os.path.split(__file__)[0])
_root_dir = os.path.abspath(_p.parent)
multiple_config = load_config(_root_dir)

config = select_configuration(multiple_config)

conn, cur = connect_to_db(config)

if is_postgresql_db_exists(config):
    values = get_type_ids(cur)
    max_id = max(values)
    min_id = min(values)
    # find missing integer numbers in list 'values'
    missing = [str(x) for x in range(min_id, max_id + 1) if x not in values]
    print(f"Missing: {', '.join(missing)}, {max_id + 1}...")
else:
    print(f"\nDatabase '{config['base']}' does not exists")
