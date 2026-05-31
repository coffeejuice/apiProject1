from psycopg2.extensions import connection
from enum import Enum, unique


@unique
class CreateQueueFunctions(Enum):

    get_priority_int = """
CREATE OR REPLACE FUNCTION get_priority_int(priority priority_enum) RETURNS SMALLINT AS $$
BEGIN
RETURN CASE priority
    WHEN 'Whenever' THEN 1
    WHEN 'Normal' THEN 2 
    WHEN 'ASAP' THEN 3
    WHEN 'Now' THEN 4
    ELSE 0
END;
END;
$$ LANGUAGE plpgsql;
"""

    # -------------------------------------------------------------------------------------------------

    calculate_simulation_priority = """
CREATE OR REPLACE FUNCTION calculate_simulation_priority(
    process_priority_enum priority_enum, 
    user_priority_enum priority_enum
) RETURNS SMALLINT AS $$
BEGIN
    RETURN get_priority_int(process_priority_enum) * 4 + get_priority_int(user_priority_enum);
END;
$$ LANGUAGE plpgsql;
"""

    # -------------------------------------------------------------------------------------------------

    function_update_simulation_priority_on_process_priority_change = """
CREATE OR REPLACE FUNCTION function_update_simulation_priority_on_process_priority_change()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE process_versions pv
        SET simulation_priority = calculate_simulation_priority(NEW.process_priority_enum, a.user_priority_enum)
        FROM accounts a
        INNER JOIN process p ON a.user_id = p.user_id
        WHERE pv.process_version_id = NEW.process_version_id AND p.process_id = NEW.process_id;
RETURN NEW;
END;
$$ LANGUAGE plpgsql;"""

    tr_update_simulation_priority_on_process_priority_change = """
CREATE TRIGGER tr_update_simulation_priority_on_process_priority_change
    AFTER UPDATE OF process_priority_enum ON process_versions
    FOR EACH ROW
    WHEN (OLD.process_priority_enum <> NEW.process_priority_enum)
    EXECUTE FUNCTION function_update_simulation_priority_on_process_priority_change();"""

    # -------------------------------------------------------------------------------------------------

    function_update_simulation_priority_on_user_priority_change = """
CREATE OR REPLACE FUNCTION function_update_simulation_priority_on_user_priority_change()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE process_versions pv
        SET simulation_priority = calculate_simulation_priority(pv.process_priority_enum, NEW.user_priority_enum)
        FROM process p
        WHERE p.process_id = pv.process_id AND p.user_id = NEW.user_id;

RETURN NEW;
END;
$$ LANGUAGE plpgsql;"""

    tr_update_simulation_priority_on_user_priority_change = """
CREATE TRIGGER tr_update_simulation_priority_on_user_priority_change
    AFTER UPDATE OF user_priority_enum ON accounts
    FOR EACH ROW
    WHEN (OLD.user_priority_enum <> NEW.user_priority_enum)
    EXECUTE FUNCTION function_update_simulation_priority_on_user_priority_change();"""

    # -------------------------------------------------------------------------------------------------

    function_update_simulation_queue_number = """
CREATE OR REPLACE FUNCTION function_update_simulation_queue_number() 
RETURNS TRIGGER AS $$
DECLARE
    total_threads_count INTEGER;
BEGIN
    -- Step 1: Calculate Total Active Simulation Threads
    SELECT COALESCE(SUM(max_threads_count), 0) INTO total_threads_count
    FROM servers
    WHERE 
        type = 'simulation'::server_type_enum
        AND is_active = TRUE;

    -- Handle case where there are no active simulation threads
    IF total_threads_count <= 0 THEN
        -- Nullify queue numbers for all process versions since no threads are available
        UPDATE process_versions
        SET simulation_queue_number = NULL,
            simulation_queue_row_number = NULL;
        RETURN NEW;
    END IF;

    -- Step 2: Assign Queue Numbers and Row Numbers to Active Process Versions
    WITH RankedProcesses AS (
        SELECT 
            process_version_id,
            ROW_NUMBER() OVER (ORDER BY simulation_priority DESC, simulation_expected_duration_days DESC) AS chain_number,
            CEIL(ROW_NUMBER() OVER (ORDER BY simulation_priority DESC, simulation_expected_duration_days DESC) / total_threads_count::numeric) AS matrix_row_number
        FROM process_versions
        WHERE run_switch_status = TRUE
    )
    UPDATE process_versions pv
    SET 
        simulation_queue_number = rp.chain_number,
        simulation_queue_row_number = rp.matrix_row_number
    FROM RankedProcesses rp
    WHERE pv.process_version_id = rp.process_version_id;

    -- Step 3: Nullify Queue Numbers for Inactive Process Versions
    UPDATE process_versions
    SET 
        simulation_queue_number = NULL,
        simulation_queue_row_number = NULL
    WHERE run_switch_status = FALSE;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;"""

    trigger_update_simulation_queue_on_process_versions_change = """
CREATE TRIGGER trigger_update_simulation_queue_on_process_versions_change
    AFTER UPDATE OF simulation_priority, simulation_expected_duration_days, run_switch_status 
    ON process_versions
    FOR EACH STATEMENT
    EXECUTE FUNCTION function_update_simulation_queue_number();"""

    trigger_update_simulation_queue_on_servers_change = """
CREATE TRIGGER trigger_update_simulation_queue_on_servers_change
    AFTER UPDATE OF max_threads_count, is_active, type
    ON servers
    FOR EACH STATEMENT
    EXECUTE FUNCTION function_update_simulation_queue_number();"""

    @classmethod
    def create(cls, conn: connection):
        """
        Create tables for forgelab schema.

        param: conn: psycopg2.extensions.connection
        """

        print("Creating FUNCTIONS & TRIGGERS...")

        cur = conn.cursor()

        len_i = len(cls)
        i = 0
        for _member in cls:
            query_text = _member.value
            cur.execute(query_text)
            conn.commit()
            print(f"Adding FUNCTIONS & TRIGGERS {i + 1}/{len_i} finished", end='\r')
            i += 1
        cur.close()
