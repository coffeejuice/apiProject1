from psycopg2.extensions import connection
from enum import Enum, unique


@unique
class CreateAdminManagementFunctions(Enum):

    function_on_accounts_update = """
    -- Create the function to send notification on update of signal_clear_token
    CREATE OR REPLACE FUNCTION function_on_accounts_update()
        RETURNS TRIGGER AS $$
        BEGIN
            IF 
                OLD.signal_clear_token <> NEW.signal_clear_token AND NEW.signal_clear_token IS TRUE
            THEN
                PERFORM pg_notify('signal_clear_token', NEW.user_id::text);
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;"""

    trigger_on_accounts_update = """
    CREATE TRIGGER trigger_on_accounts_update
        AFTER UPDATE ON accounts
        FOR EACH ROW
        EXECUTE FUNCTION function_on_accounts_update();"""

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
