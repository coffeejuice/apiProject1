from psycopg2.extensions import connection
from enum import Enum, unique


@unique
class CreateRunStopButtonsFunctions(Enum):
    # ------------------------- CLIENT BUTTONS ACTIVATION FUNCTIONS -----------------------

    func_is_run_simulation_allowed = """
CREATE OR REPLACE FUNCTION func_is_run_simulation_allowed(input_process_version_id BIGINT)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN (
        SELECT run_switch_is_active = TRUE AND run_switch_status = FALSE
        FROM process_versions
        WHERE process_version_id = input_process_version_id
    );
END;
$$ LANGUAGE plpgsql;
"""

    func_is_continue_simulation_allowed = """
CREATE OR REPLACE FUNCTION func_is_continue_simulation_allowed(
    input_process_version_id BIGINT, 
    input_execution_order SMALLINT)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN (
        SELECT run_switch_is_active = TRUE AND run_switch_status = FALSE
        FROM process_versions
        WHERE process_version_id = input_process_version_id
    );
END;
$$ LANGUAGE plpgsql;
"""

    func_is_stop_simulation_allowed = """
CREATE OR REPLACE FUNCTION func_is_stop_simulation_allowed(input_process_version_id BIGINT)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN (
        SELECT run_switch_status = TRUE
        FROM process_versions
        WHERE process_version_id = input_process_version_id
    );
END;
$$ LANGUAGE plpgsql;"""

    function_run_simulation = """
CREATE OR REPLACE FUNCTION function_run_simulation(input_process_version_id BIGINT)
RETURNS VOID AS $$
BEGIN
IF 
    func_is_run_simulation_allowed(input_process_version_id::BIGINT) 
THEN

    UPDATE process_versions
        SET run_switch_status = True
        WHERE process_version_id = input_process_version_id;

    PERFORM pg_notify('simulation_status_changed', input_process_version_id::TEXT);

END IF;
RETURN;
END;
$$ LANGUAGE plpgsql;
"""

    function_continue_simulation = """
CREATE OR REPLACE FUNCTION function_continue_simulation(
    input_process_version_id BIGINT, 
    input_execution_order SMALLINT
)
RETURNS VOID AS $$
BEGIN
IF 
    func_is_continue_simulation_allowed(input_process_version_id::BIGINT, input_execution_order::SMALLINT)
THEN

    UPDATE process_versions
        SET run_switch_status = True
        WHERE process_version_id = input_process_version_id;

    PERFORM pg_notify('simulation_status_changed', input_process_version_id::TEXT);

END IF;
RETURN;
END;
$$ LANGUAGE plpgsql;"""

    function_stop_simulation = """
CREATE OR REPLACE FUNCTION function_stop_simulation(input_process_version_id BIGINT)
RETURNS VOID AS $$
BEGIN
IF 
    func_is_stop_simulation_allowed(input_process_version_id::BIGINT)
THEN

    UPDATE process_versions
        SET run_switch_status = FALSE
        WHERE process_version_id = input_process_version_id;

    PERFORM pg_notify('simulation_status_changed', input_process_version_id::TEXT);

END IF;
RETURN;
END;
$$ LANGUAGE plpgsql;"""

    function_on_run_switch_status_change = """
CREATE OR REPLACE FUNCTION function_on_run_switch_status_change() 
RETURNS TRIGGER AS $$
BEGIN
    IF 
        NEW.run_switch_status = TRUE 
    THEN
        UPDATE process_versions
            SET 
                simulation_status = 'queue'::simulation_status_enum,
                preview_status = 'ok_not_editable'::preview_status_enum,
                is_editable = FALSE
            WHERE process_version_id = NEW.process_version_id;
    ELSE
        UPDATE process_versions
            SET 
                simulation_status = 'stop'::simulation_status_enum
            WHERE process_version_id = NEW.process_version_id;
    END IF;

    PERFORM pg_notify('simulation_status_changed', NEW.process_version_id::TEXT);

RETURN NEW;
END;
$$ LANGUAGE plpgsql;"""

    trigger_on_run_switch_status_change = """
CREATE TRIGGER trigger_on_run_switch_status_change
    AFTER UPDATE OF run_switch_status ON process_versions
    FOR EACH ROW
    WHEN (
        OLD.run_switch_status <> NEW.run_switch_status
        AND 
        NEW.simulation_status <> 'finished'
    )
    EXECUTE FUNCTION function_on_run_switch_status_change();"""

    function_on_preview_status_change = """
CREATE OR REPLACE FUNCTION function_on_preview_status_change() 
RETURNS TRIGGER AS $$
BEGIN
    UPDATE process_versions
        SET run_switch_is_active = (NEW.preview_status IN ('ok', 'ok_not_editable'))
        WHERE process_version_id = NEW.process_version_id;

    PERFORM pg_notify('simulation_status_changed', NEW.process_version_id::TEXT);

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;"""

    trigger_on_preview_status_change = """
CREATE TRIGGER trigger_on_preview_status_change
    AFTER UPDATE OF preview_status ON process_versions
    FOR EACH ROW
    WHEN (OLD.preview_status <> NEW.preview_status)
    EXECUTE FUNCTION function_on_preview_status_change();"""

    function_on_server_pre_main_billet_file_change = """
CREATE OR REPLACE FUNCTION function_on_server_pre_main_billet_file_change() 
RETURNS TRIGGER AS $$
BEGIN
    IF 
        NEW.post_status IN ('queue', 'error')
        AND NEW.post_server_id IS NULL 
    THEN
        PERFORM pg_notify('simulation_of_operation_finished', NEW.execution_id::TEXT);
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;"""

    trigger_on_server_pre_main_post_status_change = """
CREATE TRIGGER trigger_on_server_pre_main_post_status_change
    AFTER UPDATE OF post_status ON server_pre_main
    FOR EACH ROW
    WHEN (OLD.post_status <> NEW.post_status)
    EXECUTE FUNCTION function_on_server_pre_main_billet_file_change();"""

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
