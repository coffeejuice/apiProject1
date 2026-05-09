---
apply: always
---

# Old Backend Migration Map

## Purpose
This file maps legacy modules from `backend_old/` into the new backend runtime layout under `backend/app/`.

This map is intentionally migration-oriented:
- it identifies the target area for each old module
- it marks whether logic should be ported, split, deferred, or dropped
- it treats the new backend architecture as authoritative for orchestration shape

## Status Legend
- `port`: move most of the useful logic with moderate adaptation
- `split`: break old module into several new modules; do not copy as-is
- `defer`: keep as reference only for now
- `drop`: no direct runtime port planned

## New Target Layout
- `backend/app/orchestration/`: DB-backed queue claims, LISTEN/NOTIFY, coordinator, leases, workflow state
- `backend/app/workers/`: thin worker entrypoints only
- `backend/app/services/preprocessor/`: document/process preprocessing into control-program records
- `backend/app/services/solver/`: single-step solver execution and DEFORM integration
- `backend/app/services/postprocess/`: reports, images, PPT/PDF generation
- `backend/app/services/files/`: file paths, storage, shared/local artifact movement
- `backend/deploy/windows/`: Windows installer and service-registration scripts
- `backend/db_setup/`, `backend/alembic/`, `backend/scripts/`: schema/bootstrap/one-off conversion utilities

## Runtime Schema Migration Notes
- Old `operation` terminology should be translated to new `block` terminology.
- Planned runtime table naming:
  - old `server_pre_main` -> split into:
    - `simulation_steps`
    - `simulation_step_status`
    - `postprocessing_tasks`
  - old `post_operations` data moves into `postprocessing_tasks`
- Current `simulation_steps` semantics:
  - use `document_operation_id` as the primary key and sibling identity for the source `document_operations` row
  - do not use old numeric `operation_type_id`, `parent_operation_type_id`, or `block_type_id` in active runtime dispatch
  - use semantic `operation_template_id`, `operation_kind`, and `source_block_id` snapshots for traceability
  - create/remove sibling `simulation_steps` rows together with regenerated `document_operations`; valid operation rows set `preprocess_ready = true`
  - do not keep old `is_simulation` branching; every valid materialized operation follows the same simulation-step path
- Planned timing field naming:
  - `time_before_operation_seconds` -> `accumulated_time_start_seconds`
  - `total_time_seconds` -> `accumulated_time_stop_seconds`
- Planned runtime estimate placement:
  - move step runtime estimate out of `simulation_steps`
  - use `simulation_step_status.simulation_expected_duration_seconds`
  - do not keep `simulation_expected_duration_days` in `simulation_steps`

## Implemented Schema Changes
- `blocks` table was renamed to `document_blocks`.
- `operations_library` table was renamed to `document_blocks_library`.
- `material_versions` table was added.
  - `projects.material_id` still points to the project-level material root.
  - `documents.material_version_id` now points to the selected material version.
  - `simulation_steps.material_version_id` is now a real FK to `material_versions.material_version_id`.

## Consolidated Runtime Schema Specification
This is the accepted target split for the old `server_pre_main` / `post_operations` runtime data.

### `simulation_steps`
Sibling execution rows for `document_operations`; `Pre` later fills compiled step definitions.

| Column | Type | FK / Rule | Meaning |
|---|---|---|---|
| `document_operation_id` | `BIGINT NOT NULL` | PK + FK -> `document_operations.document_operation_id` `ON DELETE CASCADE` | Source operation and step identity |
| `document_version_id` | `BIGINT NOT NULL` | FK -> `document_versions.document_version_id` `ON DELETE CASCADE` | Parent document version/run |
| `execution_order` | `INT NOT NULL` | `UNIQUE(document_version_id, execution_order)` | Step order inside one run |
| `source_block_id` | `UUID NULL` | FK -> `document_blocks.block_id` `ON DELETE SET NULL` | Source user block/card |
| `operation_template_id` | `VARCHAR(255) NULL` |  | Semantic operation template id |
| `operation_kind` | `VARCHAR(63) NOT NULL` |  | Semantic operation kind |
| `operation_label_snapshot` | `VARCHAR(255) NULL` |  | Stable operation label |
| `preprocess_ready` | `BOOLEAN NOT NULL DEFAULT FALSE` |  | Row is valid and ready for Pre calculation |
| `block_name_snapshot` | `VARCHAR(255) NOT NULL` |  | Stable user-facing block name |
| `library_name_snapshot` | `VARCHAR(255) NOT NULL` |  | Stable library label |
| `material_version_id` | `INT NULL` | FK -> `material_versions.material_version_id` `ON DELETE SET NULL` | Versioned material reference |
| `press_id` | `INT NULL` | FK -> `presses.id` `ON DELETE SET NULL` | Press |
| `press_mode_id` | `INT NULL` | FK -> `press_modes.id` `ON DELETE SET NULL` | Press mode |
| `die_assembly_id` | `INT NULL` | FK -> `die_assemblies.id` `ON DELETE SET NULL` | Die assembly |
| `top_die_id` | `INT NULL` | FK -> `dies.id` `ON DELETE SET NULL` | Top die |
| `bottom_die_id` | `INT NULL` | FK -> `dies.id` `ON DELETE SET NULL` | Bottom die |
| `left_die_id` | `INT NULL` | FK -> `dies.id` `ON DELETE SET NULL` | Left die |
| `right_die_id` | `INT NULL` | FK -> `dies.id` `ON DELETE SET NULL` | Right die |
| `parameter_values` | `JSONB NOT NULL DEFAULT '{}'` |  | Raw normalized block values |
| `control_parameters` | `JSONB NOT NULL DEFAULT '{}'` |  | Solver control inputs |
| `step_specific_parameters` | `JSONB NOT NULL DEFAULT '{}'` |  | Precomputed step-specific payload |
| `initial_geometry` | `JSONB NULL` |  | Geometry before this step |
| `final_geometry` | `JSONB NULL` |  | Expected geometry after this step |
| `metrics` | `JSONB NOT NULL DEFAULT '{}'` |  | Calculated scalar values |
| `accumulated_time_start_seconds` | `DOUBLE PRECISION NULL` |  | Absolute start time on compiled process timeline |
| `duration_seconds` | `DOUBLE PRECISION NULL` |  | Step duration estimate |
| `accumulated_time_stop_seconds` | `DOUBLE PRECISION NULL` |  | Absolute stop time on compiled process timeline |
| `created_at` | `TIMESTAMP NOT NULL DEFAULT NOW()` |  | Audit |
| `updated_at` | `TIMESTAMP NOT NULL DEFAULT NOW()` |  | Audit |

Accepted notes:
- Runtime execution is keyed by semantic operation rows, not by old numeric operation IDs.
- Do not keep old `parent_operation_type_id`; the new document block model is flat.
- `source_block_id` now follows the `document_blocks` naming.

### `simulation_step_status`
Mutable runtime state for one compiled simulation step.

| Column | Type | FK / Rule | Meaning |
|---|---|---|---|
| `document_operation_id` | `BIGINT NOT NULL` | PK + FK -> `simulation_steps.document_operation_id` `ON DELETE CASCADE` | Status row for one compiled step |
| `status` | `simulation_step_status_enum NOT NULL` | values: `blocked`, `queued`, `running`, `finished`, `failed`, `cancelled` | Current solver state |
| `simulation_server_id` | `INT NULL` | FK -> `servers.id` `ON DELETE SET NULL` | Assigned solver PC |
| `worker_name` | `VARCHAR(255) NULL` |  | Worker instance name |
| `attempt_no` | `INT NOT NULL DEFAULT 1` |  | Current attempt number |
| `retry_count` | `INT NOT NULL DEFAULT 0` |  | Retry counter |
| `cancel_requested` | `BOOLEAN NOT NULL DEFAULT FALSE` |  | Graceful cancel request flag |
| `simulation_percent` | `SMALLINT NOT NULL DEFAULT 0` |  | Current step progress |
| `simulation_expected_duration_seconds` | `DOUBLE PRECISION NULL` |  | Expected solver duration for this step |
| `queued_at` | `TIMESTAMP NULL` |  | When step became runnable |
| `started_at` | `TIMESTAMP NULL` |  | When current attempt started |
| `heartbeat_at` | `TIMESTAMP NULL` |  | Last worker heartbeat |
| `finished_at` | `TIMESTAMP NULL` |  | When step finished |
| `runtime_artifacts` | `JSONB NOT NULL DEFAULT '{}'` |  | Runtime paths and generated files |
| `last_error` | `TEXT NULL` |  | Last error message |
| `error_payload` | `JSONB NULL` |  | Structured error/debug data |
| `updated_at` | `TIMESTAMP NOT NULL DEFAULT NOW()` |  | Audit timestamp |

### `postprocessing_tasks`
Mutable postprocessing queue and output records derived from simulation steps.

| Column | Type | FK / Rule | Meaning |
|---|---|---|---|
| `postprocessing_task_id` | `BIGSERIAL` | PK | Task id |
| `document_operation_id` | `BIGINT NOT NULL` | FK -> `simulation_steps.document_operation_id` `ON DELETE CASCADE` | Source compiled step |
| `task_kind` | `VARCHAR(63) NOT NULL DEFAULT 'full'` | `UNIQUE(document_operation_id, task_kind)` | Postprocessing task type |
| `status` | `postprocessing_task_status_enum NOT NULL` | values: `queued`, `running`, `finished`, `failed`, `cancelled` | Current post state |
| `postprocessing_server_id` | `INT NULL` | FK -> `servers.id` `ON DELETE SET NULL` | Assigned post worker PC |
| `worker_name` | `VARCHAR(255) NULL` |  | Worker instance name |
| `retry_count` | `INT NOT NULL DEFAULT 0` |  | Retry counter |
| `queued_at` | `TIMESTAMP NULL` |  | When task entered queue |
| `started_at` | `TIMESTAMP NULL` |  | When post started |
| `heartbeat_at` | `TIMESTAMP NULL` |  | Last worker heartbeat |
| `finished_at` | `TIMESTAMP NULL` |  | When post finished |
| `input_payload` | `JSONB NOT NULL DEFAULT '{}'` |  | Input params for postprocessing |
| `output_payload` | `JSONB NOT NULL DEFAULT '{}'` |  | Structured result summary |
| `images_dir_path` | `VARCHAR(2047) NULL` |  | Output images directory |
| `pptx_file_name` | `VARCHAR(255) NULL` |  | Generated PPTX |
| `pdf_file_name` | `VARCHAR(255) NULL` |  | Generated PDF |
| `last_error` | `TEXT NULL` |  | Last error message |
| `error_payload` | `JSONB NULL` |  | Structured error/debug data |
| `updated_at` | `TIMESTAMP NOT NULL DEFAULT NOW()` |  | Audit timestamp |

## Top-Level Runtime Modules
- `backend_old/forgelab/server.py`
  - Target: `backend/app/orchestration/coordinator.py`, `backend/app/orchestration/claims.py`, `backend/app/orchestration/leases.py`, `backend/app/workers/*.py`
  - Status: `split`
  - Notes: keep workflow ideas only; remove in-memory queues, semaphores, and parent-owned worker pools.

- `backend_old/forgelab/config.py`
  - Target: `backend/app/config.py`, `backend/app/services/files/paths.py`, `backend/deploy/windows/*.ps1`
  - Status: `split`
  - Notes: preserve settings concepts and host/runtime paths; do not port legacy singleton + threaded connection-pool shape.

- `backend_old/forgelab/notifications_listener_service.py`
  - Target: `backend/app/orchestration/pg_notify.py`
  - Status: `port`
  - Notes: preserve LISTEN/NOTIFY socket-wait pattern; remove coupling to local multiprocessing queues.

- `backend_old/forgelab/service_file_remover.py`
  - Target: `backend/app/services/files/storage.py`, `backend/app/orchestration/coordinator.py`
  - Status: `split`
  - Notes: keep artifact-cleanup logic; trigger it from explicit reconciliation/cleanup flows instead of a hidden helper thread.

- `backend_old/forgelab/plot_service.py`
  - Target: none
  - Status: `drop`
  - Notes: commented-out/obsolete runtime path.

- `backend_old/forgelab/plot_service_2.py`
  - Target: `backend/scripts/` if later needed for experiments only
  - Status: `defer`
  - Notes: not part of the planned runtime.

## Preprocessing Area
- Current migrated compiler support:
  - billet geometry cards `68..79`
  - furnace operation `10` with merged furnace class and initial temperature fields
  - deformation requirement operation `26` with merged press, speed, and feed fields accumulated into forming simulation rows
  - heating operation `23`
  - upsetting operations `91`, `92`, `93`, `94`, `100`
  - axial prolongation operations `46`, `83`, `90`
  - spiral prolongation operations `50`, `51`
  - radial prolongation operations `95`, `96`, legacy `80`, `82`
- Current prolongation implementation lives in `backend/app/services/preprocessor/prolongation.py`.
  - It ports feed/bite table construction, deformation/timing state, rotations metadata, and final-geometry propagation into a dependency-light implementation.
  - It now uses `backend/app/services/preprocessor/prolongation_geometry.py` for the Shapely-backed die/polygon path migrated from `common/shapely_2d_funcs.py`.
  - The migrated Shapely path covers polygon conversion, die gap positioning, final die positioning, vertical pre-scaling, split-line trimming, contact-width optimization, middle-zone reconstruction, and area/height validation.
  - If Shapely is unavailable or the trim result fails quality checks, prolongation falls back to deterministic dependency-light scaling and records a compiler note.
  - The old STL die-section import path is not ported; the new path reconstructs simplified 2D die cross-sections from `dies.properties` dimensions.
- `simulation_steps.source_block_id` is now populated from the source `document_blocks.block_id` when the runtime pre worker compiles a document.

- `backend_old/forgelab/srv_pre/pre_worker_class.py`
  - Target: `backend/app/workers/pre_worker.py`, `backend/app/services/preprocessor/compiler.py`, `backend/app/services/preprocessor/control_program_builder.py`
  - Status: `split`
  - Notes: thin worker shell goes into `workers/`; process-analysis and control-program generation logic goes into `services/preprocessor/`.

- `backend_old/forgelab/srv_pre/geometry_class.py`
  - Target: `backend/app/services/preprocessor/` as a future geometry helper module
  - Status: `port`
  - Notes: keep geometry-domain logic, but do not leave it embedded in worker code.

## Solver Area
- `backend_old/forgelab/srv_solver/simulation_worker_class.py`
  - Target: `backend/app/workers/solver_worker.py`, `backend/app/services/solver/runner.py`, `backend/app/services/solver/step_executor.py`
  - Status: `split`
  - Notes: worker loop stays thin; DB/file/DEFORM step execution moves into solver services.

- `backend_old/forgelab/srv_solver/solver_functions.py`
  - Target: `backend/app/services/solver/runner.py`
  - Status: `port`
  - Notes: keep DEFORM launch/execution helpers, adapted to new runtime state model.

- `backend_old/forgelab/srv_solver/pre_functions.py`
  - Target: `backend/app/services/solver/deform_io.py`, `backend/app/services/files/storage.py`
  - Status: `split`
  - Notes: this contains useful file-template mutation logic, but it is too broad to port as one module.

- `backend_old/forgelab/srv_solver/import_last_step_parameters.py`
  - Target: `backend/app/services/solver/step_executor.py`
  - Status: `port`
  - Notes: keep if still needed for chaining one solver step into the next.

- `backend_old/forgelab/srv_solver/shapely_functions.py`
  - Target: `backend/app/services/solver/` as a future geometry helper module
  - Status: `defer`
  - Notes: review overlap with `common/shapely_2d_funcs.py` before porting.

- `backend_old/forgelab/srv_solver/plot_2d.py`
  - Target: `backend/scripts/` or tests only
  - Status: `defer`
  - Notes: not part of first runtime migration.

### Solver Operations Modules
- `backend_old/forgelab/srv_solver/operations/billet.py`
  - Target: `backend/app/services/solver/operations/billet.py`
  - Status: `port`

- `backend_old/forgelab/srv_solver/operations/cogging_bite.py`
  - Target: `backend/app/services/solver/operations/cogging_bite.py`
  - Status: `port`

- `backend_old/forgelab/srv_solver/operations/cut.py`
  - Target: `backend/app/services/solver/operations/cut.py`
  - Status: `port`

- `backend_old/forgelab/srv_solver/operations/forming_frozen_speed_window_boxes.py`
  - Target: `backend/app/services/solver/operations/forming_frozen_speed_window_boxes.py`
  - Status: `port`

- `backend_old/forgelab/srv_solver/operations/heat.py`
  - Target: `backend/app/services/solver/operations/heat.py`
  - Status: `port`

- `backend_old/forgelab/srv_solver/operations/offset_and_rotation.py`
  - Target: `backend/app/services/solver/operations/offset_and_rotation.py`
  - Status: `port`

- `backend_old/forgelab/srv_solver/operations/remesh.py`
  - Target: `backend/app/services/solver/operations/remesh.py`
  - Status: `port`

## Postprocessing Area
- `backend_old/forgelab/srv_post/post_worker_class.py`
  - Target: `backend/app/workers/post_worker.py`, `backend/app/services/postprocess/reporter.py`, `backend/app/services/postprocess/image_generation.py`, `backend/app/services/postprocess/ppt_builder.py`
  - Status: `split`
  - Notes: worker loop becomes thin; artifact/report generation becomes service logic.

- `backend_old/forgelab/srv_post/gen_ppt.py`
  - Target: `backend/app/services/postprocess/ppt_builder.py`
  - Status: `port`
  - Notes: likely near-direct port with path/config cleanup.

- `backend_old/forgelab/srv_post/mayavi_worker_class.py`
  - Target: `backend/app/services/postprocess/image_generation.py` and possibly a future dedicated render worker
  - Status: `split`
  - Notes: keep rendering logic; re-evaluate whether a separate render pool is needed in v1.

- `backend_old/forgelab/srv_post/tensor_variables.py`
  - Target: `backend/app/services/postprocess/image_generation.py`
  - Status: `port`

## Shared Common Modules
- `backend_old/forgelab/common/boundary_conditions.py`
  - Target: `backend/app/services/solver/` as a future boundary-condition helper module
  - Status: `port`

- `backend_old/forgelab/common/common_funcs.py`
  - Target: `backend/app/services/files/storage.py`, `backend/app/workers/base.py`
  - Status: `split`
  - Notes: keep only reusable helpers; drop broad miscellaneous catch-all structure.

- `backend_old/forgelab/common/file_operations.py`
  - Target: `backend/app/services/files/paths.py`, `backend/app/services/files/storage.py`
  - Status: `split`
  - Notes: this is a major migration source for path generation, directory cleanup, and artifact movement.

- `backend_old/forgelab/common/fluent_bit_logger.py`
  - Target: `backend/app/` logging setup only if still operationally needed
  - Status: `defer`
  - Notes: do not block core migration on Fluent Bit integration.

- `backend_old/forgelab/common/library_sql_query.py`
  - Target: `backend/app/services/preprocessor/control_program_builder.py`, `backend/app/services/library_seed_service.py`
  - Status: `split`
  - Notes: separate runtime library reads from one-time conversion/seeding helpers.

- `backend_old/forgelab/common/matlib.py`
  - Target: `backend/app/services/preprocessor/` or `backend/app/services/solver/`
  - Status: `defer`
  - Notes: review actual runtime use before creating a dedicated new module.

- `backend_old/forgelab/common/plot_funcs.py`
  - Target: `backend/scripts/` or tests only
  - Status: `defer`

- `backend_old/forgelab/common/queries.py`
  - Target: `backend/app/orchestration/claims.py`, `backend/app/services/solver/runner.py`, `backend/app/services/postprocess/reporter.py`
  - Status: `split`
  - Notes: legacy-table queries must be rewritten against the new state model, not ported verbatim.

- `backend_old/forgelab/common/read_deform_keyfile.py`
  - Target: `backend/app/services/solver/deform_io.py`, `backend/app/services/postprocess/image_generation.py`
  - Status: `split`
  - Notes: highly useful domain parser; preserve logic, but extract only what current runtime needs.

- `backend_old/forgelab/common/shapely_2d_funcs.py`
  - Target: `backend/app/services/preprocessor/` and `backend/app/services/solver/`
  - Status: `split`
  - Notes: likely one of the most reusable geometry modules, but too broad for one direct destination.

- `backend_old/forgelab/common/time_between_operations.py`
  - Target: `backend/app/services/preprocessor/control_program_builder.py`
  - Status: `port`
  - Notes: runtime lookup logic survives; storage already aligns with current `time_between_operations` model.

## SQL Bootstrap / Schema Scripts
- `backend_old/forgelab/sql_setup/connections.py`
  - Target: none
  - Status: `drop`
  - Notes: replaced by `backend/app/database.py`, Alembic, and modern DB setup scripts.

- `backend_old/forgelab/sql_setup/create_admin_management_functions.py`
  - Target: none
  - Status: `drop`

- `backend_old/forgelab/sql_setup/create_functions_and_triggers.py`
  - Target: `backend/alembic/` only if a specific trigger is still required
  - Status: `defer`

- `backend_old/forgelab/sql_setup/create_functions_communicate_with_client.py`
  - Target: none
  - Status: `drop`
  - Notes: old client communication functions are superseded by FastAPI.

- `backend_old/forgelab/sql_setup/create_operations.py`
  - Target: `backend/data/database_seeding/`
  - Status: `split`

- `backend_old/forgelab/sql_setup/create_operations_table_functions.py`
  - Target: none
  - Status: `drop`

- `backend_old/forgelab/sql_setup/create_queue_functions.py`
  - Target: none
  - Status: `drop`
  - Notes: queue behavior should live in Python + DB tables, not DB functions.

- `backend_old/forgelab/sql_setup/create_run_stop_buttons_functions.py`
  - Target: none
  - Status: `drop`

- `backend_old/forgelab/sql_setup/create_tables.py`
  - Target: `backend/alembic/versions/`
  - Status: `drop`
  - Notes: use as legacy schema reference only.

- `backend_old/forgelab/sql_setup/create_tooltip_images.py`
  - Target: `backend/scripts/`
  - Status: `defer`

- `backend_old/forgelab/sql_setup/hash_password.py`
  - Target: none
  - Status: `drop`
  - Notes: current auth stack already provides password hashing.

- `backend_old/forgelab/sql_setup/import_json.py`
  - Target: `backend/db_setup/`, `backend/app/services/library_seed_service.py`
  - Status: `split`

- `backend_old/forgelab/sql_setup/insert_die_records_from_library.py`
  - Target: `backend/app/services/library_seed_service.py`, `backend/data/database_seeding/`
  - Status: `split`

- `backend_old/forgelab/sql_setup/insert_feed_direction_records.py`
  - Target: Alembic seed/bootstrap scripts only if legacy enums still matter
  - Status: `defer`

- `backend_old/forgelab/sql_setup/insert_material_records.py`
  - Target: `backend/app/services/library_seed_service.py`, `backend/data/database_seeding/materials.json`
  - Status: `split`

- `backend_old/forgelab/sql_setup/insert_or_update_table_from_library.py`
  - Target: `backend/scripts/`, `backend/app/services/library_seed_service.py`
  - Status: `defer`

- `backend_old/forgelab/sql_setup/insert_press_records_from_library.py`
  - Target: `backend/app/services/library_seed_service.py`, `backend/data/database_seeding/library.json`
  - Status: `split`

- `backend_old/forgelab/sql_setup/insert_time_records.py`
  - Target: `backend/app/services/library_seed_service.py`
  - Status: `port`

- `backend_old/forgelab/sql_setup/library_dictionary.py`
  - Target: `backend/data/database_seeding/` and conversion scripts only
  - Status: `defer`

- `backend_old/forgelab/sql_setup/query_operation.py`
  - Target: `backend/scripts/`
  - Status: `defer`

- `backend_old/forgelab/sql_setup/query_press.py`
  - Target: `backend/scripts/`
  - Status: `defer`

- `backend_old/forgelab/sql_setup/test_records_add.py`
  - Target: `backend/scripts/create_test_user.py`, test fixtures, or seed helpers
  - Status: `split`

## Legacy Utility Scripts
- `backend_old/utils/setup_sql.py`
  - Target: `backend/db_setup/`, `backend/deploy/windows/`
  - Status: `split`
  - Notes: use as bootstrap/deployment reference only, not runtime.

- `backend_old/utils/query_and_file_functions.py`
  - Target: `backend/app/services/files/storage.py`, `backend/app/orchestration/claims.py`
  - Status: `split`

- `backend_old/utils/add_operations.py`
  - Target: none
  - Status: `drop`
  - Notes: old operation YAML conversion workflow was removed; active Operation metadata is localized in backend services.

- `backend_old/utils/add_attributes_to_operations_json.py`
  - Target: none
  - Status: `drop`
  - Notes: old operation YAML conversion workflow was removed; active Operation metadata is localized in backend services.

- `backend_old/utils/add_die_records_from_library.py`
  - Target: `backend/scripts/` or seed conversion helpers
  - Status: `defer`

- `backend_old/utils/add_press_records_from_library.py`
  - Target: `backend/scripts/` or seed conversion helpers
  - Status: `defer`

- `backend_old/utils/refresh_time_between_operations.py`
  - Target: `backend/scripts/`
  - Status: `defer`

- `backend_old/utils/get_available_lybrary_type_id_numbers.py`
  - Target: `backend/scripts/`
  - Status: `defer`

- `backend_old/utils/test_psql.py`
  - Target: none
  - Status: `drop`

- `backend_old/utils/die_test.py`
  - Target: `backend/tests/` or `backend/scripts/`
  - Status: `defer`

- `backend_old/utils/convert.py`
  - Target: `backend/scripts/`
  - Status: `defer`

- `backend_old/utils/rot4.py`
  - Target: `backend/scripts/`
  - Status: `defer`

- `backend_old/utils/srv_pre/server.py`
  - Target: none
  - Status: `drop`
  - Notes: superseded by the new worker/coordinator architecture.

- `backend_old/utils/srv_post/server.py`
  - Target: none
  - Status: `drop`

- `backend_old/utils/install.bat`
  - Target: `backend/deploy/windows/`
  - Status: `defer`

- `backend_old/utils/install_initial.bat`
  - Target: `backend/deploy/windows/`
  - Status: `defer`

- `backend_old/utils/install_update.bat`
  - Target: `backend/deploy/windows/`
  - Status: `defer`

- `backend_old/utils/autostart.bat`
  - Target: `backend/deploy/windows/`
  - Status: `defer`

- `backend_old/utils/pb_dumpall.bat`
  - Target: `backend/deploy/windows/` if backup workflow is still needed
  - Status: `defer`

- `backend_old/utils/fluent-bit.conf`
  - Target: external ops/deploy config only
  - Status: `defer`

- `backend_old/utils/operations_old.json`
  - Target: one-time reference only
  - Status: `drop`

- `backend_old/utils/triggers.json`
  - Target: one-time reference only
  - Status: `defer`

## Data and Assets
- `backend_old/forgelab/data/materials/*`
  - Target: `backend/data/materials/`
  - Status: `port`
  - Notes: many files are already represented in the new backend data tree.

- `backend_old/forgelab/data/dies/*`
  - Target: `backend/data/dies/`
  - Status: `port`

- `backend_old/forgelab/data/operations/*`
  - Target: `backend/data/operations/`
  - Status: `port`

- `backend_old/forgelab/data/ppt/template.pptx`
  - Target: `backend/data/ppt/template.pptx`
  - Status: `port`

## Migration Priority Hint
Recommended order for actual code porting:
1. `common/file_operations.py`
2. `notifications_listener_service.py`
3. `srv_pre/pre_worker_class.py` split into worker shell + preprocessing services
4. `srv_solver/pre_functions.py` and `solver_functions.py`
5. `srv_solver/operations/*.py`
6. `common/read_deform_keyfile.py`
7. `srv_post/gen_ppt.py` and `srv_post/post_worker_class.py`
8. selected `sql_setup/*` conversion/seed helpers only after runtime path is stable
