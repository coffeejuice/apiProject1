

def insert_material_records(cur):
    """Add materials to materials table in postgresql 'forgelab_db' database."""
    mat_formula = "INSERT INTO material (material_name, material_path, short_name, density) VALUES (%s, %s, %s, %s)"
    mat_values = [
        ('LANGUAGE|EN|Select material|LANGUAGE|RU|Выберите материал|LANGUAGE|ZH_HANS|选择材料', '', 'NA', 0),
        ('LANGUAGE|EN|INC718|LANGUAGE|RU|INC718|LANGUAGE|ZH_HANS|INC718', 'material_Inc718_20220602.key', 'Inc718', 8190),
        ('LANGUAGE|EN|BT20 (Ti-6.5Al-2Zr-1Mo-1V)|LANGUAGE|RU|Вт20 (Ti-6.5Al-2Zr-1Mo-1V)|LANGUAGE|ZH_HANS|TA15 (Ti-6.5Al-2Zr-1Mo-1V)', 'material_TA15_20221024_RUSSIA_JMATPRO.KEY', 'TA15', 4450),
        ('LANGUAGE|EN|Ti-10V-2Fe-3Al|LANGUAGE|RU|Ti-10V-2Fe-3Al|LANGUAGE|ZH_HANS|TB6', 'material_TB6_20220717.key', 'TB6', 4620),
        ('LANGUAGE|EN|TB18|LANGUAGE|RU|TB18|LANGUAGE|ZH_HANS|TB18', 'material_TB18_20220602.key', 'TB18', 4450),
        ('LANGUAGE|EN|TC2 (Ti-4AL-1.5Mn)|LANGUAGE|RU|OT4-1 (Ti-4AL-1.5Mn)|LANGUAGE|ZH_HANS|TC2 (Ti-4AL-1.5Mn)', 'material_TC2_20220602.key',  'TC2', 4530),
        ('LANGUAGE|EN|Ti-6Al-4V|LANGUAGE|RU|Вт6 (Ti-6Al-4V)|LANGUAGE|ZH_HANS|TC4 (Ti-6Al-4V)', 'material_TC4_20220602.key', 'TC4', 4430),
        ('LANGUAGE|EN|TC17 (Ti-5Al-2Sn-4Mo-2Zr-4Cr)|LANGUAGE|RU|Ti17 (Ti-5Al-2Sn-4Mo-2Zr-4Cr)|LANGUAGE|ZH_HANS|TC17 (Ti-5Al-2Sn-4Mo-2Zr-4Cr)', 'material_TC17_20220602.key', 'TC17', 4650),
        ('LANGUAGE|EN|BT22|LANGUAGE|RU|Вт22|LANGUAGE|ZH_HANS|TC18', 'material_TC18_TC18-D500-T16-v04-sparse.KEY', 'TC18', 4620),
        ('LANGUAGE|EN|TC21|LANGUAGE|RU|TC21|LANGUAGE|ZH_HANS|TC21', 'material_TC21_20220622.KEY', 'TC21', 4430),
        ('LANGUAGE|EN|Ti5553|LANGUAGE|RU|Ti5553|LANGUAGE|ZH_HANS|Ti5553', 'material_Ti5553_20220621.key', 'Ti5553', 4650),
        ('LANGUAGE|EN|Ti80 (Ti-6Al-3Nb-2Zr-1Mo)|LANGUAGE|RU|Ti80 (Ti-6Al-3Nb-2Zr-1Mo)|LANGUAGE|ZH_HANS|Ti80 (Ti-6Al-3Nb-2Zr-1Mo)', 'material_Ti80_WST_20240528.KEY', 'Ti80', 4490),
    ]
    cur.executemany(mat_formula, mat_values)
