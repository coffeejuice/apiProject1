---
apply: always
---

# Block Types

## Purpose
This file is the single source of truth for block types and their behavior. Update it whenever new block types are added.

## Architecture summary
- Backend defines the `BlockType` enum in `backend/app/models/document/block.py`. Each `Block` stores `text` plus JSON `props`, with ordering by `order_key`.
- System metadata (`is_system`, `is_removable`, `fixed_position`) lives on the `blocks` table.
- Block handlers live in `backend/app/models/document/block_types/` and implement `BlockTypeHandler`:
  - Default props, validation, and frontend serialization live in each handler.
  - The registry is in `backend/app/models/document/block_types/__init__.py`.
  - `backend/app/services/block_type_service.py` initializes system blocks, enforces constraints, and enriches block data for the frontend (including `editable_fields`).
- System blocks are auto-created on document creation in `backend/app/routers/document.py` via `initialize_system_blocks`.
- Frontend registers block components in `frontend/src/components/blocks/BlockRegistry.ts` and `frontend/src/components/blocks/index.ts`.
- The editor treats system blocks as non-user-editable in `frontend/src/lib/blockManager.ts` (excludes them from delete/reorder diffs).

## Existing block types

### System blocks (auto-created, fixed order, non-removable)

#### `document_heading`
- Backend handler: `backend/app/models/document/block_types/document_heading.py`
- Position: 0 (first), `is_system = true`, `is_removable = false`, `allow_multiple_instances = false`
- Stored props: `heat_no`, `finished_size`, `stock_size`, `stock_weight`, `remarks`, `preview_status`
- Enriched data on read: `title`, `user_id`, `material_id`, `created_at`, `last_edit_at`, `current_rev_number`, and `version` (name, is_editable, execution_order, operations_count, created_at, last_modified)
- Editable fields: `title`, `heat_no`, `finished_size`, `stock_size`, `stock_weight`, `remarks`, `preview_status`
- UI: title-page table with edit/save and optional version section.
- Design notes (from `BLOCK_SYSTEM_REFACTOR.md`): mentions additional fields (lot no, standards, product specs, stock info, material BTT/tolerance) that are not implemented in current code.

#### `input_workpiece`
- Backend handler: `backend/app/models/document/block_types/input_workpiece.py`
- Position: 1 (second), `is_system = true`, `is_removable = false`, `allow_multiple_instances = false`
- Stored props: `geometry_type_id`, `mesh_elements`, `weight`, `attributes`
- Validation: `geometry_type_id` required; `mesh_elements` integer; `weight` numeric; geometry type must exist when set.
- UI: geometry type dropdown + dynamic attribute inputs, weight, mesh elements; shows generated title.
- Geometry types (IDs 68-79) and attributes:
  - 68 round D: `diameter`
  - 69 round D + tail edge radius: `diameter`, `tail_radius`
  - 70 round D + tail chamfer 45 deg: `diameter`, `tail_chamfer`
  - 71 round L/D ratio: `length_to_diameter_ratio`
  - 72 square H: `side_of_square`
  - 73 square H + diagonal: `side_of_square`, `diagonal`
  - 74 square L/H ratio: `length_to_side_ratio`
  - 75 rectangle H x W: `height`, `width`
  - 76 rectangle H/W ratio + L/Thickness ratio: `height_to_width_ratio`, `length_to_thickness_ratio`
  - 77 rectangle H x W + diagonal: `height`, `width`, `diagonal`
  - 78 rectangle H x W + two diagonals: `height`, `width`, `diagonal_1`, `diagonal_2`
  - 79 octagon H: `height`
- Exact display labels live in `backend/app/models/document/block_types/input_workpiece.py` (`GEOMETRY_TYPES`).

### Legacy/editor blocks (text-centric)
These are still present for migration, import/export, and the editor mapping, but do not have handler classes.

- `paragraph`
- `heading1`
- `heading2`
- `list`
- `todo` (uses `props.checked`)
- `code` (uses `props.language`)
- `quote`
- `divider`

## Planned / design notes from `BLOCK_SYSTEM_REFACTOR.md`
- `material` (system block, not yet implemented):
  - Single instance per document; fixed order; auto-created; non-removable.
  - Two required dropdowns: material category and material (filtered by category).
  - Category list: Aluminum, Beta materials, Die materials, Steel, Stainless steel, Steel (extended), Superalloy, Titanium, Tool material (default Superalloy).
  - When implemented, update the `BlockType` enum, add a handler + registry entry, initialize in `block_type_service`, and register the frontend component + system block list.
- The refactor note mentions "two more block types", but only `material` is specified. Capture additional specs here once defined.
