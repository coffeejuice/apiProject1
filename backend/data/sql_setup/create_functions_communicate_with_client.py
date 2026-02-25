from psycopg2.extensions import connection
from enum import Enum, unique


@unique
class CreateToClientCommunicationFunctions(Enum):

    function_notify_on_simulation_status_change = """
CREATE OR REPLACE FUNCTION function_notify_on_simulation_status_change()
    RETURNS TRIGGER AS $$
    BEGIN
        PERFORM pg_notify('process_versions_simulation_status_change', '');
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;"""

    trigger_simulation_status_change = """
CREATE TRIGGER trigger_simulation_status_change
    AFTER UPDATE OF 
        simulation_status, preview_status, run_switch_status, run_switch_is_active, name, ran_at, finished_at, 
        simulation_server_id, simulation_expected_duration_days, simulation_queue_number
    ON process_versions
    FOR EACH ROW
    EXECUTE FUNCTION function_notify_on_simulation_status_change();"""

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
