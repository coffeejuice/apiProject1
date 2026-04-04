from psycopg2.extensions import connection
from enum import Enum, unique


@unique
class CreateOperationFunctions(Enum):

    create_operations_type_id_record = """
    CREATE OR REPLACE FUNCTION create_operations_type_id_record() RETURNS TRIGGER AS $$
        DECLARE
            table_exists BOOLEAN;
        BEGIN
            -- Check if the operations_type_id_NEW table exists
            EXECUTE format(
                'SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = %L)',
                'operations_type_id_' || NEW.type_id
            )
            INTO table_exists;

            -- If the table exists, insert a new record
            IF table_exists THEN
                EXECUTE format('INSERT INTO operations_type_id_%s (id) VALUES (%s)', NEW.type_id, NEW.id);
            END IF;        
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;"""

    create_operations_type_id_record_trigger = """
    CREATE TRIGGER create_operations_type_id_record_trigger
        AFTER INSERT ON operations
        FOR EACH ROW
        EXECUTE FUNCTION create_operations_type_id_record();"""

    # ---------------------------------------------------------------------------------------

    update_operations_type_id_record = """
    CREATE OR REPLACE FUNCTION update_operations_type_id_record() RETURNS TRIGGER AS $$
        DECLARE
            table_exists BOOLEAN;
        BEGIN
            -- Check if the type_id has changed
            IF OLD.type_id <> NEW.type_id THEN
                -- Check if the operations_type_id_OLD table exists
                EXECUTE format(
                    'SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = %L)',
                    'operations_type_id_' || OLD.type_id
                )
                INTO table_exists;

                -- If the table exists, delete the old record
                IF table_exists THEN
                    EXECUTE format('DELETE FROM operations_type_id_%s WHERE id = %s', OLD.type_id, OLD.id);
                END IF;

                -- Check if the operations_type_id_NEW table exists
                EXECUTE format(
                    'SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = %L)',
                    'operations_type_id_' || NEW.type_id
                )
                INTO table_exists;

                -- If the table exists, insert a new record
                IF table_exists THEN
                    EXECUTE format('INSERT INTO operations_type_id_%s (id) VALUES (%s)', NEW.type_id, NEW.id);
                END IF;
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;"""

    update_operations_type_id_record_trigger = """
    -- Create the trigger for updates
    CREATE TRIGGER update_operations_type_id_record_trigger
        AFTER UPDATE OF type_id ON operations
        FOR EACH ROW
        EXECUTE FUNCTION update_operations_type_id_record();"""

    # ---------------------------------------------------------------------------------------

    function_add_operations_changes = """
    CREATE OR REPLACE FUNCTION function_add_operations_changes() RETURNS TRIGGER AS $$
    DECLARE
        process_version BIGINT;
    BEGIN
        -- Get the process_version_id from the operations table
        SELECT o.process_version_id INTO process_version
        FROM operations o
        WHERE o.id = NEW.id;
    
        -- Insert into operations_changes table
        INSERT INTO operations_changes (id, process_version_id)
        VALUES (NEW.id, process_version)
        ON CONFLICT (id) DO NOTHING;
    
        -- Send notification with process_version_id as payload
        PERFORM pg_notify('operations_changes', process_version::TEXT);
    
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;"""

    trigger_operations_changes = """
    CREATE TRIGGER trigger_operations_changes
        AFTER INSERT OR UPDATE ON operations
        FOR EACH ROW
        EXECUTE FUNCTION function_add_operations_changes();"""

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
