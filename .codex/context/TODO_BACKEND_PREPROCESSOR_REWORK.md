# TODO: Backend Preprocessor Rework Plan

## Purpose
This file is the active TODO context for finishing the new `document_blocks -> document_operations -> simulation_steps -> Pre` pipeline.

It intentionally replaces older stage plans. Earlier stages for data-model cleanup, YAML removal, `document_operations`, `simulation_steps` sibling rows, Operations-screen parse diagnostics, and semantic Pre adapter migration are considered completed baseline work unless source code proves otherwise.

## Completed Baseline
- Editable document source data lives in `document_blocks`.
- `document_operations` is regenerated from saved `document_blocks` and stores final user/process operation JSON in `operation_parameters`.
- `document_operations` no longer stores inherited/effective namespace columns.
- Deformation values are copied into generated Operation rows by direct-parent rules only.
- `simulation_steps.document_operation_id` is the primary key and required FK to `document_operations.document_operation_id`.
- Operation regeneration creates/removes sibling `simulation_steps` rows together with `document_operations`.
- Valid `document_operations` rows set sibling `simulation_steps.preprocess_ready = true`.
- Runtime YAML/schema files were removed; rules are localized in the endpoint/service code that executes them.
- Operations view shows `document_operations.operation_parameters` JSON and parse diagnostics.
- The Pre bridge reads `document_operations.operation_parameters` through `build_process_cards_for_document_version`.
- Semantic Pre definitions live in `backend/app/services/preprocessor/control_program_builder.py`.
- Pre compiler dispatch is semantic-template based, not old numeric operation-id based.
- `backend/scripts/check_preprocessor_pipeline.py --list-support` reports semantic adapter coverage.
- All current semantic operation templates have a real Pre adapter; no current template is intentionally left on generic fallback.
- API, Pre, Post, and Coordinator have local JSONL rotating-file logging and a frontend Logs view. Solver logging is intentionally excluded from this local log viewer for now.

## Current Main Risk
The remaining integration risk is not generic adapter coverage. The main risk is that Pre output is only partially represented in a user-friendly way for expert inspection, advanced multi-step visual analysis is not implemented yet, and some downstream migrated math may still assume old-project DB/table/column shapes, old parameter names, or old wide-table payloads.

The first work item remains the Simulations/Steps inspection UI plus correct 2D/3D geometry display. Backend runtime validation remains the next stage and continues to verify the real worker path against the current DB schema and JSON payloads.

## How To Reference This Plan
- Say `этап 1`, `этап 2`, etc. to work on a full stage.
- Say `задача 1.3` to reference a specific task.
- Say `следующий этап по TODO_BACKEND_PREPROCESSOR_REWORK` to continue from the next unfinished stage.
- If implementation changes make this file wrong, update this context file in the same task.
- When showing tasks to the user, use task ids as the only numbering, for example `1.10 Single-Step 3D Overlay Mode`.

## Decisions Already Made
- Do not restore the old `server_pre_main` wide-table schema as-is.
- Do not add a new all-in-one central rules file.
- Keep rule ownership localized in the backend/frontend code that executes the rule.
- Keep important stable workflow/query fields as typed columns.
- Keep operation-specific, variable, and evolving Pre payloads in JSONB unless a field becomes a stable query/index key.
- Keep large arbitrary binary/heavy artifacts out of the hot list-view path. Store only compact summaries or references in `simulation_steps` when payloads become large.
- Use local JSONL files plus read-only API endpoints for API/Pre/Post/Coordinator diagnostics. Do not store diagnostic logs in workflow tables.

## Deferred Or Rejected Items
- Do not add a duplicate Operations table elsewhere in the UI. Extend the existing Operations workspace instead.
- Do not add per-row Pre result placeholders inside the document by default. Result areas appear only when result display mode is explicitly enabled.
- Do not implement a full raw `simulation_steps` table mode as the user-facing Pre result view. It is an explicitly rejected UI option because it forces users to read a wide DB-shaped table and scroll both horizontally and vertically. Keep raw JSON/details available only as targeted expandable diagnostics for the selected step.
- Do not calculate and color a true 3D intersection volume for initial/final overlays unless the chosen 3D viewer provides it cheaply. Use transparent overlap instead.
- Do not implement physically exact rotation animation until `simulation_steps` carries enough orientation/basis metadata to avoid guessing.
- Do not add a new orchestration framework. Continue with lightweight worker processes plus PostgreSQL-backed queue/notification flow.
- Do not migrate Solver/Post until the Pre path is validated on real documents and `simulation_steps` payload shape is stable enough.
- Do not expose Solver raw log files through the central frontend Logs view until Solver-PC deployment/log transport is designed.

## Stage 1: Simulations/Steps Inspection UI And 3D Geometry Pipeline
Goal: make Pre-calculated `simulation_steps` readable for a human expert before Solver starts, while also recovering the old-project 3D surface-generation capability without bringing back old DB coupling.

Current implementation status:
- Done tasks are listed under `Done`.
- Open or partially open tasks remain under `Open / Remaining`.
- `backend/app/services/preprocessor/legacy_surface_mesh.py` restores the old-project Trimesh/STL mesh-state path for Pre-generated 3D surfaces.
- `backend/app/services/preprocessor/surface_mesh.py` is only a mesh payload/STL serialization container; it must not synthesize fallback geometry.
- `GET /documents/{document_id}/simulation-steps/{document_operation_id}/surface` reads only Pre-generated legacy mesh artifacts for the selected step.
- `SimulationStepsView` shows explicit legacy STL artifact errors when mesh loading fails; it must not fall back to local outline extrusion.
- Remaining optional work after the strict legacy 3D path is stable: multi-step selection/visualization, export controls, normalized orientation metadata, and persistent heavy-artifact references needed by Solver/Post.

### Done

### Stage 1.1 Compact Step List — Done
- The `Steps` main view has a very narrow left step/task list.
- The left step/task list has independent vertical scrolling and does not scroll the right 2D/3D/detail area.
- The left list is visible only when the `Steps` tool button is active.
- A second click on the active `Steps` tool button hides the left list while keeping the `Steps` main view open, matching the hide/show mechanics used by other tool panes.
- The list includes visual-only title cards for document structure:
  - Heating section titles with section numbers.
  - Deformation section titles with section numbers.
  - Furnace child titles with child numbers.
  - Operation child titles with child numbers.
- Step cards under those title cards show saved user-entered operation variables from `document_operations.operation_parameters`, not only compiled Pre output.
- Step card selection drives the large right-side 2D/3D/detail panels.
- The list remains compact and does not become a full raw `simulation_steps` table.

### Stage 1.2 2D Geometry View — Done
- The 2D view overlays initial/final cross-section outlines in one shared coordinate system.
- Geometry uses proportional X/Y scaling.
- Initial and final states use distinct visual styles.
- The view avoids width/height-ratio distortion.

### Stage 1.3 2D Numeric Overlays — Done
- The 2D view shows compact H/W/L/A values and available deformation/strain metrics.
- Initial/final values are displayed close to the geometry instead of requiring a wide raw table.

### Stage 1.4 Lightweight 3D Preview Fallback — Removed
- The earlier frontend/backend extrusion preview is intentionally removed from the active 3D path.
- 3D preview must use explicit legacy Pre-generated STL/Trimesh artifacts.
- If artifacts are missing, the UI shows the backend error instead of generating substitute geometry.

### Stage 1.5 Old 3D Surface Pipeline Audit — Done
- Old-project 3D surface-generation audit found the relevant chain.
- `backend_old/forgelab/srv_pre/geometry_class.py` builds Shapely cross-section polygons from old billet operation parameters.
- `backend_old/forgelab/common/shapely_2d_funcs.py::polygon_to_3d_trimesh_object` triangulates the polygon and extrudes it with `trimesh`.
- Old DB columns `initial_3d_stl` / `final_3d_stl` stored binary STL.
- The active project intentionally does not put heavy binary mesh payloads into the default step list.

### Stage 1.6 Legacy Surface Generator Migration — Done
- The old Shapely polygon -> Trimesh/STL generator and row-to-row carried mesh-state concept are migrated into `backend/app/services/preprocessor/legacy_surface_mesh.py`.
- Billet, heating/furnace carry, upsetting, prolongation/radial/full-die, and cutting rows now use explicit legacy mesh generation during Pre compilation.
- `backend/app/services/preprocessor/surface_mesh.py` is only the JSON/API payload container and STL serializer helper.
- Hidden fallback geometry generation from `simulation_steps.initial_geometry/final_geometry` JSON is forbidden.
- Binary STL artifacts are stored as selected-step run-cache files; old `initial_3d_stl` / `final_3d_stl` DB bytea columns are not restored.

### Stage 1.7 Artifact Storage And Loading — Done
- Heavy mesh artifacts are generated row-by-row by Pre, not lazily by a replacement algorithm.
- `GET /documents/{document_id}/simulation-steps/{document_operation_id}/surface` reads Pre-generated initial/final mesh JSON plus JSON/STL artifact files.
- If required artifacts are missing, unreadable, or were produced by a non-legacy source, the endpoint returns an explicit error.
- Artifact files are stored under the local run cache below `TEMP_FILES_ROOT/runs/<document_version_id>/<execution_order>/surface/document_operation_<id>/`.
- `simulation_steps.metrics.surface_artifacts` stores only compact references, file sizes, hashes, and mesh summaries, not full vertex/face payloads.
- Download endpoints expose cached artifact files:
  - `/documents/{document_id}/simulation-steps/{document_operation_id}/surface/artifacts/initial/json`
  - `/documents/{document_id}/simulation-steps/{document_operation_id}/surface/artifacts/initial/stl`
  - `/documents/{document_id}/simulation-steps/{document_operation_id}/surface/artifacts/final/json`
  - `/documents/{document_id}/simulation-steps/{document_operation_id}/surface/artifacts/final/stl`
- The default `simulation_steps` list remains compact and does not include heavy mesh payloads.

### Stage 1.8 Errors And Staleness — Done
- `simulation_steps` API responses include existing `document_operations` parse metadata:
  - `source_text_hash`
  - `parse_status`
  - `parse_errors`
  - `parse_warnings`
- The Steps right panel shows a compact diagnostics card with:
  - document operation id
  - operation order
  - operation order inside source block
  - operation template id
  - source block id
  - source sentence/table row when available
  - parse status
  - last update time
- The diagnostics card collects visible errors from:
  - `simulation_steps.metrics`
  - `simulation_step_status.last_error`
  - `simulation_step_status.error_payload`
  - parse errors/warnings
  - legacy surface artifact write/load errors
- The UI shows explicit `parse error`, `failed`, `pending`, `queued`, and `not ready` state text instead of requiring raw JSON inspection.
- Missing Pre output is shown as pending/not available, not silently treated as valid compiled geometry.

### Stage 1.9 Block/Operation Linking — Done
- The Steps view supports direct-parent source filtering when an active block is known from the document editor state:
  - active Operation/Furnace shows rows generated by that block
  - active Deformation/Heating shows rows generated by child Operation/Furnace blocks
- The left Steps list still contains visual-only Heating/Deformation/Furnace/Operation title cards.
- Hovering a title card highlights related step rows.
- Hovering a step row highlights its source title-card relationship.
- Selecting a step keeps the source relationship visible.
- The row-count badge shows filtered/total row counts when an active source block filter is applied.

### Stage 1.10 Single-Step 3D Overlay Mode — Done
- The selected step has a `Overlay / Side by side` 3D mode switch.
- Overlay mode renders initial and final legacy STL meshes in one shared-scale SVG viewport.
- Initial and final meshes use distinct colors and light transparent surface fills.
- Mesh edges are drawn from actual Pre-generated STL face topology.
- Candidate end-rim edges are emphasized from actual mesh vertices; no substitute geometry is generated.
- Side-by-side 3D cards remain available as a fallback viewing mode.
- If legacy STL artifacts are missing, the 3D viewport shows the backend artifact error instead of creating a hidden fallback mesh.

### Stage 1.11 3D Numeric And Engineering Annotations — Done With Metadata Limitation
- 3D overlay mode includes a compact corner table with initial/final:
  - surface area
  - volume
  - length
  - height
  - width
- Side-by-side 3D cards show compact area/volume/dimension values.
- A lightweight length guide is drawn when the projected mesh bounds leave enough room.
- Backend geometry payloads now explicitly expose `basis`, `top_marker`, and `orientation_metadata_status` fields.
- Current Pre output sets basis/top-marker fields to `null` with `orientation_metadata_status = "missing"` because normalized orientation data is not migrated yet.
- The frontend shows a visible missing-metadata warning and does not invent basis, top marker, or physically exact rotation data.
- Exact rotation animation remains deferred to Stage 1.16.

### Open / Remaining

### Stage 1.12 Multi-Step Selection Model
- Extend the compact step list to support selecting more than one step.
- Keep one active step for detail panels and keyboard/navigation focus.
- Allow multiple selected steps for comparative visualization.
- Recommended controls:
  - click row = active step
  - checkbox or modifier-click = selected step
  - shift-click = contiguous range selection
- Multi-selection must not replace the current single-step diagnostics; it only changes visualization modes.

### Stage 1.13 Multi-Step Visualization Modes
- When two or more steps are selected, show mode buttons whose availability depends on selection count and available payloads.
- Mode `Animation`:
  - available for two or more selected steps only after orientation/rotation metadata is available
  - shows one object at a time, not initial/final comparison
  - animates rotations between steps and then switches to the next final geometry
  - interprets signed angles by the right-hand rule around the object's local basis axes
  - support operation variables such as `n_angle` only through a backend-normalized rotation payload
- Mode `Initial first + final last`:
  - show the initial object of the first selected step and final object of the last selected step
  - use this to evaluate total shape change over a selected sequence
- Mode `All final forms`:
  - show final geometry for every selected step
  - available for both 2D and 3D views
  - use low-opacity surfaces/contours and a compact legend to avoid visual overload

### Stage 1.14 2D Multi-Step Refinements
- Keep current proportional cross-section overlay as the default for one selected step.
- For selected step(s), add optional thin reference rectangles/bounds around initial and final sections:
  - about 1 px line width
  - distinct styles/colors for initial vs final
  - no distortion of the actual contour
- Add compact metric tables for values that are initial/final pairs and values that are increments:
  - deformation increment
  - relative deformation
  - logarithmic deformation
  - other Pre metrics when present
- For `All final forms`, draw all final 2D contours with thin lines and a compact legend.

### Stage 1.15 Copy And Export Controls
- Add copy controls for 2D and 3D result panes:
  - copy selected-step data summary to clipboard
  - copy raw selected-step JSON diagnostics to clipboard
  - copy 2D image/SVG to clipboard when browser support allows
  - copy 3D image/SVG/canvas snapshot to clipboard when browser support allows
- If direct image clipboard is not supported by the browser, provide a visible error/help message instead of silently failing.

### Stage 1.16 Backend Payload Prerequisites For Advanced Visualization
- Normalize any orientation/rotation data needed by the UI into `simulation_steps` output.
- Candidate payload fields:
  - `initial_geometry.basis`
  - `final_geometry.basis`
  - `initial_geometry.top_marker`
  - `final_geometry.top_marker`
  - `metrics.rotation_sequence`
  - `step_specific_parameters.rotation_sequence`
- Preserve old-project variable names only inside backend adapters; frontend should consume normalized semantic payloads.
- Add diagnostics when animation mode is requested but required orientation data is missing.

### Stage 1.17 Exit Criteria
Stage 1 is done when:
- The Simulations/Steps screen has a compact step list plus large 2D/3D views.
- 2D overlays show initial/final sections proportionally and with readable compact metrics.
- Round source geometry renders as round/cylindrical in the 3D preview.
- Pre errors are visible without opening raw JSON.
- Raw JSON/details remain available only as targeted expandable diagnostics for the selected step, not as a full raw table mode.
- The old 3D surface generation path has been audited and mapped to new modules.
- Migrated generator consumes current JSON payloads and has no old DB dependency.
- At least round and arbitrary-outline geometry render as true 3D surfaces, not width/height-only placeholder prisms.
- Heavy artifacts do not slow down the default Steps list.
- A one-window 3D initial/final overlay mode exists or is explicitly rejected after practical UI testing.
- Multi-step selection exists with at least `Initial first + final last` and `All final forms` modes.
- Rotation animation is implemented only after normalized basis/rotation payloads are available.
- 2D/3D result panes expose copy-data controls and best-effort copy-image controls.

## Stage 2: Validate Real Pre Runtime And DB Compatibility
Goal: prove that the implemented JSON Pre path works through the real worker, current DB schema, current parameter names, and current `simulation_steps` sibling rows.

### Stage 2 Implementation Status
- Implemented in `backend/scripts/check_preprocessor_pipeline.py`.
- Main validation command from `backend/`:
  - `.venv/bin/python scripts/check_preprocessor_pipeline.py --validate-stage1 --worker-once`
- The command keeps the historical `--validate-stage1` name even though this TODO stage is now numbered Stage 2.
- The validator now performs:
  - real Pre source audit for obsolete table references
  - semantic adapter coverage audit
  - idempotent minimal fixture document creation/reset
  - `document_operations` regeneration
  - dry-run Pre compile
  - apply-mode `simulation_steps` rebuild
  - billet/document-initial-data geometry output verification
  - real `PreJobClaimer` + `PreJobExecutor` one-shot claim/execute cycle
  - controlled invalid-operation failure diagnostic check
  - valid fixture restoration after the controlled failure check
- Fixture document name:
  - `Codex Stage1 Pre Fixture`
- A Pre compile failure now stores diagnostics and sets `DocumentVersion.run_switch_status = false`.
  - This prevents invalid documents from being re-claimed endlessly by long-running Pre workers.
  - Retry must be explicit through the API/user action after fixing invalid input.

### Stage 2.1 Worker Startup
- Start a Pre worker from `backend/`:
  - `FORGELAB_WORKER_NAME=<name> python -m app.workers.pre_worker`
- Confirm the worker imports current backend modules, not `backend_old`.
- Confirm the worker uses current SQLAlchemy models and current DB connection settings.
- Confirm the worker can idle without crashing when there is no queued Pre task.

### Stage 2.2 Queue Claiming And Wake-Up
- Verify Pre task claiming through `DocumentVersion.run_switch_status = true`.
- Verify the claim path accepts `preprocess_status in queued/failed`.
- Verify the worker marks claimed/running state with worker name and timestamps.
- Verify PostgreSQL `LISTEN/NOTIFY` wake-up through `backend/app/orchestration/pg_notify.py`.
- Verify the worker also survives missed notifications by polling or timeout fallback.

### Stage 2.3 Old DB Shape Audit
- Audit the real Pre worker path for old-project table/column assumptions.
- Confirm the path does not query old `operations`, `server_pre_main`, `process_versions`, or old numeric operation-type tables.
- Confirm the path reads current `document_operations.operation_parameters`.
- Confirm `build_process_cards_for_document_version` is the only bridge from DB rows to `ProcessCard`.
- Confirm `simulation_steps` output is written through sibling rows keyed by `document_operation_id`.

### Stage 2.4 Parameter Name Compatibility Audit
- Audit semantic parameter names that bridge old math to new JSON.
- Confirm aliases/expected names exist for:
  - billet/document initial data
  - material id/name/version where needed
  - input stock geometry type and dimensions
  - input stock weight/volume
  - mesh element count
  - press id and press mode id
  - die assembly id, top die id, bottom die id
  - die dimensions injected by DB enrichment
  - `speed_upsetting`
  - `speed_prolongation`
  - feed direction id
  - `feed_first`, `feed_middle`, `feed_last`
  - operation-specific text/table parsed values
- If a mismatch is found, prefer adding a narrow adapter/alias at the Pre bridge boundary instead of changing frontend field names blindly.

### Stage 2.5 Billet-First Validation
- Start validation from the first operation row:
  - `operation_template_id = document_initial_data`
  - expected compiler operation type: `NewBillet`
- Confirm the row is generated from the root `document` block.
- Confirm its `operation_parameters` contains:
  - `document_info`
  - `process_data`
  - `material`
  - `input_stock`
  - `mesh`
- Confirm Pre calculates billet geometry and writes output into the matching `simulation_steps` sibling row.
- Confirm output contains enough information for the next operation:
  - initial geometry
  - final geometry
  - billet dimensions
  - volume
  - equivalent diameter
  - cross-section area
  - cross-section outline/section data
  - surface-area metrics where available
  - mesh metrics where available
- Confirm the geometry payload is sufficient for current migrated math even if full IGO3D file generation is not complete yet.

### Stage 2.6 Dry-Run And Apply Script Checks
- Use dry-run compile:
  - `backend/scripts/check_preprocessor_pipeline.py --document-id <id>`
- Use apply mode:
  - `backend/scripts/check_preprocessor_pipeline.py --document-id <id> --apply`
- Confirm dry-run does not mutate DB.
- Confirm apply mode writes compiled payload into existing sibling `simulation_steps`, not newly invented rows.
- Confirm `--list-support` still reports no `generic_fallback`.

### Stage 2.7 Fixture Document
- Create or repair a small valid fixture document if local documents contain intentionally invalid operations.
- The first fixture should be minimal:
  - Document initial data
  - one Deformation
  - one simple valid Operation
- The second fixture should include:
  - Document initial data
  - one Furnace table
  - one Deformation
  - several operation rows from one Operation block
- Fixture documents should be valid enough to prove Pre runtime plumbing before testing complex deformation edge cases.

### Stage 2.8 Success And Failure Diagnostics
- Confirm successful Pre rows update the matching `simulation_steps` row.
- Confirm failed Pre rows are traceable by:
  - `document_operation_id`
  - `operation_template_id`
  - `source_block_id`
  - operation order
- Confirm failure details are written to:
  - `simulation_steps.metrics.preprocessor_status`
  - `simulation_steps.metrics.preprocessor_error`
  - `simulation_step_status.status`
  - `simulation_step_status.last_error`
  - `simulation_step_status.error_payload`
- Confirm frontend can display enough error text to help the user identify the invalid block or source sentence/table row.

### Stage 2.9 Exit Criteria
Stage 2 is done when:
- A Pre worker starts and idles successfully.
- A queued document is claimed by the Pre worker.
- A valid document compiles through the worker path.
- `document_initial_data` writes billet geometry into sibling `simulation_steps`.
- At least one valid deformation operation writes compiled geometry/metrics into sibling `simulation_steps`.
- A controlled invalid operation writes readable diagnostics into sibling status/payload fields.
- No current semantic operation template reports generic fallback.

## Stage 3: Runtime Logging Foundation
Goal: make API, Pre, Post, and Coordinator runtime diagnostics readable from the frontend without Fluent Bit or DB log storage.

### Stage 3 Implementation Status
- Implemented local structured JSONL logging in `backend/app/logging_config.py`.
- Logging is configured for:
  - API startup in `backend/app/main.py`
  - Pre worker in `backend/app/workers/pre_worker.py`
  - Post worker in `backend/app/workers/post_worker.py`
  - Coordinator in `backend/app/orchestration/coordinator.py`
- Solver worker is intentionally excluded.
- Log files are written under `LOGS_FILES_ROOT` with per-service/per-worker paths:
  - `api/api.jsonl`
  - `pre/<worker-name>.jsonl`
  - `post/<worker-name>.jsonl`
  - `coordinator/<worker-name>.jsonl`
- Log files rotate by `LOG_FILE_MAX_BYTES` and `LOG_FILE_BACKUP_COUNT`.
- Read-only API endpoints live in `backend/app/routers/logs.py`:
  - `GET /logs/services`
  - `GET /logs/{service}/tail?worker_name=<name>&lines=300`
- Frontend Logs workspace is available from the left tool switcher and reads API/Pre/Post/Coordinator logs through those endpoints.

### Stage 3 Exit Criteria
Stage 3 is done when:
- API writes a local JSONL log file.
- Pre writes a local JSONL log file when started as a worker.
- Post writes a local JSONL log file when started as a worker.
- Coordinator writes a local JSONL log file when started.
- Frontend Logs view can list service log files and read the tail of each file.
- Solver remains excluded from this local frontend log viewer.

## Stage 4: Finalize `simulation_steps` Data Contract
Goal: keep `simulation_steps` useful for Pre/Solver/Post and for user inspection without recreating old brittle wide-table coupling.

### Stage 4.1 Typed Columns vs JSONB
- Keep typed columns for stable identity/workflow/query fields:
  - `document_operation_id`
  - `document_version_id`
  - `execution_order`
  - `source_block_id`
  - `operation_template_id`
  - `operation_kind`
  - `operation_label_snapshot`
  - `preprocess_ready`
  - `press_id`
  - `press_mode_id`
  - die/material ids
  - accumulated time/duration fields
- Keep flexible operation payloads in JSONB:
  - `parameter_values`
  - `control_parameters`
  - `step_specific_parameters`
  - `initial_geometry`
  - `final_geometry`
  - `metrics`
- Add a typed column only when the field becomes stable, frequently queried, or required for queue/index logic.

### Stage 4.2 Solver-Minimum Input Contract
- Confirm each compiled simulation step contains the data Solver needs without reading `document_blocks` directly:
  - number of feeds/bites/rotations where applicable
  - initial length and current billet geometry
  - active operation template/kind
  - selected press/press mode
  - selected die assembly or separate top/bottom/side dies
  - working speed and feed settings copied from the direct parent Deformation
  - timing fields and accumulated time
- Keep these values in compact JSON payloads unless a field becomes a queue/index key.
- Add validation diagnostics when Solver-required values are missing, but keep operation rows visible for troubleshooting.

### Stage 4.3 Geometry And Artifact Storage
- Keep compact geometry summaries in `simulation_steps` JSONB while payloads remain small enough for responsive table/list views.
- Compact geometry should include:
  - width
  - height
  - length
  - volume
  - equivalent diameter
  - cross-section area
  - cross-section outline
  - optional surface-area and mesh metrics
- Do not store large arbitrary IGO3D/2D/3D artifacts directly in the hot table if they become large or numerous.
- If heavy artifacts are needed, store files externally or create a dedicated artifact table keyed by `document_operation_id` / `simulation_step`.
- Store artifact references, summaries, and status in `simulation_steps`.
- PostgreSQL TOAST can store large JSONB/text automatically, but TOAST is not a product-level reason to overload the main runtime table.

### Stage 4.4 User-Facing Result Contract
- Standardize compact UI result fields so the frontend does not infer meaning from arbitrary JSON names:
  - `document_operation_id`
  - source block/operation label
  - status/severity
  - short summary
  - detailed diagnostics
  - geometry summary
  - optional artifact references
- Support result kinds:
  - numeric data
  - compact text notes
  - warnings/errors
  - 2D geometry/section previews
  - 3D preview geometry
  - heavy artifact references
- Add compact summary plus expandable details.
- Add lazy loading for heavy image/geometry/preview payloads.

### Stage 4.5 Exit Criteria
Stage 4 is done when:
- The project has a written rule for typed-column vs JSONB storage in `simulation_steps`.
- Solver-minimum input data is explicitly listed and can be checked per step.
- Geometry/artifact storage boundary is documented.
- The result payload contract is clear enough to implement UI without guessing.

## Stage 5: Show Pre/Post Results In Document UI
Goal: show calculated results inside the document without making the editor noisy or unstable.

Tasks:
- Add document-level result toggles near Save:
  - `Preprocessor`
  - `Postprocessor`
- If no result toggle is active, keep the document compact with no reserved result areas.
- If a result toggle is active, show result areas only for relevant active/selected operation context.
- For one Operation block that materializes multiple `document_operations` rows, choose visible result row by:
  - active operation row
  - selected operation row
  - last row fallback
- Avoid vertically rendering all operation results because image-heavy output will stretch the document too much.
- Use horizontal synchronized scrolling for multi-operation results if several result cards must be visible.
- Reserve placeholders only in explicit result modes to avoid layout jumps during background Pre/Post updates.

## Stage 6: Verification And Regression Tests
Goal: keep the new operation-materialization and Pre bridge stable while Solver/Post migration continues.

Tasks:
- Add regression tests for Operation text parsing.
- Add regression tests for Rounding table parsing.
- Add regression tests for Furnace table materialization.
- Add regression tests for `document_initial_data` materialization and Pre compilation.
- Add regression tests for direct-parent Deformation copy rules:
  - dies
  - feed
  - speed
  - parser variables
- Add a focused billet-first fixture that verifies `document_initial_data -> NewBillet -> simulation_steps` geometry output.
- Add fixtures for 2-3 typical documents covering:
  - Billet
  - Furnace
  - Upsetting
  - Cogging
  - Rounding
  - Radial
  - Transverse
  - Cutting
- Verify fixed document/version immutability:
  - after fixation, user edits cannot mutate the operation rows used for simulation

## Stage 7: Diagnostics And Migration Support
Goal: make future Solver/Post migration safer without adding heavy orchestration.

Tasks:
- Add a developer diagnostic endpoint or script output showing:
  - `document_blocks -> document_operations -> simulation_steps`
- Keep semantic adapter coverage visible with:
  - `check_preprocessor_pipeline.py --list-support`
- Fail loudly if a new semantic template would use generic fallback.
- Maintain a compact mapping doc or generated report:
  - semantic operation id -> Pre adapter -> legacy operation/math source
- Maintain a compact mapping doc or generated report:
  - new JSON parameter name -> old preprocessor/math variable name
- Before Solver migration, audit which solver adapters still expect old flat columns.
- Update Solver adapters to consume `simulation_steps.step_specific_parameters` JSON where appropriate.

## Explicit Deferred Task
- Do not implement exact animation rotation until normalized `basis` / `rotation_sequence` data exists in `simulation_steps`.
