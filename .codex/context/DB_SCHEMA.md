---
apply: always
---

# Database Schema

## Scope
This file is the source of truth for the current PostgreSQL schema snapshot used by the backend.

It covers:
- active Alembic baseline/head context
- public-schema table inventory
- key columns and relationships for each table
- important JSONB payload shapes that are relied on by code and seeding

If source code or migrations conflict with this file, source code is authoritative and this file must be updated.

## DB consistency snapshot (updated 2026-04-07)
- Alembic code state:
  - current head migration file: `d2c6e8a4b9f1_change_material_name_to_varchar.py`
- Baseline remains `9ac4e7b1d2f3_squashed_current_schema_baseline.py`
- Current schema shape of note:
  - `projects.material_id` points to `materials.material_id`
  - `materials` is now a thin canonical root table with plain-text `name`, `deform_file_name`, `note`, `is_obsolete`, `owner_id`
  - shared material classification uses normalized tables: `material_classification_axes`, `material_classification_values`, `material_classification_assignments`
  - `material_classification_axes.hierarchy_level` defines the dashboard/filter tree: level 1 = object type, level 2 = composition base, level 3 = all other categories
  - material standards/documents and material-specific designations use normalized tables: `material_standards_catalog`, `materials_designations`
  - material chemistry/publication data uses normalized tables: `publications_catalog`, `materials_designations_standard_chemistry`, `materials_test_records`, `materials_chemistry_tests_results`
  - test-record-linked property datasets use normalized tables: `materials_property_tables`, `materials_property_table_to_columns_connectivity`, `materials_property_column_values`
- Verification status:
  - frontend `npm run typecheck` passes after the materials update
  - backend `python3 -m compileall backend/app backend/alembic/versions backend/db_setup/reinit_db.py` passes
  - backend automated tests are unavailable because `pytest` is not installed in `backend/.venv`

## Public schema table inventory
- Tables currently present:
  - `alembic_version`
  - `blocks`
  - `config`
  - `devices`
  - `die_assemblies`
  - `die_types`
  - `dies`
  - `document_acl`
  - `document_edit_sessions`
  - `document_versions`
  - `documents`
  - `library`
  - `logs`
  - `material_classification_assignments`
  - `material_classification_axes`
  - `material_classification_values`
  - `material_standards_catalog`
  - `materials`
  - `materials_chemistry_tests_results`
  - `materials_designations`
  - `materials_designations_standard_chemistry`
  - `materials_property_column_values`
  - `materials_property_table_to_columns_connectivity`
  - `materials_property_tables`
  - `materials_test_records`
  - `operations_library`
  - `physical_machines`
  - `press_die_map`
  - `press_modes`
  - `presses`
  - `projects`
  - `publications_catalog`
  - `servers`
  - `settings`
  - `share_links`
  - `time_between_operations`
  - `users`

## Core editor and auth tables
- `users`
  - `user_id`, `login`, `email`, `password_hashed`, `signal_clear_token`, `supervisor_id`, `full_name`, `language_code`, `user_settings`, `user_priority_enum`, `created_at`
- `projects`
  - `project_id`, `user_id` (FK `users.user_id`), `material_id` (FK `materials.material_id`), `name`, `notes`, `created_at`, `updated_at`, `deleted_at`
- `documents`
  - `document_id`, `project_id`, `source_document_id`, `editor_user_id`, `first_block_id`, `name`, `notes`, `created_at`, `updated_at`, `deleted_at`
- `blocks`
  - `block_id`, `document_id`, `previous_block_id`, `next_block_id`, `block_type_id`, `props` (JSONB), `created_at`, `updated_at`, `is_system`, `is_removable`, `fixed_position`
- `settings`
  - `setting_id`, `key`, `value` (JSONB), `scope`, `user_id`
  - unique index on (`key`, `scope`, `user_id`)

## Industrial and library normalized tables
- `die_types`
  - `id`, `name` (JSONB)
- `materials`
  - `material_id`, `name` (VARCHAR), `deform_file_name`, `note`, `is_obsolete`, `owner_id` (FK `users.user_id`)
- `material_standards_catalog`
  - `standard_id`, `predecessor_standard_id` (self FK), `issue_organization`, `issue_year`, `geographic_level`, `country_or_region`, `title` (JSONB), `standard_number`, `url`, `file_name`, `is_obsolete`, `created_at`, `updated_at`
- `materials_designations`
  - `designation_id`, `designation`, `material_id` (FK `materials.material_id`), `standard_id` (nullable FK `material_standards_catalog.standard_id`), `is_main_designation`, `note`, `is_obsolete`, `created_at`, `updated_at`
- `publications_catalog`
  - `publication_id`, `source_type`, `title`, `authors_text`, `publisher_or_journal`, `issue_year`, `doi`, `url`, `file_name`, `note`, `is_obsolete`, `created_at`, `updated_at`
- `materials_designations_standard_chemistry`
  - `standard_chemistry_id`, `designation_id` (FK `materials_designations.designation_id`), `element_symbol`, `min_wt_pct`, `max_wt_pct`, `is_balance`, `note`, `is_obsolete`, `created_at`, `updated_at`
- `materials_test_records`
  - `test_record_id`, `material_id` (FK `materials.material_id`), `designation_id` (nullable FK `materials_designations.designation_id`), `publication_id` (nullable FK `publications_catalog.publication_id`), `heat_number`, `batch_number`, `sample_label`, `test_date`, `note`, `is_obsolete`, `created_at`, `updated_at`
- `materials_chemistry_tests_results`
  - composite PK (`test_record_id`, `element_symbol`)
  - `actual_wt_pct`
  - DB trigger updates parent `materials_test_records.updated_at` on insert, update, and delete
- `materials_property_tables`
  - `table_id`, `test_record_id` (FK `materials_test_records.test_record_id`), `property_type`, `representation_kind`, `replicate_no`, `conditions` (JSONB), `title`, `note`, `is_obsolete`, `created_at`, `updated_at`
- `materials_property_table_to_columns_connectivity`
  - `column_id`, `table_id` (FK `materials_property_tables.table_id`), `column_property_type`, `column_units`, `sort_order`
- `materials_property_column_values`
  - composite PK (`column_id`, `point_index`)
  - `value` (NUMERIC)
  - child-table triggers update parent `materials_property_tables.updated_at`, and parent-table triggers propagate freshness to `materials_test_records.updated_at`
- `material_classification_axes`
  - `axis_id`, `key`, `name` (JSONB), `description` (JSONB), `selection_mode`, `hierarchy_level`, `sort_order`, `is_filter_visible`, `is_obsolete`, `created_at`, `created_by_user_id` (FK `users.user_id`)
- `material_classification_values`
  - `value_id`, `axis_id` (FK `material_classification_axes.axis_id`), `key`, `name` (JSONB), `color`, `sort_order`, `is_obsolete`, `created_at`, `created_by_user_id` (FK `users.user_id`)
- `material_classification_assignments`
  - composite PK (`material_id`, `value_id`)
  - `created_at`, `created_by_user_id` (FK `users.user_id`)
- `dies`
  - `id`, `name` (JSONB), `die_type_id` (FK `die_types.id`), `die_template_file_name`, `inventory_number`, `properties` (JSONB), `is_obsolete`, `created_at`, `obsolete_at`, `owner_user_id` (FK `users.user_id`)
- `die_assemblies`
  - `id`, `name` (JSONB), `is_obsolete`, `created_at`, `obsolete_at`, `top_die_id`, `bottom_die_id`, `left_die_id`, `right_die_id` (FKs to `dies.id`), `owner_user_id` (FK `users.user_id`)
- `presses`
  - `id`, `name` (JSONB), `is_obsolete`, `created_at`, `obsolete_at`, `owner_user_id` (FK `users.user_id`)
- `press_modes`
  - `id`, `press_id` (FK `presses.id`), `name` (JSONB, nullable), `owner_user_id` (FK `users.user_id`), `is_obsolete`, `created_at`, `obsolete_at`, `properties` (JSONB), `is_default_press_mode`
- `press_die_map`
  - composite PK (`press_id`, `die_id`)
  - `is_matching_as_top`, `is_matching_as_bottom`, `is_matching_as_left`, `is_matching_as_right`, `owner_user_id`, `is_obsolete`, `created_at`, `obsolete_at`

## Unified library table
- `library`
  - `id`, `parent_id` (self FK), `type`, `name`, `props` (JSONB), `created_at`, `updated_at`, `is_obsolete`

## JSONB structures and seeded payload shapes
- All JSON-like columns are JSONB. There are no remaining `json` columns in `public`.
- Localization name objects (`die_types.name`, `dies.name`, `die_assemblies.name`, `presses.name`, `press_modes.name`) use the same multilingual map structure:
  - observed keys: `EN`, `RU`, `ZH_HANS`
  - values: localized strings
- `materials.name` is now plain text; national/regional naming belongs in `materials_designations`.
- `material_classification_axes.name`, `material_classification_axes.description`, and `material_classification_values.name` follow the same multilingual JSONB pattern.
- Current seeded hierarchy for `backend/data/database_seeding/materials.json`:
  - `object_type` -> level `1`
  - `composition` (`Composition Base`) -> level `2`
  - all remaining material-classification axes -> level `3`
- `backend/data/database_seeding/materials.json` now includes fully populated normalized-material examples for:
  - `Ti-6Al-4V` sourced from `backend_obsolete/TI64.md`
  - `Inconel 718` sourced from `backend_obsolete/Inc718.md`
  - `Waspaloy` sourced from `backend_obsolete/waspaloy.md`
  Each example can populate:
  - canonical `materials[]` note / DEFORM file reference
  - `material_standards_catalog[]`
  - `materials_designations[]`
  - `publications_catalog[]`
  - `materials_designations_standard_chemistry[]`
  - `materials_test_records[]`
  - `materials_chemistry_tests_results[]`
  - `materials_property_tables[]`
  - `materials_property_table_to_columns_connectivity[]`
  - `materials_property_column_values[]`
- `dies.properties` seed structure:
  - numeric keys observed: `total_length`, `total_width`, `height`, `straight_length`, `edge_radius`, `edge_angle`
- `press_modes.properties` seed structure:
  - scalar keys: `is_left_manipulator`, `is_right_manipulator`, `automatic_feed_mode_is_on_when_bites_count`, `max_force`, `back_speed`, `idle_speed`, `working_speed`, `min_dwell_speed`, `max_dwell_time`, `min_idle_stroke`, `max_idle_stroke`, `approaching_distance`, `open_height_without_dies`
  - array key: `power_limit` -> list of objects with keys `id`, `force`, `speed`
- `blocks.props`
  - `document_heading`: stores block fields (`heat_no`, `finished_size`, `stock_size`, `stock_weight`, `remarks`, `preview_status`), then is enriched for read responses with document metadata (`name`, `project_id`, `source_document_id`, `editor_user_id`, `created_at`, `updated_at`) and optional nested `version`
  - `input_workpiece`: `geometry_type_id`, `mesh_elements`, `weight`, `attributes` (dynamic object), and response-enriched fields (`title`, `available_geometry_types`, optional `selected_geometry`)
  - basic text blocks (`paragraph`, `heading1`, `heading2`, `list`, `code`, `quote`) store `text`
  - `todo` stores `text` and `checked`
  - `divider` typically has an empty object

## Database seeding layout
- Database seeding reads two files from `backend/data/database_seeding/`
  - `library.json` for shared library sections such as `users`, `die_types`, `dies`, `die_assemblies`, `presses`, `press_modes`, and `press_die_map`
  - `materials.json` for the normalized materials domain seed sections
- `backend/data/database_seeding/materials.json` may store top-level:
  - current committed example coverage includes Ti-6Al-4V, Inconel 718, and Waspaloy across the standards, designation, publication, chemistry, test-record, and property-table sections
  - `materials[]`
  - `material_standards_catalog[]`
  - `materials_designations[]`
  - `publications_catalog[]`
  - `materials_designations_standard_chemistry[]`
  - `materials_test_records[]`
  - `materials_chemistry_tests_results[]`
  - `materials_property_tables[]`
  - `materials_property_table_to_columns_connectivity[]`
  - `materials_property_column_values[]`
  - `material_classification_axes[]`
  - `material_classification_values[]`
  - `material_classification_assignments[]`
- These sections seed directly into the corresponding normalized tables when present.
- Waspaloy is currently seeded without a DEFORM source file (`materials.deform_file_name = null`), so it is present in the normalized materials domain but has no DEFORM-backed visuals until such a file is added.
