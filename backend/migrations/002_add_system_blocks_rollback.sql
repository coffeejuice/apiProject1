-- Rollback migration: Remove system block support
-- WARNING: This will delete all blocks and restore old block types

-- Step 1: Drop function
DROP FUNCTION IF EXISTS initialize_system_blocks(BIGINT);

-- Step 2: Delete all blocks (necessary for enum change)
DELETE FROM blocks;

-- Step 3: Recreate old enum type
CREATE TYPE blocktype_old AS ENUM (
    'paragraph',
    'heading1',
    'heading2',
    'list',
    'todo',
    'code',
    'quote',
    'divider'
);

-- Step 4: Change column back to old enum
ALTER TABLE blocks
ALTER COLUMN block_type TYPE blocktype_old
USING block_type::text::blocktype_old;

-- Step 5: Drop new enum
DROP TYPE IF EXISTS blocktype CASCADE;

-- Step 6: Rename old enum back
ALTER TYPE blocktype_old RENAME TO blocktype;

-- Step 7: Remove new columns
ALTER TABLE blocks
DROP COLUMN IF EXISTS is_system,
DROP COLUMN IF EXISTS is_removable,
DROP COLUMN IF EXISTS fixed_position;
