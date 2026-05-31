library = dict(
    press=[
        {
            'press_die_match_code': 'empty_record',
            'name': 'LANGUAGE|EN|Select press|LANGUAGE|RU|Выберите пресс|LANGUAGE|ZH_HANS|选择锻压机'
        },
        {
            'press_die_match_code': 'p80',
            'name': 'LANGUAGE|EN|80MN|LANGUAGE|RU|80МН|LANGUAGE|ZH_HANS|80MN'
        },
        {
            'press_die_match_code': 'p45',
            'name': "LANGUAGE|EN|45MN|LANGUAGE|RU|45МН|LANGUAGE|ZH_HANS|45MN"
        },
        {
            'press_die_match_code': 'p16',
            'name': "LANGUAGE|EN|16MN|LANGUAGE|RU|16МН|LANGUAGE|ZH_HANS|16MN"
        },
        {
            'press_die_match_code': 'gfm20',
            'name': "LANGUAGE|EN|GFM 20MN|LANGUAGE|RU|GFM 20МН|LANGUAGE|ZH_HANS|GFM 20MN"
        },
    ],
    # --------------------------------------------------------------------------------------------------------
    press_mode=[
        dict(
            press_mode_name='p80_empty_record',
            name='LANGUAGE|EN|Select press mode|LANGUAGE|RU|Выберите режим|LANGUAGE|ZH_HANS|选择锻压模式',
            press_die_match_code='p80',
            is_default_press_mode=False,
            manipulators_count=2,
            automatic_feed_mode_is_on_when_bites_count=7,
            max_force=0.0,
            back_speed=0.0,
            idle_speed=0.0,
            working_speed=0.0,
            min_dwell_speed=0.0,
            max_dwell_time=0.0,
            power_limit=[
                [0.0, 0.0],
                [0.0, 0.0]],
            min_idle_stroke=0.0,
            max_idle_stroke=0.0,
            approaching_distance=0.0,  # Distance to billet, at which speed switches from idle to working ones
            open_height_without_dies=0.0),
        dict(
            press_mode_name='p80_63',
            name='LANGUAGE|EN|63/80MN|LANGUAGE|RU|63/80МН|LANGUAGE|ZH_HANS|63/80MN',
            press_die_match_code='p80',
            is_default_press_mode=True,
            manipulators_count=2,
            automatic_feed_mode_is_on_when_bites_count=7,
            max_force=63.0e6,
            back_speed=250.0,
            idle_speed=250.0,
            working_speed=95.0,
            min_dwell_speed=5.0,
            max_dwell_time=3.0,
            power_limit=[
                [0.0, 95.0],
                [1.26E+7, 76.0],
                [2.52E+7, 57.0],
                [3.78E+7, 38.0],
                [5.04E+7, 19.0],
                [6.3E+7, 0.0],
                [1.0E+9, 0.0]],
            min_idle_stroke=40.0,
            max_idle_stroke=250.0,
            approaching_distance=10.0,  # Distance to billet, at which speed switches from idle to working ones
            open_height_without_dies=4500.0),
        dict(
            press_mode_name='p80_42',
            name='LANGUAGE|EN|42/80MN|LANGUAGE|RU|42/80МН|LANGUAGE|ZH_HANS|42/80MN',
            press_die_match_code='p80',
            is_default_press_mode=False,
            manipulators_count=2,
            automatic_feed_mode_is_on_when_bites_count=7,
            max_force=42.0e6,
            back_speed=250.0,
            idle_speed=250.0,
            working_speed=140.0,
            min_dwell_speed=5.0,
            max_dwell_time=0.5,
            power_limit=[
                [0.0, 140.0],
                [8.4E+6, 112.0],
                [1.68E+7, 84.0],
                [2.52E+7, 56.0],
                [3.36E+7, 28.0],
                [4.2E+7, 0.0],
                [1.0E+9, 0.0]],
            min_idle_stroke=40.0,
            max_idle_stroke=250.0,
            approaching_distance=10.0,  # Distance to billet, at which speed switches from idle to working ones
            open_height_without_dies=4500.0),
        dict(
            press_mode_name='p80_21',
            name='LANGUAGE|EN|21/80MN|LANGUAGE|RU|21/80МН|LANGUAGE|ZH_HANS|21/80MN',
            press_die_match_code='p80',
            is_default_press_mode=False,
            manipulators_count=2,
            automatic_feed_mode_is_on_when_bites_count=7,
            max_force=21.0e6,
            back_speed=250.0,
            idle_speed=250.0,
            working_speed=190.0,
            min_dwell_speed=5.0,
            max_dwell_time=0.25,
            power_limit=[
                [0.0, 190.0],
                [4.2E+6, 152.0],
                [8.4E+6, 116.0],
                [1.26E+7, 76.0],
                [1.68E+7, 38.0],
                [2.1E+7, 0.0],
                [1.0E+9, 0.0]],
            min_idle_stroke=40.0,
            max_idle_stroke=250.0,
            approaching_distance=10.0,  # Distance to billet, at which speed switches from idle to working ones
            open_height_without_dies=4500.0),
        dict(
            press_mode_name='p80_80',
            name='LANGUAGE|EN|80/80MN|LANGUAGE|RU|80/80МН|LANGUAGE|ZH_HANS|80/80MN',
            press_die_match_code='p80',
            is_default_press_mode=False,
            manipulators_count=2,
            automatic_feed_mode_is_on_when_bites_count=7,
            max_force=80.0e6,
            back_speed=250.0,
            idle_speed=250.0,
            working_speed=67.0,
            min_dwell_speed=1.0,
            max_dwell_time=120.0,
            power_limit=[
                [0.0, 67.0],
                [1.6E+7, 53.6],
                [3.2E+7, 40.2],
                [4.8E+7, 26.8],
                [6.4E+7, 13.4],
                [8.0E+7, 0.0],
                [1.0E+9, 0.0]],
            min_idle_stroke=40.0,
            max_idle_stroke=250.0,
            approaching_distance=10.0,  # Distance to billet, at which speed switches from idle to working ones
            open_height_without_dies=4500.0),
        dict(
            press_mode_name='p45_empty_record',
            name='LANGUAGE|EN|Select press mode|LANGUAGE|RU|Выберите режим|LANGUAGE|ZH_HANS|选择锻压模式',
            press_die_match_code='p45',
            is_default_press_mode=False,
            manipulators_count=2,
            automatic_feed_mode_is_on_when_bites_count=7,
            max_force=0.0,
            back_speed=0.0,
            idle_speed=0.0,
            working_speed=0.0,
            min_dwell_speed=0.0,
            max_dwell_time=0.0,
            power_limit=[
                [0.0, 0.0],
                [0.0, 0.0]],
            min_idle_stroke=0.0,
            max_idle_stroke=0.0,
            approaching_distance=0.0,  # Distance to billet, at which speed switches from idle to working ones
            open_height_without_dies=0.0),
        dict(
            press_mode_name='p45_45',
            name='LANGUAGE|EN|45/45MN|LANGUAGE|RU|45/45МН|LANGUAGE|ZH_HANS|45/45MN',
            press_die_match_code='p45',
            is_default_press_mode=True,
            manipulators_count=2,
            automatic_feed_mode_is_on_when_bites_count=7,
            max_force=45.0E6,
            back_speed=250.0,
            idle_speed=250.0,
            working_speed=40.0,
            min_dwell_speed=5.0,
            max_dwell_time=2.0,
            power_limit=[
                [0.00E+00, 40.0],
                [9.00E+06, 32.0],
                [1.80E+07, 24.0],
                [2.70E+07, 16.0],
                [3.60E+07, 8.0],
                [4.50E+07, 0.0],
                [1.0E+09, 0.0]],
            min_idle_stroke=40.0,
            max_idle_stroke=250.0,
            approaching_distance=10.0,  # Distance to billet, at which speed switches from idle to working ones
            open_height_without_dies=4500.0),
        dict(
            press_mode_name='p16_empty_record',
            name='LANGUAGE|EN|Select press mode|LANGUAGE|RU|Выберите режим|LANGUAGE|ZH_HANS|选择锻压模式',
            press_die_match_code='p16',
            is_default_press_mode=False,
            manipulators_count=1,
            automatic_feed_mode_is_on_when_bites_count=7,
            max_force=0.0,
            back_speed=0.0,
            idle_speed=0.0,
            working_speed=0.0,
            min_dwell_speed=0.0,
            max_dwell_time=0.0,
            power_limit=[
                [0.0, 0.0],
                [0.0, 0.0]],
            min_idle_stroke=0.0,
            max_idle_stroke=0.0,
            approaching_distance=0.0,  # Distance to billet, at which speed switches from idle to working ones
            open_height_without_dies=0.0),
        dict(
            press_mode_name='p16_16',
            name='LANGUAGE|EN|16/16MN|LANGUAGE|RU|16/16МН|LANGUAGE|ZH_HANS|16/16MN',
            press_die_match_code='p16',
            is_default_press_mode=True,
            manipulators_count=1,
            automatic_feed_mode_is_on_when_bites_count=7,
            max_force=16.0E6,
            back_speed=250.0,
            idle_speed=250.0,
            working_speed=40.0,
            min_dwell_speed=5.0,
            max_dwell_time=1.0,
            power_limit=[
                [0.0, 40.0],
                [3.2E+6, 32.0],
                [6.4E+6, 24.0],
                [9.6E+6, 16.0],
                [12.8E+6, 8.0],
                [16.0E+6, 0.0],
                [1.0E+9, 0.0]
            ],
            min_idle_stroke=40.0,
            max_idle_stroke=250.0,
            approaching_distance=10.0,  # Distance to billet, at which speed switches from idle to working ones
            open_height_without_dies=4500.0),
        dict(
            press_mode_name='gfm20_empty_record',
            name='LANGUAGE|EN|Select press mode|LANGUAGE|RU|Выберите режим|LANGUAGE|ZH_HANS|选择锻压模式',
            press_die_match_code='gfm20',
            is_default_press_mode=False,
            manipulators_count=2,
            automatic_feed_mode_is_on_when_bites_count=7,
            max_force=0.0,
            back_speed=0.0,
            idle_speed=0.0,
            working_speed=0.0,
            min_dwell_speed=0.0,
            max_dwell_time=0.0,
            power_limit=[
                [0.0, 0.0],
                [0.0, 0.0]],
            min_idle_stroke=0.0,
            max_idle_stroke=0.0,
            approaching_distance=0.0,  # Distance to billet, at which speed switches from idle to working ones
            open_height_without_dies=0.0),
        dict(
            press_mode_name='gfm20_20',
            name='LANGUAGE|EN|20/20MN|LANGUAGE|RU|20/20МН|LANGUAGE|ZH_HANS|20/20MN'
                 '',
            press_die_match_code='gfm20',
            is_default_press_mode=True,
            manipulators_count=2,
            automatic_feed_mode_is_on_when_bites_count=7,
            max_force=20.0E6,
            back_speed=250.0,
            idle_speed=250.0,
            working_speed=70.0,
            min_dwell_speed=20.0,
            max_dwell_time=0.1,
            power_limit=[
                [0.0, 160.0],
                [4.0E+6, 128.0],
                [8.0E+6, 96.0],
                [12.0E+6, 64.0],
                [16.0E+6, 32.0],
                [20.0E+6, 0.0],
                [1.0E+9, 0.0]
            ],
            min_idle_stroke=10.0,
            max_idle_stroke=100.0,
            approaching_distance=0.0,  # Distance to billet, at which speed switches from idle to working ones
            open_height_without_dies=2000.0)
    ],
    # --------------------------------------------------------------------------------------------------------
    die=[
        dict(
            die_name='flat_empty_record',
            die_assembly_name='flat_empty_record',
            name='LANGUAGE|EN|Select die|LANGUAGE|RU|Выберите боёк|LANGUAGE|ZH_HANS|选择锻造工具',
            press_die_match_code='empty_record',
            die_template_file_name='',
            die_type='flat',
            inventory_number='',
            is_matching_as_top=True,
            is_matching_as_bottom=True,
            is_matching_as_minus_y=True,
            is_matching_as_plus_y=True,
            dimensions=dict(
                total_length=0.0,
                total_width=0.0,
                height=0.0,
                straight_length=0.0,
                edge_radius=0.0,
                edge_angle=0.0
            ),
            is_obsolete=False),
        dict(
            die_name='flat_d650_top',
            die_assembly_name='flat_d650',
            name='LANGUAGE|EN|650|LANGUAGE|RU|650|LANGUAGE|ZH_HANS|650',
            press_die_match_code='p80',
            die_template_file_name='press_80_flat_650_top.zip',
            die_type='flat',
            inventory_number='',
            is_matching_as_top=True,
            is_matching_as_bottom=False,
            is_matching_as_minus_y=False,
            is_matching_as_plus_y=False,
            dimensions=dict(
                total_length=650.0,
                total_width=2200.0,
                height=1200.0,
                straight_length=390.0,
                edge_radius=160.0,
                edge_angle=90.0,
            ),
            is_obsolete=False),
        dict(
            die_name='flat_d650_bottom',
            die_assembly_name='flat_d650',
            name='LANGUAGE|EN|650|LANGUAGE|RU|650|LANGUAGE|ZH_HANS|650',
            press_die_match_code='p80',
            die_template_file_name='press_80_flat_650_bottom.zip',
            die_type='flat',
            inventory_number='',
            is_matching_as_top=False,
            is_matching_as_bottom=True,
            is_matching_as_minus_y=False,
            is_matching_as_plus_y=False,
            dimensions=dict(
                total_length=650.0,
                total_width=2200.0,
                height=1200.0,
                straight_length=390.0,
                edge_radius=160.0,
                edge_angle=90.0,
            ),
            is_obsolete=False),
        dict(
            die_name='flat_d900_top',
            die_assembly_name='flat_d900',
            name='LANGUAGE|EN|900|LANGUAGE|RU|900|LANGUAGE|ZH_HANS|900',
            press_die_match_code='p80',
            die_template_file_name='press_80_flat_900_top.zip',
            die_type='flat',
            inventory_number='',
            is_matching_as_top=True,
            is_matching_as_bottom=False,
            is_matching_as_minus_y=False,
            is_matching_as_plus_y=False,
            dimensions=dict(
                total_length=900.0,
                total_width=1500.0,
                height=1200.0,
                straight_length=500.0,
                edge_radius=250.0,
                edge_angle=90.0,
            ),
            is_obsolete=False),
        dict(
            die_name='flat_d900_bottom',
            die_assembly_name='flat_d900',
            name='LANGUAGE|EN|900|LANGUAGE|RU|900|LANGUAGE|ZH_HANS|900',
            press_die_match_code='p80',
            die_template_file_name='press_80_flat_900_bottom.zip',
            die_type='flat',
            inventory_number='',
            is_matching_as_top=False,
            is_matching_as_bottom=True,
            is_matching_as_minus_y=False,
            is_matching_as_plus_y=False,
            dimensions=dict(
                total_length=900.0,
                total_width=1500.0,
                height=1200.0,
                straight_length=500.0,
                edge_radius=250.0,
                edge_angle=90.0,
            ),
            is_obsolete=False),
        dict(
            die_name='flat_d550_top',
            die_assembly_name='flat_d550',
            name='LANGUAGE|EN|550|LANGUAGE|RU|550|LANGUAGE|ZH_HANS|550',
            press_die_match_code='p45',
            die_template_file_name='press_45_flat_550_top.zip',
            die_type='flat',
            inventory_number='',
            is_matching_as_top=True,
            is_matching_as_bottom=False,
            is_matching_as_minus_y=False,
            is_matching_as_plus_y=False,
            dimensions=dict(
                total_length=550.0,
                total_width=2000.0,
                height=1200.0,
                straight_length=390.0,
                edge_radius=80.0,
                edge_angle=90.0,
            ),
            is_obsolete=False),
        dict(
            die_name='flat_d550_bottom',
            die_assembly_name='flat_d550',
            name='LANGUAGE|EN|550|LANGUAGE|RU|550|LANGUAGE|ZH_HANS|550',
            press_die_match_code='p45',
            die_template_file_name='press_45_flat_550_bottom.zip',
            die_type='flat',
            inventory_number='',
            is_matching_as_top=False,
            is_matching_as_bottom=True,
            is_matching_as_minus_y=False,
            is_matching_as_plus_y=False,
            dimensions=dict(
                total_length=550.0,
                total_width=2000.0,
                height=1200.0,
                straight_length=390.0,
                edge_radius=80.0,
                edge_angle=90.0,
            ),
            is_obsolete=False),
        # ------------------------------------------- V-DIES ------------------------------------------------------
        dict(
            die_name='v_die_empty_record',
            die_assembly_name='v_die_empty_record',
            name='LANGUAGE|EN|Select die|LANGUAGE|RU|Выберите боёк|LANGUAGE|ZH_HANS|选择锻造工具',
            press_die_match_code='p80',
            die_template_file_name='',
            die_type='v_die',
            inventory_number='',
            is_matching_as_top=True,
            is_matching_as_bottom=True,
            is_matching_as_minus_y=True,
            is_matching_as_plus_y=True,
            dimensions=dict(
                total_length=0.0,
                total_width=0.0,
                height=0.0,
                straight_length=0.0,
                edge_radius=0.0,
                edge_angle=90.0,
            ),
            is_obsolete=False),
        dict(
            die_name='v_die_p80_v_die_d355_d180_top',
            die_assembly_name='v_die_p80_v_die_d355_d180',
            name='LANGUAGE|EN|V122°◯355->◯180|LANGUAGE|RU|V122°◯355->◯180|LANGUAGE|ZH_HANS|V122°◯355->◯180',
            press_die_match_code='p80',
            die_template_file_name='press_80_v_a122_d355_d180_top.zip',
            die_type='v_die',
            inventory_number='',
            is_matching_as_top=True,
            is_matching_as_bottom=False,
            is_matching_as_minus_y=False,
            is_matching_as_plus_y=False,
            dimensions=dict(
                total_length=650.0,
                total_width=500.0,
                height=300.0,
                straight_length=353.35,
                edge_radius=150.0,
                edge_angle=90.0,
            ),
            is_obsolete=False),
        dict(
            die_name='v_die_p80_v_die_d355_d180_bottom',
            die_assembly_name='v_die_p80_v_die_d355_d180',
            name='LANGUAGE|EN|V122°◯355->◯180|LANGUAGE|RU|V122°◯355->◯180|LANGUAGE|ZH_HANS|V122°◯355->◯180',
            press_die_match_code='p80',
            die_template_file_name='press_80_v_a122_d355_d180_bottom.zip',
            die_type='v_die',
            inventory_number='',
            is_matching_as_top=False,
            is_matching_as_bottom=True,
            is_matching_as_minus_y=False,
            is_matching_as_plus_y=False,
            dimensions=dict(
                total_length=650.0,
                total_width=500.0,
                height=300.0,
                straight_length=353.35,
                edge_radius=150.0,
                edge_angle=90.0,
            ),
            is_obsolete=False),
        # ------------------------------------------- GFM-DIES -------------------------------------------
        dict(
            die_name='gfm_die_empty_record',
            die_assembly_name='gfm_die_empty_record',
            name='LANGUAGE|EN|Select die|'
                 'LANGUAGE|RU|Выберите боёк|'
                 'LANGUAGE|ZH_HANS|选择锻造工具',
            press_die_match_code='gfm20',
            die_template_file_name='',
            die_type='gfm_die',
            inventory_number='',
            is_matching_as_top=True,
            is_matching_as_bottom=True,
            is_matching_as_minus_y=True,
            is_matching_as_plus_y=True,
            dimensions=dict(
                total_length=0.0,
                total_width=0.0,
                height=0.0,
                straight_length=0.0,
                edge_radius=0.0,
                edge_angle=10.0,
            ),
            is_obsolete=False),
        dict(
            die_name='gfm_die_gfm20_w90_top',
            die_assembly_name='gfm_die_gfm20_w90',
            name='LANGUAGE|EN|w90xl240 ∠10° L850 (Top)|'
                 'LANGUAGE|RU|w90xl240 ∠10° L850 (Верхний)|'
                 'LANGUAGE|ZH_HANS|w90xl240 ∠10° L850 (Top)',
            press_die_match_code='gfm20',
            die_template_file_name='gfm_die_gfm20_w90_top.zip',
            die_type='gfm_die',
            inventory_number='',
            is_matching_as_top=True,
            is_matching_as_bottom=False,
            is_matching_as_minus_y=False,
            is_matching_as_plus_y=False,
            dimensions=dict(
                total_length=850.0,
                total_width=90.0,
                height=170.0,
                straight_length=240.0,
                edge_radius=20.0,
                edge_angle=10.0,
            ),
            is_obsolete=False),
        dict(
            die_name='gfm_die_gfm20_w90_bottom',
            die_assembly_name='gfm_die_gfm20_w90',
            name='LANGUAGE|EN|w90xl240 ∠10° L850 (Bottom)|'
                 'LANGUAGE|RU|w90xl240 ∠10° L850 (Нижний)|'
                 'LANGUAGE|ZH_HANS|w90xl240 ∠10° L850 (Bottom)',
            press_die_match_code='gfm20',
            die_template_file_name='gfm_die_gfm20_w90_bottom.zip',
            die_type='gfm_die',
            inventory_number='',
            is_matching_as_top=False,
            is_matching_as_bottom=True,
            is_matching_as_minus_y=False,
            is_matching_as_plus_y=False,
            dimensions=dict(
                total_length=850.0,
                total_width=90.0,
                height=170.0,
                straight_length=240.0,
                edge_radius=20.0,
                edge_angle=10.0,
            ),
            is_obsolete=False),
        dict(
            die_name='gfm_die_gfm20_w90_plus_y',
            die_assembly_name='gfm_die_gfm20_w90',
            name='LANGUAGE|EN|w90xl240 ∠10° L850 (+Y)|'
                 'LANGUAGE|RU|w90xl240 ∠10° L850 (+Y)|'
                 'LANGUAGE|ZH_HANS|w90xl240 ∠10° L850 (+Y)',
            press_die_match_code='gfm20',
            die_template_file_name='gfm_die_gfm20_w90_plus_y.zip',
            die_type='gfm_die',
            inventory_number='',
            is_matching_as_top=False,
            is_matching_as_bottom=False,
            is_matching_as_minus_y=False,
            is_matching_as_plus_y=True,
            dimensions=dict(
                total_length=850.0,
                total_width=90.0,
                height=170.0,
                straight_length=240.0,
                edge_radius=20.0,
                edge_angle=10.0,
            ),
            is_obsolete=False),
        dict(
            die_name='gfm_die_gfm20_w90_minus_y',
            die_assembly_name='gfm_die_gfm20_w90',
            name='LANGUAGE|EN|w90xl240 ∠10° L850 (-Y)|'
                 'LANGUAGE|RU|w90xl240 ∠10° L850 (-Y)|'
                 'LANGUAGE|ZH_HANS|w90xl240 ∠10° L850 (-Y)',
            press_die_match_code='gfm20',
            die_template_file_name='gfm_die_gfm20_w90_minus_y.zip',
            die_type='gfm_die',
            inventory_number='',
            is_matching_as_top=False,
            is_matching_as_bottom=False,
            is_matching_as_minus_y=True,
            is_matching_as_plus_y=False,
            dimensions=dict(
                total_length=850.0,
                total_width=90.0,
                height=170.0,
                straight_length=240.0,
                edge_radius=20.0,
                edge_angle=10.0,
            ),
            is_obsolete=False)
    ],

    # --------------------------------------------------------------------------------------------------------
    die_assembly=[
        dict(
            die_assembly_name='flat_empty_record',
            name='LANGUAGE|EN|Select die|LANGUAGE|RU|Выберите боёк|LANGUAGE|ZH_HANS|选择锻造工具',
            press_die_match_code='empty_record',
            die_type='flat',
            is_obsolete=False),
        dict(
            die_assembly_name='flat_d650',
            name='LANGUAGE|EN|650|LANGUAGE|RU|650|LANGUAGE|ZH_HANS|650',
            die_type='flat',
            is_obsolete=False),
        dict(
            die_assembly_name='flat_d900',
            name='LANGUAGE|EN|900|LANGUAGE|RU|900|LANGUAGE|ZH_HANS|900',
            die_type='flat',
            is_obsolete=False),
        dict(
            die_assembly_name='flat_d550',
            name='LANGUAGE|EN|550|LANGUAGE|RU|550|LANGUAGE|ZH_HANS|550',
            die_type='flat',
            is_obsolete=False),
        dict(
            die_assembly_name='flat_d550',
            name='LANGUAGE|EN|550|LANGUAGE|RU|550|LANGUAGE|ZH_HANS|550',
            die_type='flat',
            is_obsolete=False),
        # ------------------------------------------- V-DIES ------------------------------------------------------
        dict(
            die_assembly_name='v_die_empty_record',
            name='LANGUAGE|EN|Select die|LANGUAGE|RU|Выберите боёк|LANGUAGE|ZH_HANS|选择锻造工具',
            die_type='v_die',
            is_obsolete=False),
        dict(
            die_assembly_name='v_die_p80_v_die_d355_d180',
            name='LANGUAGE|EN|V122°◯355->◯180|LANGUAGE|RU|V122°◯355->◯180|LANGUAGE|ZH_HANS|V122°◯355->◯180',
            die_type='v_die',
            is_obsolete=False),
        # ------------------------------------------- GFM-DIES -------------------------------------------
        dict(
            die_assembly_name='gfm_die_empty_record',
            name='LANGUAGE|EN|Select die|LANGUAGE|RU|Выберите боёк|LANGUAGE|ZH_HANS|选择锻造工具',
            die_type='gfm_die',
            is_obsolete=False),
        dict(
            die_assembly_name='gfm_die_gfm20_w90',
            name='LANGUAGE|EN|w90xl240 ∠10° L850|LANGUAGE|RU|w90xl240 ∠10° L850|LANGUAGE|w90xl240 ∠10° L850',
            die_type='gfm_die',
            is_obsolete=False),
    ],

    # --------------------------------------------------------------------------------------------------------
    operations=['Draw', 'Upset', 'Cut', 'Heat', 'Pause'],
    # --------------------------------------------------------------------------------------------------------
    feed_directions=dict(
        Draw=['-->', '<--'],
        Upset=['-->', '<--'],
        Cut=['-->', '<--'],
        Heat=['NA'],
        Pause=['NA'],
        NewBillet=['NA']),
    # --------------------------------------------------------------------------------------------------------
    deformation_control=dict(
        Draw=['E', 'P', 'H'],
        Upset=['E', 'P', 'H'],
        Cut=dict(
            Equals=['k1-PcNum'],
            KeepFirst=['Length', 'Percent'],
            DeleteFirst=['Length', 'Percent']),
        Heat=['NA'],
        Pause=['NA'],
        NewBillet=['NA']),
    # --------------------------------------------------------------------------------------------------------
    first_pass_values=dict(
        initialize_table=dict(
            operation_number=1,
            operation_type='NewBillet',
            step_control='TC4',
            deformation_control='NA',
            angle='0',
            max_temperature=20.0,
            operation_time=0.0,
            total_time=0.0,
            feed_first=0.0,
            feed_middle=0.0,
            feed_last=0.0,
            speed=0.0,
            final_height=500.0,
            final_width=500.0,
            final_length=1000.0,
            final_diagonal=600.0,
            elongation_channel_a=1.0,
            elongation_channel_b=1.0,
            strain_accumulated_channel_a=0.0,
            strain_accumulated_channel_b=0.0),
        update_pass=dict(
            operation_number=1,
            operation_type='NewBillet',
            deformation_control='NA',
            angle='0',
            feed_first=0.0,
            feed_middle=0.0,
            feed_last=0.0,
            speed=0.0,
            elongation_channel_a=1.0,
            elongation_channel_b=1.0,
            strain_accumulated_channel_a=0.0,
            strain_accumulated_channel_b=0.0)),

    # --------------------------------------------------------------------------------------------------------
    variables_to_show_in_widget=[
        'operation_type',
        'deformation_control',
        'step_control',
        'press',
        'die',
        'feed_direction',
        'angle',
        'feed_first',
        'feed_middle',
        'feed_last',
        'speed',
        'final_height',
        'final_width',
        'final_length',
        'final_diagonal',
        'final_chamfer'],
    # --------------------------------------------------------------------------------------------------------
    change_operation_type_initial_parameters=dict(
        Draw=dict(
            operation_type='NA',
            deformation_control='E',
            step_control='Feed',
            feed_direction='-->',
            angle='90',
            feed_first=250.0,
            feed_middle=250.0,
            feed_last=250.0,
            speed=20.0,
            relative_deformation=12.0),
        Upset=dict(
            operation_type='NA',
            deformation_control='E',
            step_control='StepsNum',
            feed_direction='-->',
            angle='90',
            feed_first=250.0,
            feed_middle=250.0,
            feed_last=250.0,
            speed=20.0,
            relative_deformation=12.0),
        Cut=dict(
            operation_type='NA',
            step_control='Equals',
            deformation_control='k1-PcNum',
            feed_direction='-->',
            angle='0',
            relative_deformation=0.0,
            penetration=0.5,
            feed_first=0.0,
            feed_middle=0.0,
            feed_last=0.0,
            speed=40.0,
            elongation_channel_a=1.0,
            strain_accumulated_channel_a=0.0,
            num_of_bites=2),
        Heat=dict(
            operation_type='NA',
            deformation_control='NA',
            step_control='NA',
            feed_direction='NA',
            angle='0',
            relative_deformation=0.0,
            penetration=0.0,
            feed_first=0.0,
            feed_middle=0.0,
            feed_last=0.0,
            speed=0.0,
            num_of_bites=0,
            elongation_channel_a=1.0,
            strain_accumulated_channel_a=0.0),
        Pause=dict(
            operation_type='NA',
            deformation_control='NA',
            step_control='NA',
            feed_direction='NA',
            angle='0',
            relative_deformation=0.0,
            penetration=0.0,
            feed_first=0.0,
            feed_middle=0.0,
            feed_last=0.0,
            speed=0.0,
            num_of_bites=0,
            elongation_channel_a=1.0,
            strain_accumulated_channel_a=0.0),
        NewBillet=dict(
            operation_type='NA',
            deformation_control='NA',
            step_control='NA',
            feed_direction='NA',
            angle='0',
            relative_deformation=0.0,
            penetration=0.0,
            feed_first=0.0,
            feed_middle=0.0,
            feed_last=0.0,
            speed=0.0,
            num_of_bites=0,
            elongation_channel_a=1.0,
            strain_accumulated_channel_a=0.0)),

    add_row_copy_parameters=dict(
        Draw=dict(
            copied_values=[
                'operation_type',
                'deformation_control',
                'step_control',
                'press',
                'die',
                'feed_direction',
                'angle',
                'relative_deformation',
                'final_length',
                'final_height',
                'penetration',
                'feed_first',
                'feed_middle',
                'feed_last',
                'speed'],
            initialized_values=dict(
                operation_type='Draw')),
        Upset=dict(
            copied_values=[
                'operation_type',
                'deformation_control',
                'step_control',
                'press',
                'die',
                'feed_direction',
                'angle',
                'relative_deformation',
                'final_length',
                'final_height',
                'penetration',
                'feed_first',
                'feed_middle',
                'feed_last',
                'speed'],
            initialized_values=dict(
                operation_type='Upset')),
        Cut=dict(
            copied_values=[
                'press',
                'die'],
            initialized_values=dict(
                operation_type='Heat',
                feed_direction='-->',
                angle='0',
                feed_first=0.0,
                feed_middle=0.0,
                feed_last=0.0,
                speed=0.0,
                elongation_channel_a=1.0,
                strain_accumulated_channel_a=0.0)),
        Heat=dict(
            copied_values=[
                'press',
                'die'],
            initialized_values=dict(
                operation_type='Draw',
                deformation_control='H',
                step_control='Feed',
                feed_direction='-->',
                angle='0',
                feed_first=250.0,
                feed_middle=250.0,
                feed_last=250.0,
                speed=20.0,
                relative_deformation=12.0)),
        Pause=dict(
            copied_values=[
                'press',
                'die'],
            initialized_values=dict(
                operation_type='Draw',
                deformation_control='E',
                step_control='Feed',
                feed_direction='-->',
                angle='0',
                feed_first=250.0,
                feed_middle=250.0,
                feed_last=250.0,
                speed=20.0,
                relative_deformation=12.0)),
        NewBillet=dict(
            copied_values=[
                'press',
                'die'],
            initialized_values=dict(
                operation_type='Heat',
                feed_direction='-->',
                angle='0',
                feed_first=0.0,
                feed_middle=0.0,
                feed_last=0.0,
                speed=0.0,
                elongation_channel_a=1.0,
                strain_accumulated_channel_a=0.0))),
    default_values=dict(
        Draw=dict(
            E=dict(
                Feed={},
                StepsNum={}),
            P=dict(
                Feed={},
                StepsNum={}),
            H=dict(
                Feed={},
                StepsNum={})),
        Upset=dict(
            E=dict(
                Feed={},
                StepsNum={}),
            P=dict(
                Feed={},
                StepsNum={}),
            H=dict(
                Feed={},
                StepsNum={})),
        Cut={
            'Equals': {
                'k1-PcNum': {}},
            'KeepFirst': {
                'Length': {},
                'Percent': {}},
            'DeleteFirst': {
                'Length': {},
                'Percent': {}}},
        Heat=dict(NA=dict(NA=dict(num_of_bites=0, time_before_pass=60.0))),
        Pause={
            'NA': {
                'NA': {
                    'num_of_bites': 0}}},
        NewBillet=dict(NA=dict(NA=dict(num_of_bites=0, time_before_pass=0.0)))),
    # library['set_editable'][current_operation_type][deformation_control][step_control][flag_is_same_controls]
    set_editable=dict(
        first_pass=[
            'step_control', 'max_temperature', 'press', 'die', 'final_height', 'final_width', 'final_length',
            'final_diagonal'],
        Draw=dict(
            E=dict(
                Feed=dict(
                    same_controls=[
                        'operation_type', 'deformation_control', 'step_control',
                        'feed_direction', 'angle',
                        'relative_deformation',
                        'feed_first', 'feed_middle', 'feed_last'],
                    NA=[
                        'operation_type', 'deformation_control', 'step_control',
                        'press', 'die', 'feed_direction', 'angle',
                        'relative_deformation',
                        'feed_first', 'feed_middle', 'feed_last',
                        'speed']),
                StepsNum=dict(
                    same_controls=[
                        'operation_type', 'deformation_control', 'step_control',
                        'feed_direction', 'angle',
                        'relative_deformation',
                        'num_of_bites'],
                    NA=[
                        'operation_type', 'deformation_control', 'step_control',
                        'press', 'die', 'feed_direction', 'angle',
                        'relative_deformation',
                        'num_of_bites',
                        'speed'])),
            P=dict(
                Feed=dict(
                    same_controls=[
                        'operation_type', 'deformation_control', 'step_control',
                        'feed_direction', 'angle',
                        'penetration',
                        'feed_first', 'feed_middle', 'feed_last'],
                    NA=[
                        'operation_type', 'deformation_control', 'step_control',
                        'press', 'die', 'feed_direction', 'angle',
                        'penetration',
                        'feed_first', 'feed_middle', 'feed_last',
                        'speed']),
                StepsNum=dict(
                    same_controls=[
                        'operation_type', 'deformation_control', 'step_control',
                        'feed_direction', 'angle',
                        'penetration',
                        'num_of_bites'],
                    NA=[
                        'operation_type', 'deformation_control', 'step_control',
                        'press', 'die', 'feed_direction', 'angle',
                        'penetration',
                        'num_of_bites',
                        'speed'])),
            H=dict(
                Feed=dict(
                    same_controls=[
                        'operation_type', 'deformation_control', 'step_control',
                        'feed_direction', 'angle',
                        'final_height',
                        'feed_first', 'feed_middle', 'feed_last'],
                    NA=[
                        'operation_type', 'deformation_control', 'step_control',
                        'press', 'die', 'feed_direction', 'angle',
                        'final_height',
                        'feed_first', 'feed_middle', 'feed_last',
                        'speed']),
                StepsNum=dict(
                    same_controls=[
                        'operation_type', 'deformation_control', 'step_control',
                        'feed_direction', 'angle',
                        'final_height',
                        'num_of_bites'],
                    NA=[
                        'operation_type', 'deformation_control', 'step_control',
                        'press', 'die', 'feed_direction', 'angle',
                        'final_height',
                        'num_of_bites',
                        'speed']))),
        Upset={
            'E': {
                'Feed': {
                    'same_controls': [
                        'operation_type', 'deformation_control', 'step_control', 'feed_direction',
                        'relative_deformation', 'feed_first', 'feed_middle', 'feed_last'],
                    'NA': [
                        'operation_type', 'deformation_control', 'step_control', 'press', 'die', 'feed_direction',
                        'relative_deformation', 'feed_first', 'feed_middle', 'feed_last', 'speed']},
                'StepsNum': {
                    'same_controls': [
                        'operation_type', 'deformation_control', 'step_control', 'feed_direction',
                        'relative_deformation', 'num_of_bites'],
                    'NA': [
                        'operation_type', 'deformation_control', 'step_control', 'press', 'die', 'feed_direction',
                        'relative_deformation', 'num_of_bites', 'speed']},
                'OneStrictly': {
                    'same_controls': [
                        'operation_type', 'deformation_control', 'step_control', 'relative_deformation'],
                    'NA': [
                        'operation_type', 'deformation_control', 'step_control', 'press', 'die',
                        'relative_deformation', 'speed']},
                'Three(Mid+L+R)': {
                    'same_controls': [
                        'operation_type', 'deformation_control', 'step_control', 'feed_direction',
                        'relative_deformation'],
                    'NA': [
                        'operation_type', 'deformation_control', 'step_control', 'press', 'die', 'feed_direction',
                        'relative_deformation', 'speed']},
                'OneOrThree': {
                    'same_controls': [
                        'operation_type', 'deformation_control', 'step_control', 'feed_direction',
                        'relative_deformation'],
                    'NA': [
                        'operation_type', 'deformation_control', 'step_control', 'press', 'die', 'feed_direction',
                        'relative_deformation', 'speed']}},
            'P': {
                'Feed': {
                    'same_controls': [
                        'operation_type', 'deformation_control', 'step_control', 'feed_direction',
                        'penetration', 'feed_first', 'feed_middle', 'feed_last'],
                    'NA': [
                        'operation_type', 'deformation_control', 'step_control', 'press', 'die', 'feed_direction',
                        'penetration', 'feed_first', 'feed_middle', 'feed_last', 'speed']},
                'StepsNum': {
                    'same_controls': [
                        'operation_type', 'deformation_control', 'step_control', 'feed_direction',
                        'penetration', 'num_of_bites'],
                    'NA': [
                        'operation_type', 'deformation_control', 'step_control', 'press', 'die', 'feed_direction',
                        'penetration', 'num_of_bites', 'speed']},
                'OneStrictly': {
                    'same_controls': [
                        'operation_type', 'deformation_control', 'step_control', 'penetration'],
                    'NA': [
                        'operation_type', 'deformation_control', 'step_control', 'press', 'die',
                        'penetration', 'speed']},
                'Three(Mid+L+R)': {
                    'same_controls': [
                        'operation_type', 'deformation_control', 'step_control', 'feed_direction',
                        'penetration'],
                    'NA': [
                        'operation_type', 'deformation_control', 'step_control', 'press', 'die', 'feed_direction',
                        'penetration', 'speed']},
                'OneOrThree': {
                    'same_controls': [
                        'operation_type', 'deformation_control', 'step_control', 'feed_direction',
                        'penetration'],
                    'NA': [
                        'operation_type', 'deformation_control', 'step_control', 'press', 'die', 'feed_direction',
                        'penetration', 'speed']}},
            'H': {
                'Feed': {
                    'same_controls': [
                        'operation_type', 'deformation_control', 'step_control', 'feed_direction',
                        'final_length', 'feed_first', 'feed_middle', 'feed_last'],
                    'NA': [
                        'operation_type', 'deformation_control', 'step_control', 'press', 'die', 'feed_direction',
                        'final_length', 'feed_first', 'feed_middle', 'feed_last', 'speed']},
                'StepsNum': {
                    'same_controls': [
                        'operation_type', 'deformation_control', 'step_control', 'feed_direction',
                        'final_length', 'num_of_bites'],
                    'NA': [
                        'operation_type', 'deformation_control', 'step_control', 'press', 'die', 'feed_direction',
                        'final_length', 'num_of_bites', 'speed']},
                'OneStrictly': {
                    'same_controls': [
                        'operation_type', 'deformation_control', 'step_control', 'final_length'],
                    'NA': [
                        'operation_type', 'deformation_control', 'step_control', 'press', 'die',
                        'final_length', 'speed']},
                'Three(Mid+L+R)': {
                    'same_controls': [
                        'operation_type', 'deformation_control', 'step_control', 'feed_direction',
                        'final_length'],
                    'NA': [
                        'operation_type', 'deformation_control', 'step_control', 'press', 'die', 'feed_direction',
                        'final_length', 'speed']},
                'OneOrThree': {
                    'same_controls': [
                        'operation_type', 'deformation_control', 'step_control', 'feed_direction',
                        'final_length'],
                    'NA': [
                        'operation_type', 'deformation_control', 'step_control', 'press', 'die', 'feed_direction',
                        'final_length', 'speed']}}},
        Cut=dict(
            Equals={
                'k1-PcNum': {
                    'NA': [
                        'operation_type', 'step_control',
                        'press', 'die', 'feed_direction',
                        'k1', 'num_of_bites', 'scrap_rate',
                        'speed']}},
            KeepFirst=dict(
                Length=dict(NA=[
                    'operation_type', 'deformation_control', 'step_control',
                    'press', 'die', 'feed_direction',
                    'final_length', 'scrap_rate',
                    'speed']),
                Percent=dict(NA=[
                    'operation_type', 'deformation_control', 'step_control',
                    'press', 'die', 'feed_direction',
                    'relative_deformation', 'scrap_rate',
                    'speed'])),
            DeleteFirst=dict(
                Length=dict(NA=[
                    'operation_type', 'deformation_control', 'step_control',
                    'press', 'die', 'feed_direction',
                    'penetration', 'scrap_rate',
                    'speed']),
                Percent=dict(NA=[
                    'operation_type', 'deformation_control', 'step_control',
                    'press', 'die', 'feed_direction',
                    'relative_deformation', 'scrap_rate',
                    'speed']))),
        Heat=dict(
            NA=dict(
                NA=dict(
                    NA=[
                        'operation_type', 'press', 'die',
                        'max_temperature', 'operation_time', 'time_before_pass', 'scrap_rate']))),
        Pause=dict(
            NA=dict(
                NA=dict(
                    NA=['operation_type', 'press', 'die', 'time_before_pass_minutes'])))))
