# Block System Refactoring - Implementation Summary

## Overview
Complete refactoring of the document/process system to support modular, extensible block types with special system blocks.

## Architecture Changes

### Backend Changes

#### 1. Block Model Updates (`backend/app/models/document/block.py`)
- **Removed old block types**: `paragraph`, `heading1`, `heading2`, `list`, `todo`, `code`, `quote`, `divider`
- **Added new block types**: `process_heading`, `input_workpiece`
- **New fields**:
  - `is_system`: Boolean flag for system blocks
  - `is_removable`: Boolean flag indicating if block can be deleted
  - `fixed_position`: Integer for fixed position in document (NULL if reorderable)

#### 2. Block Type Handler System
**New files created:**
- `backend/app/models/document/block_types/base.py` - Abstract base class for block handlers
- `backend/app/models/document/block_types/__init__.py` - Block type registry
- `backend/app/models/document/block_types/process_heading.py` - ProcessHeading handler
- `backend/app/models/document/block_types/input_workpiece.py` - InputWorkpiece handler

**Key Features:**
- Plugin-style architecture for adding new block types
- Each block type has its own handler class
- Handlers control:
  - Default props
  - Validation
  - Serialization for frontend
  - Lifecycle hooks (on_create, on_update, on_delete)
  - Editable fields
  - System block properties (removable, position, uniqueness)

#### 3. Block Type Service (`backend/app/services/block_type_service.py`)
**Functions:**
- `initialize_system_blocks()` - Auto-create system blocks for new documents
- `validate_block_constraints()` - Enforce single-instance and other constraints
- `can_delete_block()` - Check if block is removable
- `can_reorder_block()` - Check if block has fixed position
- `enrich_block_data_for_frontend()` - Serialize blocks with handler-specific data

#### 4. Updated Services
- **`routers/process.py`**: Auto-creates system blocks when creating new document
- **`routers/blocks.py`**: Returns enriched block data using handlers
- **`services/commit_service.py`**: Enforces block constraints and calls handler hooks

### Frontend Changes

#### 1. Block Component System
**New files created:**
- `frontend/src/components/blocks/BlockRegistry.ts` - Component registry
- `frontend/src/components/blocks/ProcessHeadingBlock.tsx` - ProcessHeading component
- `frontend/src/components/blocks/InputWorkpieceBlock.tsx` - InputWorkpiece component
- `frontend/src/components/blocks/index.ts` - Registration and exports

**Key Features:**
- Registry maps block types to React components
- Each block type has its own component
- Props interface: `BlockComponentProps { block, onUpdate, isReadOnly }`

#### 2. New Block Editor (`frontend/src/components/BlockEditor.tsx`)
- **Replaced TipTap** rich text editor with custom block rendering
- Loads blocks from `/documents/{id}/blocks/root` endpoint
- Renders blocks using registered components
- Handles block updates via commit API
- Shows unknown block types gracefully

#### 3. Updated Application
- **`pages/AppPage.tsx`**: Now uses `BlockEditor` instead of `Editor`
- Imports block component registry on mount

### Database Migration

#### Migration File: `backend/migrations/002_add_system_blocks.sql`
**Actions:**
1. Adds new columns: `is_system`, `is_removable`, `fixed_position`
2. Updates `BlockType` enum (removes old types, adds new ones)
3. Creates `initialize_system_blocks()` PostgreSQL function
4. Initializes system blocks for existing processes
5. **WARNING**: Deletes all existing blocks (development only)

#### Rollback File: `backend/migrations/002_add_system_blocks_rollback.sql`
- Restores old block types
- Removes system block columns
- **WARNING**: Also deletes all blocks

## System Block Definitions

### 1. ProcessHeading Block
**Properties:**
- Block type: `process_heading`
- Position: 0 (always first)
- Removable: No
- Multiple instances: No
- Data source: `processes` and `process_versions` tables

**Fields displayed:**
- Title (editable, also updates process.title)
- Heat No, Lot No, Finished Size
- Standards (Customer, WST)
- Product specifications (Condition, Surface, Tolerances)
- Stock information (Size, Weight, No)
- Material BTT and tolerance
- Remarks
- Created/Last edited timestamps
- Version information (if exists)

**Visual appearance:**
- Table format mimicking industrial process report title page
- Large title at top
- Edit/Save buttons
- Field labels and values in two-column layout

### 2. InputWorkpiece Block
**Properties:**
- Block type: `input_workpiece`
- Position: 1 (always second)
- Removable: No
- Multiple instances: No
- Data source: Block props (JSON)

**Fields:**
- `mesh_elements`: Elements across width [pcs] (integer)
- `weight`: Weight [kg] (float)
- `geometry_type`: Geometry type (string, dropdown)

**Visual appearance:**
- Table format with field labels and values
- Edit/Save buttons
- Geometry type dropdown: Cylindrical, Rectangular, Square, Hexagonal, Custom

## How to Add New Block Types

### Backend:
1. Add new block type to `BlockType` enum in `block.py`
2. Create handler in `backend/app/models/document/block_types/my_block.py`:
   ```python
   from .base import BlockTypeHandler

   class MyBlockHandler(BlockTypeHandler):
       @property
       def block_type_name(self) -> str:
           return "my_block"

       # Implement required methods...
   ```
3. Register in `block_types/__init__.py`:
   ```python
   from .my_block import MyBlockHandler
   register_block_type(MyBlockHandler())
   ```

### Frontend:
1. Create component in `frontend/src/components/blocks/MyBlock.tsx`:
   ```tsx
   export default function MyBlock({ block, onUpdate, isReadOnly }: BlockComponentProps) {
       // Render block...
   }
   ```
2. Register in `frontend/src/components/blocks/index.ts`:
   ```ts
   import MyBlock from './MyBlock'
   registerBlockType('my_block', MyBlock)
   ```

## Testing

### To Test the New System:
1. **Run migration**: Execute `002_add_system_blocks.sql`
2. **Start backend**: System will auto-create blocks on new document creation
3. **Start frontend**: BlockEditor will render system blocks
4. **Create new document**: Should automatically have ProcessHeading and InputWorkpiece blocks
5. **Edit blocks**: Click Edit button, modify fields, Save
6. **Verify persistence**: Reload page, changes should persist

### Test Constraints:
- Try to delete ProcessHeading block → Should be blocked
- Try to create duplicate InputWorkpiece block → Should be blocked
- Try to reorder system blocks → Should be blocked

## Benefits of New Architecture

1. **Modularity**: Each block type is self-contained
2. **Extensibility**: Easy to add new block types
3. **Type Safety**: Validation and constraints enforced at handler level
4. **Data Separation**: System blocks can store data in proper DB tables
5. **Flexibility**: Blocks can have unique behaviors, validation, and UI
6. **Maintainability**: Clear separation of concerns

## Migration Notes

### Breaking Changes:
- **All existing blocks will be deleted** during migration
- Old block types (paragraph, heading, etc.) no longer supported
- TipTap editor completely replaced
- API response format changed for `/blocks/root` endpoint

### Compatibility:
- Documents created with old system must be migrated manually
- localStorage content from TipTap editor will be ignored
- Old `blockManager.ts` and `blockConverter.ts` are obsolete

## File Changes Summary

### New Files:
- Backend: 5 files in `block_types/` directory, 1 service file
- Frontend: 5 files in `blocks/` directory, 1 editor file
- Migrations: 2 SQL files

### Modified Files:
- Backend: `models/document/block.py`, `routers/process.py`, `routers/blocks.py`, `services/commit_service.py`
- Frontend: `pages/AppPage.tsx`

### Obsolete Files (can be removed):
- Frontend: `components/Editor.tsx`, `lib/blockManager.ts`, `lib/blockConverter.ts`
- Frontend: `stores/useEditorStore.ts` (if no longer used)

## Future Enhancements

1. **Block Templates**: Predefined configurations for common block types
2. **Drag-and-Drop**: Visual reordering of non-system blocks
3. **Block Nesting**: Support for parent-child block relationships
4. **Versioning**: Track changes to individual blocks
5. **Permissions**: Per-block access control
6. **Export**: Generate reports from system blocks
7. **Validation**: Real-time field validation in frontend
8. **History**: Undo/redo for block changes
