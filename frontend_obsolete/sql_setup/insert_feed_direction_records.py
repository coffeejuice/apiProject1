

def insert_feed_direction_records(cur):
    """Add materials to materials table in postgresql 'forgelab_db' database."""

    query_text = "INSERT INTO feed_direction (feed_direction_id, feed_direction_name) VALUES (%s, %s)"
    query_values = [
        (1, 'LANGUAGE|EN|Select direction|LANGUAGE|RU|Выберите направление|LANGUAGE|ZH_HANS|选择方向'),
        (2, 'LANGUAGE|EN|==>|LANGUAGE|RU|==>|LANGUAGE|ZH_HANS|==>'),
        (3, 'LANGUAGE|EN|<==|LANGUAGE|RU|<==|LANGUAGE|ZH_HANS|<=='),
        (4, 'LANGUAGE|EN|<==>|LANGUAGE|RU|<==>|LANGUAGE|ZH_HANS|<==>')]
    cur.executemany(query_text, query_values)


def insert_tail_side_records(cur):
    """Add tail side names (top, bottom) to 'tail_side' table in postgresql 'forgelab_db' database."""

    query_text = "INSERT INTO ingot_side (id, name) VALUES (%s, %s)"
    query_values = [
        (1, 'LANGUAGE|EN|Select tail side|LANGUAGE|RU|Выберите сторону|LANGUAGE|ZH_HANS|选择一边'),
        (2, 'LANGUAGE|EN|top|LANGUAGE|RU|верх|LANGUAGE|ZH_HANS|顶面'),
        (3, 'LANGUAGE|EN|bottom|LANGUAGE|RU|низ|LANGUAGE|ZH_HANS|底部')]
    cur.executemany(query_text, query_values)


def insert_languages(cur):
    """
    Add records to 'language' table.
    language_code = ISO 639-1 + (Region code ISO 3166-1 alpha-2 or Script code ISO 15924)
    """
    query_text = "INSERT INTO ui_language (language_id, language_code, language_name) VALUES (%s, %s, %s)"
    query_values = [
        (1, 'EN', 'English',),
        (2, 'RU', 'Russian (Русский)',),
        (3, 'ZH_HANS', 'Chinese (中文)',)
    ]
    cur.executemany(query_text, query_values)


def insert_furnace_class_records(cur):
    """Deprecated: furnace_class table was removed."""
    return


def insert_departments_records(cur):
    """Add default department in postgresql 'departments' database."""
    cur.execute("INSERT INTO departments (department_name) VALUES (%s)", ('Select department',))
