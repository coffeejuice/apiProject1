from psycopg2.extensions import connection
from enum import Enum, unique


@unique
class CreateFunctionsAndTriggers(Enum):

    update_operations_library_last_updated = """
CREATE OR REPLACE FUNCTION update_operations_library_last_updated()
    RETURNS TRIGGER AS $$
    BEGIN
      UPDATE operations_library_update_signal
      SET last_updated = NOW()
      WHERE id = 1;
    
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;"""

    update_operations_library_last_updated_trigger = """
CREATE TRIGGER update_operations_library_last_updated_trigger
    AFTER UPDATE ON operations_library
    FOR EACH ROW
    EXECUTE FUNCTION update_operations_library_last_updated();"""

    # ---------------------------------------------------------------------------------------

    update_updated_at_column_in_die = """
CREATE OR REPLACE FUNCTION update_updated_at_column_in_die()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = NOW();
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;"""

    update_updated_at_in_die_trigger = """
CREATE TRIGGER update_updated_at_in_die_trigger
    BEFORE UPDATE ON dies
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column_in_die();"""

    # ---------------------------------------------------------------------------------------

    update_obsolete_at_column_in_die = """
CREATE OR REPLACE FUNCTION update_obsolete_at_column_in_die()
    RETURNS TRIGGER AS $$
    BEGIN
        IF NEW.is_obsolete = TRUE 
        THEN
            NEW.obsolete_at = NOW();
        ELSE
            NEW.obsolete_at = NULL;
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;"""

    update_obsolete_at_in_die_trigger = """
CREATE TRIGGER update_obsolete_at_in_die_trigger
    BEFORE UPDATE ON dies
    FOR EACH ROW
    WHEN (OLD.is_obsolete IS DISTINCT FROM NEW.is_obsolete)
    EXECUTE FUNCTION update_obsolete_at_column_in_die();"""

    # ---------------------------------------------------------------------------------------

    function_add_server_pre_main_changes = """
CREATE OR REPLACE FUNCTION function_add_server_pre_main_changes() RETURNS TRIGGER AS $$
    BEGIN
        -- Send notification
        PERFORM pg_notify('server_pre_main_changes', NEW.process_version_id::text);
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;"""

    trigger_server_pre_main_changes = """
CREATE TRIGGER trigger_server_pre_main_changes
    AFTER INSERT OR UPDATE OR DELETE ON server_pre_main
    FOR EACH ROW
    EXECUTE FUNCTION function_add_server_pre_main_changes();"""

    # ---------------------------------------------------------------------------------------

    func_update_server_pre_main = """
CREATE OR REPLACE FUNCTION func_update_server_pre_main()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.last_modified = NOW();
    
        UPDATE process_versions 
        SET last_modified = NOW() 
        WHERE process_version_id = NEW.process_version_id;
    
        RETURN NEW;
    END;
    $$ language 'plpgsql';"""

    trigger_update_server_pre_main = """
CREATE TRIGGER trigger_update_server_pre_main
    BEFORE UPDATE ON server_pre_main
    FOR EACH ROW
    EXECUTE PROCEDURE func_update_server_pre_main();"""

    # ---------------------------------------------------------------------------------------

    function_notify_simulation_server_on_simulation_status_change = """
    CREATE OR REPLACE FUNCTION function_notify_simulation_server_on_simulation_status_change()
        RETURNS TRIGGER AS $$
        BEGIN
            IF
                NEW.simulation_status <> OLD.simulation_status
            THEN
                PERFORM pg_notify('simulation_status_changed', NEW.process_version_id::text);
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;"""

    trigger_notify_simulation_server_on_simulation_status_change = """
    CREATE TRIGGER trigger_notify_simulation_server_on_simulation_status_change
        AFTER UPDATE OF simulation_status ON process_versions
        EXECUTE FUNCTION function_notify_simulation_server_on_simulation_status_change();"""

    # ------------------------ SIMULATION SERVER ----------------------------------------
    # ------------------------ CALLING FUNCTION -----------------------------------------
    # ------------------------- func_assign_server_to_process ---------------------------
    # ------------------------ TO PICK A process_version_id -----------------------------

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
