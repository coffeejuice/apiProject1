from psycopg2.extensions import connection
from enum import Enum, unique


@unique
class CreateTables(Enum):

    # Set by 'forgelabPre' and read by 'forgelabClient'
    preview_status_enum = \
        "CREATE TYPE preview_status_enum AS ENUM ('empty', 'error', 'ok', 'ok_not_editable');"

    simulation_status_enum = \
        "CREATE TYPE simulation_status_enum AS ENUM ('stop', 'queue', 'run', 'finished', 'error');"

    post_status_enum = \
        "CREATE TYPE post_status_enum AS ENUM ('stop', 'queue', 'run', 'finished', 'error');"

    priority_enum = """
CREATE TYPE priority_enum AS ENUM ('Whenever', 'Normal', 'ASAP', 'Now');
"""

    die_type = """
CREATE TABLE IF NOT EXISTS die_types (
    id   SERIAL PRIMARY KEY,
    name JSON NOT NULL
);
"""

    deformation_type_enum = """
CREATE TYPE deformation_type_enum AS ENUM ('upsetting', 'axial_prolongation', 'radial_prolongation', 'full_die', 
'hot_cutting', 'cold_sawing');
"""

    # Server types
    server_type_enum = """
CREATE TYPE server_type_enum AS ENUM ('pre', 'post', 'simulation', 'sql', 'client', 'file_server');
"""

    # Define the renamed ENUM type for logging levels
    log_level_enum = """
CREATE TYPE log_level_enum AS ENUM ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL');
"""

    config = """
CREATE TABLE IF NOT EXISTS config (
    server_type server_type_enum PRIMARY KEY,   -- Type of server using the existing ENUM type
    config_json JSONB DEFAULT NULL
);"""

    # Ingot side
    ingot_side = """
CREATE TABLE IF NOT EXISTS ingot_side (
    id SERIAL PRIMARY KEY,
    name VARCHAR(511) NOT NULL
);
"""

    operations_library = """
CREATE TABLE IF NOT EXISTS operations_library (
    type_id                     SMALLINT PRIMARY KEY,
    parent_type_id              SMALLINT,
    auto_create_children        VARCHAR(63) DEFAULT NULL, 
    row                         SMALLINT NOT NULL,
    process_fixed_row           SMALLINT DEFAULT NULL,
    allow_copies                BOOL NOT NULL DEFAULT FALSE,
    text_id                     VARCHAR(511) NOT NULL,
    library_name                VARCHAR(255) NOT NULL,
    process_name                VARCHAR(255) NOT NULL,
    labels                      VARCHAR(1023) DEFAULT NULL,
    labels_regex                VARCHAR(255) DEFAULT NULL,
    db_column_names             VARCHAR(255) DEFAULT '',
    foreign_keys                VARCHAR(1023) DEFAULT NULL,
    is_simulation               BOOL NOT NULL DEFAULT FALSE,
    is_geometry                 BOOL NOT NULL DEFAULT FALSE,
    is_die_assembly             BOOL NOT NULL DEFAULT FALSE,
    is_custom_die_assembly      BOOL NOT NULL DEFAULT FALSE,
    is_press                    BOOL NOT NULL DEFAULT FALSE,
    is_feed                     BOOL NOT NULL DEFAULT FALSE,
    is_top_die                  BOOL NOT NULL DEFAULT FALSE,
    is_bottom_die               BOOL NOT NULL DEFAULT FALSE,
    is_speed                    BOOL NOT NULL DEFAULT FALSE,
    is_billet_category          BOOL NOT NULL DEFAULT FALSE,
    is_heating_category         BOOL NOT NULL DEFAULT FALSE,
    is_forming_category         BOOL NOT NULL DEFAULT FALSE,
    is_forming_operation        BOOL NOT NULL DEFAULT FALSE,
    is_surface_treatment_operation  BOOL NOT NULL DEFAULT FALSE,
    deformation_type            VARCHAR(255) DEFAULT NULL,
    speed_column_name           VARCHAR(255) DEFAULT NULL,
    tooltip_image               BYTEA DEFAULT NULL,
    trigger                     VARCHAR(63) DEFAULT NULL,
    is_initialize               BOOL NOT NULL DEFAULT FALSE,
    is_accumulate               BOOL NOT NULL DEFAULT FALSE,
    is_keep                     BOOL NOT NULL DEFAULT FALSE,
    is_obsolete                 BOOL NOT NULL DEFAULT FALSE,

    FOREIGN KEY (parent_type_id) REFERENCES operations_library(type_id) ON DELETE RESTRICT
);
"""

    operations_library_update_signal = """
CREATE TABLE operations_library_update_signal (
    id SERIAL PRIMARY KEY,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
"""

    operations_library_update_signal_INSERT = """
    INSERT INTO operations_library_update_signal (last_updated) VALUES (CURRENT_TIMESTAMP);
"""

    logs = """
CREATE TABLE IF NOT EXISTS logs (
    id BIGSERIAL PRIMARY KEY,           -- Unique identifier for each log record
    logger server_type_enum NOT NULL,   -- Name of the logger using the existing ENUM type
    level log_level_enum NOT NULL,      -- Severity level of the log using the renamed ENUM type
    msg TEXT NOT NULL,                  -- Actual message of the log
    logger_time TIMESTAMP,              -- Timestamp, received from logger
    sql_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, -- Timestamp when the log was generated
    process_version_id BIGINT,          -- process_versions.process_version_id
    user_id INT,                        -- accounts.user_id
    hostname VARCHAR(255),              -- Name of the machine/host from which the log originated
    ip inet                            -- IP address (IPv4 or IPv6) of the machine/host
);
"""

    ui_language = """
CREATE TABLE IF NOT EXISTS ui_language (
    language_id SMALLINT PRIMARY KEY,
    language_code VARCHAR(7) NOT NULL,
    language_name VARCHAR(63) NOT NULL
);
"""

    departments = """
CREATE TABLE IF NOT EXISTS departments (
    department_id SMALLSERIAL PRIMARY KEY,
    department_name VARCHAR(512) NOT NULL
);
"""

    accounts = """
CREATE TABLE IF NOT EXISTS accounts (
    user_id                     SERIAL PRIMARY KEY,
    login                       VARCHAR(255) UNIQUE NOT NULL,
    password_hashed             BYTEA NOT NULL,
    signal_clear_token          BOOL NOT NULL DEFAULT FALSE,
    supervisor_id               INT NOT NULL DEFAULT 1,
    full_name                   VARCHAR(511) DEFAULT NULL,
    department_id               SMALLINT NOT NULL DEFAULT 1,
    language_id                 SMALLINT NOT NULL DEFAULT 1,  -- 1=English
    editor_append_mode_id       SMALLINT NOT NULL DEFAULT 1,  -- Resolve conflict: 1=Ask user, 2=Substitute, 3=Ignore
    user_settings               VARCHAR(32767) DEFAULT NULL,
    process_version_id          BIGINT DEFAULT NULL,  -- Current process version ID user works with now
    user_priority_enum               priority_enum NOT NULL DEFAULT 'Normal',
    created_at                  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (language_id) REFERENCES ui_language(language_id) ON DELETE SET DEFAULT,
    FOREIGN KEY (department_id) REFERENCES departments(department_id) ON DELETE SET DEFAULT
);
"""

    material = """
CREATE TABLE IF NOT EXISTS materials (
    material_id SERIAL PRIMARY KEY,
    material_name VARCHAR(2047) NOT NULL,
    material_path VARCHAR(2047) NOT NULL,
    short_name VARCHAR(63) NOT NULL DEFAULT '',
    density DOUBLE PRECISION DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

    process = """
CREATE TABLE IF NOT EXISTS process (
    process_id                  BIGSERIAL PRIMARY KEY,
    user_id                     INTEGER NOT NULL DEFAULT 1,
    material_id                 SMALLINT NOT NULL DEFAULT 1,
    heat_no                     VARCHAR(255) NOT NULL,
    lot_no                      VARCHAR(255) NOT NULL,
    finished_size               VARCHAR(255) NOT NULL,
    standard_customer           VARCHAR(511) NOT NULL,
    standard_wst                VARCHAR(511) NOT NULL,
    product_condition           VARCHAR(7) NOT NULL,
    product_surface             VARCHAR(63) NOT NULL,
    product_diameter_tolerance  VARCHAR(63) NOT NULL,
    product_length_tolerance    VARCHAR(63),
    product_curvature_tolerance VARCHAR(63) NOT NULL,
    stock_size                  VARCHAR(63) NOT NULL,
    stock_weight                NUMERIC(10, 2) NOT NULL,
    stock_no                    VARCHAR(63) NOT NULL,
    material_btt                NUMERIC(6, 2) NOT NULL,
    material_btt_sym_tolerance  NUMERIC(6, 2) NOT NULL,
    remarks                     VARCHAR(4095) NOT NULL,
    created_at                  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_edit_at                TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_process_user_id_accounts_user_id
        FOREIGN KEY (user_id)
            REFERENCES accounts(user_id) ON DELETE SET DEFAULT,

    CONSTRAINT fk_process_material_id_material_material_id
        FOREIGN KEY (material_id)
            REFERENCES materials(material_id) ON DELETE SET DEFAULT
);
"""

    process_headers = """
CREATE TABLE IF NOT EXISTS process_headers (
    process_id          VARCHAR(63) NOT NULL,
    material_id         VARCHAR(63) NOT NULL,
    heat_no             VARCHAR(63) NOT NULL,
    lot_no              VARCHAR(63) NOT NULL,
    finished_size       VARCHAR(63) NOT NULL,
    standard_customer   VARCHAR(63) NOT NULL,
    standard_wst        VARCHAR(63) NOT NULL,
    product_condition   VARCHAR(63) NOT NULL,
    product_surface     VARCHAR(63) NOT NULL,
    product_diameter_tolerance VARCHAR(63) NOT NULL,
    product_length_tolerance VARCHAR(63) NOT NULL,
    product_curvature_tolerance VARCHAR(63) NOT NULL,
    stock_size          VARCHAR(63) NOT NULL,
    stock_weight        VARCHAR(63) NOT NULL,
    stock_no            VARCHAR(63) NOT NULL,
    material_btt        VARCHAR(63) NOT NULL,
    material_btt_sym_tolerance VARCHAR(63) NOT NULL,
    remarks             VARCHAR(63) NOT NULL,
    created_at          VARCHAR(63) NOT NULL,
    user_id            VARCHAR(63) NOT NULL
);
"""

    process_hide_flag = """
CREATE TABLE IF NOT EXISTS process_hide_flag (
    account_user_id     SMALLINT NOT NULL,
    process_id          BOOL DEFAULT NULL,
    material_id         BOOL DEFAULT NULL,
    heat_no             BOOL DEFAULT NULL,
    lot_no              BOOL DEFAULT NULL,
    finished_size       BOOL DEFAULT NULL,
    standard_customer   BOOL DEFAULT NULL,
    standard_wst        BOOL DEFAULT NULL,
    product_condition   BOOL DEFAULT NULL,
    product_surface     BOOL DEFAULT NULL,
    product_diameter_tolerance BOOL DEFAULT NULL,
    product_length_tolerance BOOL DEFAULT NULL,
    product_curvature_tolerance BOOL DEFAULT NULL,
    stock_size          BOOL DEFAULT NULL,
    stock_weight        BOOL DEFAULT NULL,
    stock_no            BOOL DEFAULT NULL,
    material_btt        BOOL DEFAULT NULL,
    material_btt_sym_tolerance BOOL DEFAULT NULL,
    remarks             BOOL DEFAULT NULL,
    created_at          BOOL DEFAULT NULL,
    user_id             BOOL DEFAULT NULL,
    FOREIGN KEY (account_user_id) REFERENCES accounts(user_id) ON DELETE CASCADE
);
"""

    # 'simulation_queue_number': Continuous chain queue number. Starts with 1. Highest priority = 1.
    # 'simulation_queue_number' is sorted as follows:
    #                           WHERE run_switch_status = TRUE
    #                           ORDER BY
    #                               simulation_priority DESC,
    #                               simulation_expected_duration_days DESC
    # The queue number divided by blocks of simulation threads (rows). Few simulation have same row number and should
    # run simultaneously. Number of threads in one row is equal to total number of running threads on active simulation
    # servers. Row number starts with 1. Highest row priority = 1.

    process_versions = """
CREATE TABLE IF NOT EXISTS process_versions (
    process_version_id      BIGSERIAL PRIMARY KEY,
    process_id              BIGINT,

    -- PARENT PROCESS
    parent_process_version_id   BIGINT DEFAULT NULL,        -- The id of the parent process version that was copied to create this process version

    -- PREVIEW WIDGET STATUS
    is_editable                 BOOL DEFAULT TRUE,
    preview_status              preview_status_enum NOT NULL DEFAULT 'empty',   -- Set by 'forgelabPre' and read by 'forgelabClient'

    -- SIMULATION WIDGET STATUS
    run_switch_status           BOOL NOT NULL DEFAULT FALSE,    -- Set  by 'forgelabClient', read by 'forgelabSimulation'
    run_switch_is_active        BOOL NOT NULL DEFAULT FALSE,    -- Set by 'forgelabPre' & 'forgelabSimulation', read by 'forgelabClient'
    simulation_status           simulation_status_enum NOT NULL DEFAULT 'stop', -- Set by 'forgelabSimulation', read by 'forgelabClient'

    -- SIMULATION PROGRESS
    execution_order             SMALLINT DEFAULT NULL,      -- The order of execution of the simulation. Starts with 1.
    operations_count            SMALLINT DEFAULT NULL,      -- The number of operations in the simulation
    simulation_expected_duration_days   DOUBLE PRECISION DEFAULT 0, -- Expected duration of the simulation in days
    simulation_percent          SMALLINT DEFAULT 0,

    -- TEMPORARY PROJECT PARAMETERS
    simulation_server_id        SMALLINT DEFAULT NULL,      -- The id of the simulation server that is running the simulation
    db_path_name                VARCHAR(2047) DEFAULT NULL,

    -- PERMANENT PROJECT PARAMETERS 
    name                    VARCHAR(2047) NOT NULL,
    ppt_file_name           VARCHAR(255) DEFAULT NULL,
    pdf_file_name           VARCHAR(255) DEFAULT NULL,
    db_file_name            VARCHAR(255) DEFAULT NULL,
    project_dir_name        VARCHAR(255) DEFAULT NULL,

    -- TIME
    created_at              TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_modified           TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ran_at                  TIMESTAMP DEFAULT NULL,
    finished_at             TIMESTAMP DEFAULT NULL,

    -- SIMULATION QUEUE INPUT
    process_priority_enum       priority_enum NOT NULL DEFAULT 'Normal',

    -- SIMULATION QUEUE OUTPUT
    simulation_priority         SMALLINT DEFAULT 5,                         -- Integer in range (0, (4^2 - 1)) = 0..15
    simulation_queue_number     SMALLINT DEFAULT NULL,
    simulation_queue_row_number     SMALLINT DEFAULT NULL,

    FOREIGN KEY (process_id) REFERENCES process(process_id) ON DELETE RESTRICT,
    FOREIGN KEY (parent_process_version_id) REFERENCES process_versions(process_version_id) ON DELETE SET NULL
);
"""

    accounts_ALTER = """
ALTER TABLE accounts ADD
FOREIGN KEY (process_version_id) REFERENCES process_versions(process_version_id) ON DELETE SET DEFAULT;
"""

    operations = """
CREATE TABLE IF NOT EXISTS operations (
    id BIGSERIAL,
    parent_id BIGINT,
    type_id SMALLINT NOT NULL,
    row INT NOT NULL DEFAULT 0,
    process_version_id BIGINT NOT NULL,

    PRIMARY KEY (id),

    CONSTRAINT fk_operations_parent_id_operations_id
        FOREIGN KEY (parent_id)
            REFERENCES operations(id) ON DELETE CASCADE,

    CONSTRAINT fk_operations_type_id_library
        FOREIGN KEY (type_id)
            REFERENCES operations_library(type_id) ON DELETE RESTRICT,

    CONSTRAINT fk_operations_process_version
        FOREIGN KEY (process_version_id)
            REFERENCES process_versions(process_version_id) ON DELETE CASCADE
);
"""

    operations_changes = """
CREATE TABLE IF NOT EXISTS operations_changes (
    id                  BIGINT NOT NULL UNIQUE,
    process_version_id  BIGINT NOT NULL,
    time_created        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_operations_changes_id
        FOREIGN KEY (id)
        REFERENCES operations(id) ON DELETE CASCADE,
    CONSTRAINT fk_operations_changes_process_version_id
        FOREIGN KEY (process_version_id)
        REFERENCES process_versions(process_version_id) ON DELETE CASCADE
);
"""

    operation_type_category = """
CREATE TABLE IF NOT EXISTS operation_type_category (
    id SMALLINT PRIMARY KEY,
    name VARCHAR(127)
    );
"""

    press = """
CREATE TABLE IF NOT EXISTS presses (
    press_id                SERIAL PRIMARY KEY,
    default_press_mode_id   INT,
    name                    JSON NOT NULL,
    is_obsolete             BOOL NOT NULL DEFAULT FALSE,
    created_at              TIMESTAMP NOT NULL DEFAULT NOW(),
    obsolete_at             TIMESTAMP DEFAULT NULL
);
"""

    # press parameters
    # approaching_distance - Distance to billet, at which speed switches from idle to working ones
    press_mode = """
CREATE TABLE IF NOT EXISTS press_modes (
    press_mode_id               SERIAL,
    press_id                    SMALLINT,
    name                        JSON,
    is_left_manipulator         BOOL NOT NULL DEFAULT FALSE,
    is_right_manipulator        BOOL NOT NULL DEFAULT FALSE,
    automatic_feed_mode_is_on_when_bites_count SMALLINT,
    max_force                   FLOAT,
    back_speed                  FLOAT,
    idle_speed                  FLOAT,
    working_speed               FLOAT,
    min_dwell_speed             FLOAT,
    max_dwell_time              FLOAT,
    min_idle_stroke             FLOAT,
    max_idle_stroke             FLOAT,
    approaching_distance        FLOAT,
    open_height_without_dies    FLOAT,
    PRIMARY KEY (press_mode_id),
    FOREIGN KEY (press_id) REFERENCES presses(press_id) ON DELETE RESTRICT
);
"""

    press_ALTER = """
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'presses'
          AND column_name = 'default_press_mode_id'
    ) AND EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_name = 'press_modes'
    ) THEN
        IF NOT EXISTS (
            SELECT 1
            FROM information_schema.table_constraints
            WHERE table_name = 'presses'
              AND constraint_name = 'fk_press_default_press_mode_id'
        ) THEN
            ALTER TABLE presses
            ADD CONSTRAINT fk_press_default_press_mode_id
            FOREIGN KEY (default_press_mode_id) REFERENCES press_modes(press_mode_id) ON DELETE SET NULL;
        END IF;
    END IF;
END
$$;
"""

    # Power Limit
    press_mode_power_limit = """
CREATE TABLE IF NOT EXISTS press_mode_power_limit (
    press_mode_id SMALLINT,
    row_num SMALLINT NOT NULL,
    force_value FLOAT,
    speed_value FLOAT,
    PRIMARY KEY (press_mode_id, row_num),
    FOREIGN KEY (press_mode_id) REFERENCES press_modes(press_mode_id) ON DELETE CASCADE
);
"""

    die_assembly = """
    CREATE TABLE IF NOT EXISTS die_assemblies (
        id                  SERIAL PRIMARY KEY,
        name                JSON NOT NULL,
        die_type_id         INT NOT NULL,
        is_obsolete         BOOL DEFAULT FALSE,
        --
        created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
        updated_at          TIMESTAMP DEFAULT NULL,
        obsolete_at         TIMESTAMP DEFAULT NULL,
        --
        FOREIGN KEY (die_type_id) REFERENCES die_types(id) ON DELETE RESTRICT
    );
    """

    # Die flat
    die = """
CREATE TABLE IF NOT EXISTS dies (
    --
    -- AUTOFILL
    --
    id                      SERIAL PRIMARY KEY,
    die_assembly_id         INT DEFAULT NULL,
    -- 
    -- mandatory parameters
    -- 
    name                    JSON NOT NULL,
    die_type_id             INT NOT NULL,
    -- 
    die_template_file_name  VARCHAR(1023) DEFAULT '',
    inventory_number        VARCHAR(127) DEFAULT '',
    --
    is_matching_as_top      BOOL NOT NULL DEFAULT FALSE,
    is_matching_as_bottom   BOOL NOT NULL DEFAULT FALSE,
    is_matching_as_minus_y  BOOL NOT NULL DEFAULT FALSE,
    is_matching_as_plus_y   BOOL NOT NULL DEFAULT FALSE,
    -- 
    dimensions              VARCHAR(4095) DEFAULT '',
    --
    is_obsolete             BOOL NOT NULL DEFAULT FALSE,
    --
    created_at              TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMP DEFAULT NULL,
    obsolete_at             TIMESTAMP DEFAULT NULL,
    -- 
    FOREIGN KEY (die_assembly_id) REFERENCES die_assemblies(id) ON DELETE RESTRICT,
    FOREIGN KEY (die_type_id) REFERENCES die_types(id) ON DELETE RESTRICT
);
"""

    press_die_map = """
CREATE TABLE IF NOT EXISTS press_die_map (
    press_id INT NOT NULL,
    die_id   INT NOT NULL,
    PRIMARY KEY (press_id, die_id),
    FOREIGN KEY (press_id) REFERENCES presses(press_id) ON DELETE CASCADE,
    FOREIGN KEY (die_id) REFERENCES dies(id) ON DELETE CASCADE
);
"""

    die_assembly_die_map = """
CREATE TABLE IF NOT EXISTS die_assembly_die_map (
    die_assembly_id INT NOT NULL,
    die_id          INT NOT NULL,
    PRIMARY KEY (die_assembly_id, die_id),
    FOREIGN KEY (die_assembly_id) REFERENCES die_assemblies(id) ON DELETE CASCADE,
    FOREIGN KEY (die_id) REFERENCES dies(id) ON DELETE CASCADE
);
"""

    die_top_flat = """
-- Create the view 'die_top_flat' with rows where 'die_type_id' = 'flat'
CREATE VIEW die_top_flat AS
SELECT *
FROM dies
WHERE die_type_id = 1 AND is_matching_as_top = TRUE
ORDER BY name ASC;
"""

    die_top_v_die = """
-- Create the view 'die_top_v_die' with rows where 'die_type_id' = 'v_die'
CREATE VIEW die_top_v_die AS
SELECT *
FROM dies
WHERE die_type_id = 2 AND is_matching_as_top = TRUE
ORDER BY name ASC;
"""

    die_top_rounding = """
-- Create the view 'die_top_rounding' with rows where 'die_type_id' = 'rounding'
CREATE VIEW die_top_rounding AS
SELECT *
FROM dies
WHERE die_type_id = 4 AND is_matching_as_top = TRUE
ORDER BY name ASC;
"""

    die_bottom_flat = """
-- Create the view 'die_bottom_flat' with rows where 'die_type_id' = 'flat'
CREATE VIEW die_bottom_flat AS
SELECT *
FROM dies
WHERE die_type_id = 1 AND is_matching_as_bottom = TRUE
ORDER BY name ASC;
"""

    die_bottom_v_die = """
-- Create the view 'die_bottom_v_die' with rows where 'die_type_id' = 'v_die'
CREATE VIEW die_bottom_v_die AS
SELECT *
FROM dies
WHERE die_type_id = 2 AND is_matching_as_bottom = TRUE
ORDER BY name ASC;
"""

    die_bottom_rounding = """
-- Create the view 'die_bottom_rounding' with rows where 'die_type_id' = 'rounding'
CREATE VIEW die_bottom_rounding AS
SELECT *
FROM dies
WHERE die_type_id = 4 AND is_matching_as_bottom = TRUE
ORDER BY name ASC;
"""

    die_assembly_flat = """
-- Create the view 'die_assembly_flat' with rows where 'die_type_id' = 'flat'
CREATE VIEW die_assembly_flat AS
SELECT *
FROM die_assemblies
WHERE die_type_id = 1
ORDER BY name ASC;
"""

    die_assembly_v_die = """
-- Create the view 'die_assembly_v_die' with rows where 'die_type_id' = 'v_die'
CREATE VIEW die_assembly_v_die AS
SELECT *
FROM die_assemblies
WHERE die_type_id = 2
ORDER BY name ASC;
"""

    die_assembly_rounding = """
-- Create the view 'die_assembly_rounding' with rows where 'die_type_id' = 'rounding'
CREATE VIEW die_assembly_rounding AS
SELECT *
FROM die_assemblies
WHERE die_type_id = 4
ORDER BY name ASC;
"""

    die_assembly_gfm_die = """
-- Create the view 'die_assembly_gfm_die' with rows where 'die_type_id' = 'gfm_die'
CREATE VIEW die_assembly_gfm_die AS
SELECT *
FROM die_assemblies
WHERE die_type_id = 3
ORDER BY name ASC;
"""

    feed_direction = """
CREATE TABLE IF NOT EXISTS feed_direction (
    feed_direction_id   SMALLSERIAL PRIMARY KEY,
    feed_direction_name VARCHAR(1023) UNIQUE
);
"""

    operation_order = """
CREATE TABLE IF NOT EXISTS operation_order (
    operation_id BIGSERIAL,
    process_version_id INT,
    row_id INT NOT NULL,
    operation_type_id SMALLINT,
    PRIMARY KEY (operation_id),
    FOREIGN KEY (process_version_id) REFERENCES process_versions(process_version_id) ON DELETE CASCADE,
    FOREIGN KEY (operation_type_id) REFERENCES operations_library(type_id) ON DELETE RESTRICT
);
"""

    process_versions_changes = """
CREATE TABLE IF NOT EXISTS process_versions_changes (
    process_version_id BIGINT,
    operation_id BIGINT,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (process_version_id) REFERENCES process_versions(process_version_id) ON DELETE CASCADE,
    FOREIGN KEY (operation_id) REFERENCES operation_order(operation_id) ON DELETE CASCADE
);
"""

    time_between_operations = """
CREATE TABLE IF NOT EXISTS time_between_operations (
    first_operation_type_id SMALLINT,
    second_operation_type_id SMALLINT,
    press_id SMALLINT,
    time_mean FLOAT,
    time_sigma FLOAT,

    PRIMARY KEY (first_operation_type_id, second_operation_type_id, press_id),

    CONSTRAINT fk_time_first_type_id_operations_library
        FOREIGN KEY (first_operation_type_id)
            REFERENCES operations_library(type_id) ON DELETE CASCADE,

    CONSTRAINT fk_time_second_type_id_operations_library
        FOREIGN KEY (second_operation_type_id)
            REFERENCES operations_library(type_id) ON DELETE CASCADE,

    CONSTRAINT fk_time_press_id
        FOREIGN KEY (press_id)
            REFERENCES presses(press_id) ON DELETE CASCADE
);
"""

    # TODO: remove 'name' column. 'name' column is left for compatibility with forgelabClient / Simulation widget.
    servers = """
CREATE TABLE IF NOT EXISTS public.servers (
    id                  SERIAL,
    is_active           BOOL DEFAULT FALSE,
    type                server_type_enum NOT NULL,
    name                VARCHAR(255) NOT NULL,
    hostname            VARCHAR(255) NOT NULL,
    dns_domain          VARCHAR(255) DEFAULT NULL,
    ip                  VARCHAR(63) NOT NULL,
    port_number         SMALLINT,
    login_name          VARCHAR(63),
    login_password      VARCHAR(63),
    version             VARCHAR(63) NOT NULL,
    time_started        TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    time_updated        TIMESTAMP WITHOUT TIME ZONE DEFAULT NULL,
    time_finished       TIMESTAMP WITHOUT TIME ZONE DEFAULT NULL,
    process_version_id  BIGINT,
    projects_dir        VARCHAR(2047) DEFAULT '',  -- Directory name of the projects, both local and public
    local_dir           VARCHAR(2047) DEFAULT '',  -- To be assigned by the server
    public_dir          VARCHAR(2047) DEFAULT '',
    software_root_dir   VARCHAR(2047) DEFAULT '',  -- PATH of the Server's running code
    data_files_dies     VARCHAR(2047) DEFAULT '',  -- PATH of the Server's root dir of Data files
    data_files_materials VARCHAR(2047) DEFAULT '',  -- PATH of the Server's root dir of Materials zip-files
    data_files_operations VARCHAR(2047) DEFAULT '',  -- PATH of the Server's root dir of Operations zip-files
    nas                 VARCHAR(2047) DEFAULT '',  -- PATH to the NAS, used by the Server

    max_threads_count   SMALLINT,
    cpu_performance     FLOAT,  -- Performance of standard test case per 1 cpu
    cpu_count           SMALLINT,
    ram_free_size_gb    FLOAT,
    hdd_free_size_gb    FLOAT,

    notify_timeout      FLOAT DEFAULT NULL,
    timeout_query_missed_tasks        FLOAT DEFAULT NULL,
    queue_timeout       FLOAT DEFAULT NULL,
    notify_channel      VARCHAR(255) DEFAULT NULL,
    timeout_counter     SMALLINT DEFAULT 0,
    

    CONSTRAINT pk_servers_id PRIMARY KEY (id),
    CONSTRAINT uk_servers_1 UNIQUE (type, hostname, name),
    CONSTRAINT fk_servers_process_version_id FOREIGN KEY (process_version_id)
        REFERENCES public.process_versions (process_version_id) MATCH SIMPLE
        ON UPDATE CASCADE
        ON DELETE SET DEFAULT
);
"""

    servers_versions_compatibility = """
CREATE TABLE IF NOT EXISTS servers_versions_compatibility (
    type_a      server_type_enum NOT NULL,
    version_a   VARCHAR(255) NOT NULL,

    type_b      server_type_enum NOT NULL,
    version_b   VARCHAR(255) NOT NULL,

    CONSTRAINT pk_servers_versions_compatibility PRIMARY KEY (type_a, version_a, type_b, version_b)
);
"""

    process_versions_ALTER_1 = """
ALTER TABLE process_versions ADD
FOREIGN KEY (simulation_server_id) REFERENCES servers(id) ON UPDATE CASCADE ON DELETE SET DEFAULT;
"""

    physical_machines = """
CREATE TABLE IF NOT EXISTS physical_machines (
    phm_id                      SMALLSERIAL,
    name                        VARCHAR(17) NOT NULL,  -- NetBIOS name of the virtual machine
    hard_drives_list            VARCHAR(511) NOT NULL,  -- List of hard drives and size [GB] separated by '|'
    cpu_count                   SMALLINT NOT NULL,  -- Number of physical CPUs
    core_count                  SMALLINT NOT NULL,  -- Total number of CPU cores
    processor_architecture      VARCHAR(63) NOT NULL,  -- CPU architecture
    ram_size                    INT NOT NULL,  -- RAM size in GB
    notes                       VARCHAR(511) NOT NULL DEFAULT '',  -- Notes about the physical machine

    PRIMARY KEY (phm_id)
);
"""

    server_pre_main = """
CREATE TABLE IF NOT EXISTS server_pre_main (

    ppt_file_name               VARCHAR(4096) DEFAULT NULL,  -- Network path to directory with PPT-file
    is_ready                    BOOL DEFAULT FALSE,      -- TRUE - calculations are correct

    -- ********************************* NOT NULL TABLE HEAD ***********************************

    execution_order             SMALLINT NOT NULL,  -- Order of execution of the operation
    execution_id                BIGSERIAL PRIMARY KEY,  -- Unique identifier for each execution

    -- ********************************* NOT NULL FOREIGN KEYs **********************************

    operation_id                BIGINT,
    process_version_id          BIGINT,
    type_id                     SMALLINT,  -- Type of the operation
    material_id                 INT,  -- Material ID, Foreign key

    -- ********************************* EVALUATED ************************************

    initial_height              DOUBLE PRECISION DEFAULT NULL,  -- Initial height of the billet
    initial_width               DOUBLE PRECISION DEFAULT NULL,  -- Initial width of the billet
    initial_length              DOUBLE PRECISION DEFAULT NULL,  -- Initial length of the billet

    final_height                DOUBLE PRECISION DEFAULT NULL,  -- Final height of the billet
    final_width                 DOUBLE PRECISION DEFAULT NULL,  -- Final width of the billet
    final_length                DOUBLE PRECISION DEFAULT NULL,  -- Final length of the billet

    equivalent_diameter         DOUBLE PRECISION DEFAULT NULL,  -- Final equivalent diameter of the billet

    -- ********************************* NOT NULL TIMESTAMP ************************************

    last_modified               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- Last update time                 

    -- ********************************* FOREIGN KEYs ALLOW NULL ********************************

    furnace_class_id            SMALLINT DEFAULT NULL,  -- Foreign Key - Furnace Class ID

    press_id                    INT DEFAULT NULL,  -- Press ID
    press_mode_id               INT DEFAULT NULL,  -- Press mode ID      

    die_assembly_id             INT DEFAULT NULL,  -- Die assembly ID
    top_die_id                  INT DEFAULT NULL,  -- Die top ID
    bottom_die_id               INT DEFAULT NULL,  -- Die bottom ID
    plus_y_die_id               INT DEFAULT NULL,  -- Die +Y ID
    minus_y_die_id              INT DEFAULT NULL,  -- Die -Y ID

    feed_direction_id           SMALLINT DEFAULT NULL,  -- Feed direction ID
    feed_direction_name         VARCHAR(1023) DEFAULT '',  -- ==>, <== (<==> - is not allowed) 
    feed_type_id                SMALLINT DEFAULT NULL,  -- type_id of used Feed operation

    -- ********************************* INPUT CONTROL ********************************************

    control_duration                    DOUBLE PRECISION DEFAULT NULL,  -- Duration input

    control_temperature_furnace_initial DOUBLE PRECISION DEFAULT NULL,  -- Initial Furnace temperature
    control_temperature_furnace_final   DOUBLE PRECISION DEFAULT NULL,  -- Final Furnace temperature

    -- *********************************** EVALUATED **********************************************

    operation_specific_parameters   JSONB,   -- Dictionary/JSON with unique parameters calculated by Pre Server 

    mesh_elements               SMALLINT DEFAULT NULL,   -- Number of mesh elements across width of billet

    operation_type_new          VARCHAR(63) DEFAULT '',  -- Operation type Name ('upsetting', 'axial_prolongation', 
                                                         -- 'radial_prolongation', 'full_die', 'hot_cutting')
    stage_name                  VARCHAR(63) DEFAULT '',  -- Forming stage name, as defined in 'operation_type_id_36'

    operation_type              VARCHAR(63) DEFAULT '',  -- Compatibility with ForgeLab v.1
    step_control                VARCHAR(63) DEFAULT '',  -- Compatibility with ForgeLab v.1
    deformation_control         VARCHAR(63) DEFAULT '',  -- Compatibility with ForgeLab v.1
    k1                          VARCHAR(63) DEFAULT '',  -- Compatibility with ForgeLab v.1

    deformation_type            deformation_type_enum DEFAULT NULL, -- Type of the deformation
    press                       VARCHAR(63) DEFAULT '',  -- Compatibility with ForgeLab v.1

    is_press_in_automatic_mode  BOOL DEFAULT FALSE,      -- Is forging press in Automatic or Manual mode 
                                                         -- Automatic mode: first feed is manual controlled, 
                                                         -- then next feeds are automatic controlled except last feed 

    feed_first                  DOUBLE PRECISION DEFAULT NULL,  -- Nominal Feed first, entered by User for whole process
    feed_middle                 DOUBLE PRECISION DEFAULT NULL,  -- Nominal Feed middle, entered by User for whole process
    feed_last                   DOUBLE PRECISION DEFAULT NULL,  -- Nominal Feed last, entered by User for whole process
    
    -- Feed length and feed count calculated by Pre Server.
    -- It is based on user input (feed_first, ..., feed_last) and actual circumstances,
    -- e.g. initial billet length, feed mode (either manual or automatic) and if last feed controlled or not. 
    
    simulation_feed_first       DOUBLE PRECISION DEFAULT 0.0,  
    simulation_feed_middle      DOUBLE PRECISION DEFAULT 0.0,
    simulation_feed_before_last DOUBLE PRECISION DEFAULT 0.0,
    simulation_feed_last        DOUBLE PRECISION DEFAULT 0.0,

    simulation_feed_first_count         SMALLINT DEFAULT 0,  
    simulation_feed_middle_count        SMALLINT DEFAULT 0,
    simulation_feed_before_last_count   SMALLINT DEFAULT 0,
    simulation_feed_last_count          SMALLINT DEFAULT 0,

    relative_deformation        DOUBLE PRECISION DEFAULT NULL,  -- Compatibility with ForgeLab v.1
    penetration                 DOUBLE PRECISION DEFAULT NULL,  -- Penetration of the die
    num_of_bites                SMALLINT DEFAULT NULL,          -- Number of bites
    angle                       DOUBLE PRECISION DEFAULT NULL,  -- Rotation angle of the die
    speed                       DOUBLE PRECISION DEFAULT NULL,  -- Speed of the operation

    -- *********************************** BITE **********************************************

    idle_stroke                 DOUBLE PRECISION DEFAULT NULL,  -- Normal idle stroke path
    working_approaching_stroke  DOUBLE PRECISION DEFAULT NULL,  -- Normal approaching distance
    working_stroke              DOUBLE PRECISION DEFAULT NULL,  -- Max temperature of the billet
    back_stroke                 DOUBLE PRECISION DEFAULT NULL,  -- Max temperature of the billet

    working_stroke_ratio_top_die    DOUBLE PRECISION DEFAULT NULL,  -- 0.5 for flat die
    working_stroke_ratio_bottom_die DOUBLE PRECISION DEFAULT NULL,  -- 0.5 for flat die

    open_die_height_before_idle_stroke          DOUBLE PRECISION DEFAULT NULL,
    open_die_height_max_before_working_stroke   DOUBLE PRECISION DEFAULT NULL,
    open_die_height_min_after_working_stroke    DOUBLE PRECISION DEFAULT NULL,

    -- *********************************** PRESS **********************************************

    top_die_assembly_height     DOUBLE PRECISION DEFAULT NULL,  -- Max temperature of the billet
    bottom_die_assembly_height  DOUBLE PRECISION DEFAULT NULL,  -- Max temperature of the billet

    -- *********************************** TIME **********************************************

    time_bite_idle_down_stroke  DOUBLE PRECISION DEFAULT NULL,  -- Bite idle down stroke time
    time_bite_idle_back_stroke  DOUBLE PRECISION DEFAULT NULL,  -- Bite idle back stroke time
    time_between_bites          DOUBLE PRECISION DEFAULT NULL,  -- Bite total idle time
    time_bite_working           DOUBLE PRECISION DEFAULT NULL,  -- Bite working time
    cycle_time                  DOUBLE PRECISION DEFAULT NULL,  -- Bite cycle time

    time_pass_forging           DOUBLE PRECISION DEFAULT NULL,  -- Pass forging time
    time_before_pass            DOUBLE PRECISION DEFAULT NULL,  -- Dwell time before pass
    time_before_pass_minutes    DOUBLE PRECISION DEFAULT NULL,  -- Dwell time before pass [MINUTES]
    operation_time              DOUBLE PRECISION DEFAULT NULL,  -- Total pass time

    total_time                  DOUBLE PRECISION DEFAULT NULL,  -- Compatibility with ForgeLab v.1
    total_time_minutes          DOUBLE PRECISION DEFAULT NULL,  -- Compatibility with ForgeLab v.1 [MINUTES]

    -- *********************************** BILLET **********************************************

    max_temperature             DOUBLE PRECISION DEFAULT NULL,  -- Max temperature of the billet

    initial_polygon             BYTEA DEFAULT NULL,  -- Initial 2D polygon of the billet cross-section
    final_polygon               BYTEA DEFAULT NULL,  -- Final 2D polygon of the billet cross-section

    initial_basis               FLOAT8[3][3] DEFAULT '{{0,0,0},{0,0,0},{0,0,0}}',  -- Initial Local Coordinate System (Basis) of the Billet
    final_basis                 FLOAT8[3][3] DEFAULT '{{0,0,0},{0,0,0},{0,0,0}}',  -- Final Local Coordinate System (Basis) of the Billet

    initial_3d_stl              BYTEA DEFAULT NULL,  -- Initial 3D object in binary STL format
    final_3d_stl                BYTEA DEFAULT NULL,  -- Final 3D object in binary STL format

    scrap_rate                  DOUBLE PRECISION DEFAULT NULL,  -- Scrap rate of Weight loss

    initial_weight              DOUBLE PRECISION DEFAULT NULL,  -- Initial Weight of the billet
    final_weight                DOUBLE PRECISION DEFAULT NULL,  -- Final Weight of the billet

    volume_initial              DOUBLE PRECISION DEFAULT NULL,  -- Initial Volume of the billet
    volume_final                DOUBLE PRECISION DEFAULT NULL,  -- Final Volume of the billet

    initial_cross_section_area  DOUBLE PRECISION DEFAULT NULL,  -- Initial Cross section area of the billet
    final_cross_section_area    DOUBLE PRECISION DEFAULT NULL,  -- Final Cross section area of the billet

    initial_surface_area        DOUBLE PRECISION DEFAULT NULL,  -- Initial Surface area of the billet
    final_surface_area          DOUBLE PRECISION DEFAULT NULL,  -- Final Surface area of the billet

    initial_height_to_width_ratio   DOUBLE PRECISION DEFAULT NULL,  -- Compatibility with ForgeLab v.1
    final_height_to_width_ratio     DOUBLE PRECISION DEFAULT NULL,  -- Compatibility with ForgeLab v.1

    initial_horizontal_face         DOUBLE PRECISION DEFAULT NULL,  -- Compatibility with ForgeLab v.1
    final_horizontal_face           DOUBLE PRECISION DEFAULT NULL,  -- Compatibility with ForgeLab v.1

    initial_vertical_face           DOUBLE PRECISION DEFAULT NULL,  -- Compatibility with ForgeLab v.1
    final_vertical_face             DOUBLE PRECISION DEFAULT NULL,  -- Compatibility with ForgeLab v.1

    initial_length_of_contact       DOUBLE PRECISION DEFAULT NULL,  -- Compatibility with ForgeLab v.1
    final_length_of_contact         DOUBLE PRECISION DEFAULT NULL,  -- Compatibility with ForgeLab v.1

    initial_width_of_contact        DOUBLE PRECISION DEFAULT NULL,  -- Compatibility with ForgeLab v.1
    final_width_of_contact          DOUBLE PRECISION DEFAULT NULL,  -- Compatibility with ForgeLab v.1

    elongation_channel_a            DOUBLE PRECISION DEFAULT NULL,  -- Effective strain Increment below beta
    elongation_channel_b            DOUBLE PRECISION DEFAULT NULL,  -- Effective strain Increment above beta

    strain_height                   DOUBLE PRECISION DEFAULT NULL,  -- True strain increment for height
    strain_width                    DOUBLE PRECISION DEFAULT NULL,  -- True strain increment for width
    strain_length                   DOUBLE PRECISION DEFAULT NULL,  -- True strain increment for length

    strain_accumulated_channel_a    DOUBLE PRECISION DEFAULT NULL,  -- Total effective strain below beta
    strain_accumulated_channel_b    DOUBLE PRECISION DEFAULT NULL,  -- Total effective strain above beta

    -- ********************************** PREVIEW CALCULATIONS ****************************************

    parent_simulation_status        simulation_status_enum DEFAULT 'stop',
    simulation_expected_duration_days   DOUBLE PRECISION DEFAULT 0,  -- Expected duration of the simulation in days

    -- *********************************** SIMULATION STATUS ******************************************

    simulation_status               simulation_status_enum DEFAULT 'stop',
    simulation_server_retry_count   INT DEFAULT 0,
    simulation_server_worker_id     BIGINT DEFAULT 0,
    simulation_time_started         TIMESTAMP DEFAULT NULL,
    simulation_time_finished        TIMESTAMP DEFAULT NULL,
    simulation_starting_step        INT DEFAULT NULL,
    simulation_finishing_step       INT DEFAULT NULL,
    operation_dir_name              VARCHAR(255) DEFAULT NULL,  -- Relative directory name of the operation
    billet_file_sub_operation_extract_relative_path VARCHAR(2047) DEFAULT NULL,  -- Relative path to the KEY-file of billet
    sub_operation_relative_path     VARCHAR(255) DEFAULT NULL,

    post_server_id                  SMALLINT DEFAULT NULL,  -- The id of the post server that is running the ppt generation
    post_status                     post_status_enum DEFAULT 'stop'::post_status_enum,
    post_time_started               TIMESTAMP DEFAULT NULL,
    post_time_finished              TIMESTAMP DEFAULT NULL,
    post_images_abs_path            VARCHAR(2047) DEFAULT NULL,
    post_pptx_abs_path              VARCHAR(2047) DEFAULT NULL,

    -- *********************************** UNIQUE KEYS *******************************************

    CONSTRAINT uk_server_pre_main_1 UNIQUE (process_version_id, execution_order),
    CONSTRAINT uk_server_pre_main_2 UNIQUE (operation_id),

    -- *********************************** FOREIGN KEYS ******************************************

    CONSTRAINT fk_server_pre_main_operation_id
        FOREIGN KEY (operation_id)
        REFERENCES operations(id) ON DELETE CASCADE,

    CONSTRAINT fk_server_pre_main_process_version_id_process_versions
        FOREIGN KEY (process_version_id)
        REFERENCES process_versions(process_version_id) ON DELETE CASCADE,

    CONSTRAINT fk_server_pre_main_type_id
        FOREIGN KEY (type_id)
        REFERENCES operations_library(type_id) ON UPDATE CASCADE ON DELETE CASCADE,

    CONSTRAINT fk_server_pre_main_material_id
        FOREIGN KEY (material_id)
        REFERENCES materials(material_id) ON DELETE SET DEFAULT,

    CONSTRAINT fk_server_pre_main_press_id
        FOREIGN KEY (press_id)
        REFERENCES presses(press_id) ON DELETE SET DEFAULT,

    CONSTRAINT fk_server_pre_main_press_mode_id
        FOREIGN KEY (press_mode_id)
        REFERENCES press_modes(press_mode_id) ON DELETE SET DEFAULT,

    CONSTRAINT fk_server_pre_main_die_assembly_id
        FOREIGN KEY (die_assembly_id)
        REFERENCES die_assemblies(id) ON DELETE SET DEFAULT,

    CONSTRAINT fk_server_pre_main_die_top_die_id
        FOREIGN KEY (top_die_id)
        REFERENCES dies(id) ON DELETE SET DEFAULT,

    CONSTRAINT fk_server_pre_main_die_bottom_die_id
        FOREIGN KEY (bottom_die_id)
        REFERENCES dies(id) ON DELETE SET DEFAULT,

    CONSTRAINT fk_server_pre_main_feed_direction_id
        FOREIGN KEY (feed_direction_id)
        REFERENCES feed_direction(feed_direction_id) ON DELETE SET DEFAULT
);
"""

    post_operations = """
CREATE TABLE IF NOT EXISTS post_operations (

    -- ********************************* NOT NULL FOREIGN & PRIMARY KEY **********************************

    execution_id                BIGINT PRIMARY KEY,  -- Unique identifier for each execution

    -- *********************************** FOREIGN KEY ALLOWS NULL ******************************************

    press_mode_id               INT NOT NULL DEFAULT NULL,  -- Compatibility with ForgeLab v.1

    -- ********************************* NOT NULL PRIMARY KEY **********************************

    ppt_file_name               VARCHAR(4096) DEFAULT '',  -- Network path to directory with PPT-file

    feed_table                  VARCHAR(63) DEFAULT '',  -- Compatibility with ForgeLab v.1
    feed_first                  DOUBLE PRECISION DEFAULT NULL,  -- Feed first tail
    feed_middle                 DOUBLE PRECISION DEFAULT NULL,  -- Feed middle tail
    feed_last                   DOUBLE PRECISION DEFAULT NULL,  -- Feed end tail

    relative_deformation        DOUBLE PRECISION DEFAULT NULL,  -- Compatibility with ForgeLab v.1
    penetration                 DOUBLE PRECISION DEFAULT NULL,  -- Penetration of the die
    num_of_bites                SMALLINT DEFAULT NULL,  -- Number of bites
    angle                       DOUBLE PRECISION DEFAULT NULL,  -- Rotation angle of the die
    speed                       DOUBLE PRECISION DEFAULT NULL,  -- Speed of the operation

    max_temperature             DOUBLE PRECISION DEFAULT NULL,  -- Max temperature of the billet

    time_bite_idle_down_stroke  DOUBLE PRECISION DEFAULT NULL,  -- Bite idle down stroke time
    time_bite_idle_back_stroke  DOUBLE PRECISION DEFAULT NULL,  -- Bite idle back stroke time
    time_between_bites          DOUBLE PRECISION DEFAULT NULL,  -- Bite total idle time
    time_bite_working           DOUBLE PRECISION DEFAULT NULL,  -- Bite working time
    cycle_time                  DOUBLE PRECISION DEFAULT NULL,  -- Bite cycle time

    time_pass_forging           DOUBLE PRECISION DEFAULT NULL,  -- Pass forging time
    time_before_pass            DOUBLE PRECISION DEFAULT NULL,  -- Dwell time before pass
    time_before_pass_minutes    DOUBLE PRECISION DEFAULT NULL,  -- Dwell time before pass [MINUTES]
    operation_time              DOUBLE PRECISION DEFAULT NULL,  -- Total pass time

    total_time                  DOUBLE PRECISION DEFAULT NULL,  -- Compatibility with ForgeLab v.1
    total_time_minutes          DOUBLE PRECISION DEFAULT NULL,  -- Compatibility with ForgeLab v.1 [MINUTES]

    initial_polygon             BYTEA DEFAULT NULL,  -- Initial 2D polygon of the billet cross-section
    final_polygon               BYTEA DEFAULT NULL,  -- Final 2D polygon of the billet cross-section

    initial_3d_stl              BYTEA DEFAULT NULL,  -- Initial 3D object in binary STL format
    final_3d_stl                BYTEA DEFAULT NULL,  -- Final 3D object in binary STL format

    scrap_rate                  DOUBLE PRECISION DEFAULT NULL,  -- Scrap rate of Weight loss

    initial_weight              DOUBLE PRECISION DEFAULT NULL,  -- Initial Weight of the billet
    final_weight                DOUBLE PRECISION DEFAULT NULL,  -- Final Weight of the billet

    volume_initial              DOUBLE PRECISION DEFAULT NULL,  -- Initial Volume of the billet
    volume_final                DOUBLE PRECISION DEFAULT NULL,  -- Final Volume of the billet

    initial_height              DOUBLE PRECISION DEFAULT NULL,  -- Initial height of the billet
    initial_width               DOUBLE PRECISION DEFAULT NULL,  -- Initial width of the billet
    initial_length              DOUBLE PRECISION DEFAULT NULL,  -- Initial length of the billet

    final_height                DOUBLE PRECISION DEFAULT NULL,  -- Final height of the billet
    final_width                 DOUBLE PRECISION DEFAULT NULL,  -- Final width of the billet
    final_length                DOUBLE PRECISION DEFAULT NULL,  -- Final length of the billet

    equivalent_diameter         DOUBLE PRECISION DEFAULT NULL,  -- Final equivalent diameter of the billet

    initial_cross_section_area  DOUBLE PRECISION DEFAULT NULL,  -- Initial Cross section area of the billet
    final_cross_section_area    DOUBLE PRECISION DEFAULT NULL,  -- Final Cross section area of the billet

    initial_surface_area        DOUBLE PRECISION DEFAULT NULL,  -- Initial Surface area of the billet
    final_surface_area          DOUBLE PRECISION DEFAULT NULL,  -- Final Surface area of the billet

    initial_height_to_width_ratio   DOUBLE PRECISION DEFAULT NULL,  -- Compatibility with ForgeLab v.1
    final_height_to_width_ratio     DOUBLE PRECISION DEFAULT NULL,  -- Compatibility with ForgeLab v.1

    initial_horizontal_face         DOUBLE PRECISION DEFAULT NULL,  -- Compatibility with ForgeLab v.1
    final_horizontal_face           DOUBLE PRECISION DEFAULT NULL,  -- Compatibility with ForgeLab v.1

    initial_vertical_face           DOUBLE PRECISION DEFAULT NULL,  -- Compatibility with ForgeLab v.1
    final_vertical_face             DOUBLE PRECISION DEFAULT NULL,  -- Compatibility with ForgeLab v.1

    initial_length_of_contact       DOUBLE PRECISION DEFAULT NULL,  -- Compatibility with ForgeLab v.1
    final_length_of_contact         DOUBLE PRECISION DEFAULT NULL,  -- Compatibility with ForgeLab v.1

    initial_width_of_contact        DOUBLE PRECISION DEFAULT NULL,  -- Compatibility with ForgeLab v.1
    final_width_of_contact          DOUBLE PRECISION DEFAULT NULL,  -- Compatibility with ForgeLab v.1

    elongation_channel_a            DOUBLE PRECISION DEFAULT NULL,  -- Effective strain Increment below beta
    elongation_channel_b            DOUBLE PRECISION DEFAULT NULL,  -- Effective strain Increment above beta

    strain_height                   DOUBLE PRECISION DEFAULT NULL,  -- True strain increment for height
    strain_width                    DOUBLE PRECISION DEFAULT NULL,  -- True strain increment for width
    strain_length                   DOUBLE PRECISION DEFAULT NULL,  -- True strain increment for length

    strain_accumulated_channel_a    DOUBLE PRECISION DEFAULT NULL,  -- Total effective strain below beta
    strain_accumulated_channel_b    DOUBLE PRECISION DEFAULT NULL,  -- Total effective strain above beta

    -- *********************************** SIMULATION STATUS ******************************************

    parent_simulation_status        simulation_status_enum DEFAULT 'stop',

    simulation_status               simulation_status_enum DEFAULT 'stop',
    simulation_server_retry_count   INT DEFAULT 0,
    simulation_server_worker_id     BIGINT DEFAULT 0, -- Worker GenerateImagesProcess PID 
    simulation_path                 VARCHAR(2047) DEFAULT NULL,
    simulation_time_started         TIMESTAMP DEFAULT NULL,
    simulation_time_finished        TIMESTAMP DEFAULT NULL,
    simulation_starting_step        INT DEFAULT NULL,
    simulation_finishing_step       INT DEFAULT NULL,
    simulation_expected_duration_days   DOUBLE PRECISION DEFAULT 0,  -- Expected duration of the simulation in days

    print_status                    simulation_status_enum DEFAULT 'stop',
    print_server_retry_count        INT DEFAULT 0,
    print_server_worker_id          BIGINT DEFAULT NULL, -- Worker GeneratePptProcess PID 
    print_path                      VARCHAR(2047) DEFAULT NULL,
    print_time_started              TIMESTAMP DEFAULT NULL,
    print_time_finished             TIMESTAMP DEFAULT NULL,

    -- *********************************** FOREIGN KEYS ******************************************

    CONSTRAINT fk_post_operations_execution_id
        FOREIGN KEY (execution_id)
        REFERENCES server_pre_main(execution_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CONSTRAINT fk_post_operations_press_mode_id
        FOREIGN KEY (press_mode_id)
        REFERENCES press_modes(press_mode_id)
        ON DELETE SET DEFAULT
        ON UPDATE CASCADE
);
"""

    post_bites = """
CREATE TABLE IF NOT EXISTS bites (

    bite_id                     BIGINT PRIMARY KEY,
    bite_order                  SMALLINT,
    execution_id                BIGINT,

    -- *********************************** FOREIGN KEY ALLOWS NULL ******************************************

    press_mode_id               INT NOT NULL DEFAULT NULL,  -- Compatibility with ForgeLab v.1

    -- *********************************** EVALUATED **********************************************

    ppt_file_name               VARCHAR(4096) DEFAULT '',  -- Network path to directory with PPT-file

    feed                        VARCHAR(63) DEFAULT '',  -- Compatibility with ForgeLab v.1

    relative_deformation        DOUBLE PRECISION DEFAULT NULL,  -- Compatibility with ForgeLab v.1
    penetration                 DOUBLE PRECISION DEFAULT NULL,  -- Penetration of the die
    num_of_bites                SMALLINT DEFAULT NULL,  -- Number of bites
    angle                       DOUBLE PRECISION DEFAULT NULL,  -- Rotation angle of the die
    speed                       DOUBLE PRECISION DEFAULT NULL,  -- Speed of the operation

    max_temperature             DOUBLE PRECISION DEFAULT NULL,  -- Max temperature of the billet

    time_bite_idle_down_stroke  DOUBLE PRECISION DEFAULT NULL,  -- Bite idle down stroke time
    time_bite_idle_back_stroke  DOUBLE PRECISION DEFAULT NULL,  -- Bite idle back stroke time
    time_between_bites          DOUBLE PRECISION DEFAULT NULL,  -- Bite total idle time
    time_bite_working           DOUBLE PRECISION DEFAULT NULL,  -- Bite working time
    cycle_time                  DOUBLE PRECISION DEFAULT NULL,  -- Bite cycle time

    time_pass_forging           DOUBLE PRECISION DEFAULT NULL,  -- Pass forging time
    time_before_pass            DOUBLE PRECISION DEFAULT NULL,  -- Dwell time before pass
    time_before_pass_minutes    DOUBLE PRECISION DEFAULT NULL,  -- Dwell time before pass [MINUTES]
    operation_time              DOUBLE PRECISION DEFAULT NULL,  -- Total pass time

    total_time                  DOUBLE PRECISION DEFAULT NULL,  -- Compatibility with ForgeLab v.1
    total_time_minutes          DOUBLE PRECISION DEFAULT NULL,  -- Compatibility with ForgeLab v.1 [MINUTES]

    scrap_rate                  DOUBLE PRECISION DEFAULT NULL,  -- Scrap rate of Weight loss

    initial_weight              DOUBLE PRECISION DEFAULT NULL,  -- Initial Weight of the billet
    final_weight                DOUBLE PRECISION DEFAULT NULL,  -- Final Weight of the billet

    volume_initial              DOUBLE PRECISION DEFAULT NULL,  -- Initial Volume of the billet
    volume_final                DOUBLE PRECISION DEFAULT NULL,  -- Final Volume of the billet

    initial_height              DOUBLE PRECISION DEFAULT NULL,  -- Initial height of the billet
    initial_width               DOUBLE PRECISION DEFAULT NULL,  -- Initial width of the billet
    initial_length              DOUBLE PRECISION DEFAULT NULL,  -- Initial length of the billet

    final_height                DOUBLE PRECISION DEFAULT NULL,  -- Final height of the billet
    final_width                 DOUBLE PRECISION DEFAULT NULL,  -- Final width of the billet
    final_length                DOUBLE PRECISION DEFAULT NULL,  -- Final length of the billet

    equivalent_diameter         DOUBLE PRECISION DEFAULT NULL,  -- Final equivalent diameter of the billet

    initial_cross_section_area  DOUBLE PRECISION DEFAULT NULL,  -- Initial Cross section area of the billet
    final_cross_section_area    DOUBLE PRECISION DEFAULT NULL,  -- Final Cross section area of the billet

    initial_surface_area        DOUBLE PRECISION DEFAULT NULL,  -- Initial Surface area of the billet
    final_surface_area          DOUBLE PRECISION DEFAULT NULL,  -- Final Surface area of the billet

    initial_height_to_width_ratio   DOUBLE PRECISION DEFAULT NULL,  -- Compatibility with ForgeLab v.1
    final_height_to_width_ratio     DOUBLE PRECISION DEFAULT NULL,  -- Compatibility with ForgeLab v.1

    initial_length_of_contact       DOUBLE PRECISION DEFAULT NULL,  -- Compatibility with ForgeLab v.1
    final_length_of_contact         DOUBLE PRECISION DEFAULT NULL,  -- Compatibility with ForgeLab v.1

    initial_width_of_contact        DOUBLE PRECISION DEFAULT NULL,  -- Compatibility with ForgeLab v.1
    final_width_of_contact          DOUBLE PRECISION DEFAULT NULL,  -- Compatibility with ForgeLab v.1

    elongation_channel_a            DOUBLE PRECISION DEFAULT NULL,  -- Effective strain Increment below beta
    elongation_channel_b            DOUBLE PRECISION DEFAULT NULL,  -- Effective strain Increment above beta

    strain_height                   DOUBLE PRECISION DEFAULT NULL,  -- True strain increment for height
    strain_width                    DOUBLE PRECISION DEFAULT NULL,  -- True strain increment for width
    strain_length                   DOUBLE PRECISION DEFAULT NULL,  -- True strain increment for length

    strain_accumulated_channel_a    DOUBLE PRECISION DEFAULT NULL,  -- Total effective strain below beta
    strain_accumulated_channel_b    DOUBLE PRECISION DEFAULT NULL,  -- Total effective strain above beta

    -- *********************************** SIMULATION STATUS ******************************************

    parent_simulation_status        simulation_status_enum DEFAULT 'stop',

    simulation_status               simulation_status_enum DEFAULT 'stop',
    simulation_server_retry_count   INT DEFAULT 0,
    simulation_server_worker_id     BIGINT DEFAULT 0, -- Worker GenerateImagesProcess PID 
    simulation_path                 VARCHAR(2047) DEFAULT NULL,
    simulation_time_started         TIMESTAMP DEFAULT NULL,
    simulation_time_finished        TIMESTAMP DEFAULT NULL,
    simulation_starting_step        INT DEFAULT NULL,
    simulation_finishing_step       INT DEFAULT NULL,
    simulation_duration_days        DOUBLE PRECISION DEFAULT 0,

    print_status                    simulation_status_enum DEFAULT 'stop',
    print_server_retry_count        INT DEFAULT 0,
    print_server_worker_id          BIGINT DEFAULT NULL, -- Worker GeneratePptProcess PID 
    print_path                      VARCHAR(2047) DEFAULT NULL,
    print_time_started              TIMESTAMP DEFAULT NULL,
    print_time_finished             TIMESTAMP DEFAULT NULL,

    -- *********************************** UNIQUE KEYS *******************************************

    CONSTRAINT uk_post_bites_1 UNIQUE (execution_id, bite_order),

    -- *********************************** FOREIGN KEYS ******************************************

    CONSTRAINT fk_post_bites_execution_id
        FOREIGN KEY (execution_id)
        REFERENCES server_pre_main(execution_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CONSTRAINT fk_post_bites_press_mode_id
        FOREIGN KEY (press_mode_id)
        REFERENCES press_modes(press_mode_id)
        ON DELETE SET DEFAULT
        ON UPDATE CASCADE           
);
"""


    @classmethod
    def create(cls, conn: connection):
        """
        Create tables for forgelab schema.

        param: conn: psycopg2.extensions.connection
        """

        print("Creating TABLEs...")

        cur = conn.cursor()

        len_i = len(cls)
        i = 0
        for _member in cls:
            query_text = _member.value
            cur.execute(query_text)
            conn.commit()
            print(f"CREATE TABLE query {i + 1}/{len_i} finished", end='\r')
            i += 1
        cur.close()
