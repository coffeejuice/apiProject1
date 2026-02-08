-- Migration: Add system block support
-- This migration:
-- 1. Removes old block types from BlockType enum
-- 2. Adds new system block types (document_heading, input_workpiece)
-- 3. Adds system block metadata columns to blocks table

-- Step 1: Add new columns to blocks table
ALTER TABLE blocks
ADD COLUMN IF NOT EXISTS is_system BOOLEAN NOT NULL DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS is_removable BOOLEAN NOT NULL DEFAULT TRUE,
ADD COLUMN IF NOT EXISTS fixed_position SMALLINT NULL;

-- Step 2: Update BlockType enum
-- Note: PostgreSQL doesn't support removing enum values easily
-- We need to create a new enum and migrate

-- Create new enum type with only system blocks
CREATE TYPE blocktype_new AS ENUM (
    'document_heading',
    'input_workpiece'
);

-- Alter table to use new enum (this will fail if there are existing blocks with old types)
-- To safely migrate, first delete all existing blocks or update them to new types
-- For this migration, we'll delete old blocks since we're restructuring

-- Option 1: Delete all existing blocks (DESTRUCTIVE - use for development only)
DELETE FROM blocks;

-- Now we can safely change the column type
ALTER TABLE blocks
ALTER COLUMN block_type TYPE blocktype_new
USING block_type::text::blocktype_new;

-- Drop old enum
DROP TYPE IF EXISTS blocktype CASCADE;

-- Rename new enum to blocktype
ALTER TYPE blocktype_new RENAME TO blocktype;

-- Step 3: Create function to initialize system blocks for a document
CREATE OR REPLACE FUNCTION initialize_system_blocks(p_document_id BIGINT)
RETURNS VOID AS $$
DECLARE
    v_order_key_1 VARCHAR(100);
    v_order_key_2 VARCHAR(100);
BEGIN
    -- Generate order keys for fixed positions
    v_order_key_1 := lpad('0', 20, '0') || '-1000';
    v_order_key_2 := lpad(1000000000000000000::TEXT, 20, '0') || '-1000';

    -- Insert document_heading block (position 0)
    INSERT INTO blocks (
        block_id,
        document_id,
        parent_block_id,
        order_key,
        block_type,
        text,
        props,
        is_system,
        is_removable,
        fixed_position
    )
    VALUES (
        gen_random_uuid(),
        p_document_id,
        NULL,
        v_order_key_1,
        'document_heading',
        '',
        '{}',
        TRUE,
        FALSE,
        0
    );

    -- Insert input_workpiece block (position 1)
    INSERT INTO blocks (
        block_id,
        document_id,
        parent_block_id,
        order_key,
        block_type,
        text,
        props,
        is_system,
        is_removable,
        fixed_position
    )
    VALUES (
        gen_random_uuid(),
        p_document_id,
        NULL,
        v_order_key_2,
        'input_workpiece',
        '',
        '{"mesh_elements": 0, "weight": 0.0, "geometry_type": ""}',
        TRUE,
        FALSE,
        1
    );
END;
$$ LANGUAGE plpgsql;

-- Step 4: Initialize system blocks for existing documents
DO $$
DECLARE
    proc_record RECORD;
BEGIN
    FOR proc_record IN SELECT document_id FROM documents LOOP
        PERFORM initialize_system_blocks(proc_record.document_id);
    END LOOP;
END $$;

-- Step 5: Add comments
COMMENT ON COLUMN blocks.is_system IS 'Indicates if this is a system block';
COMMENT ON COLUMN blocks.is_removable IS 'Indicates if this block can be deleted by users';
COMMENT ON COLUMN blocks.fixed_position IS 'Fixed position in document (0-based), NULL if reorderable';
COMMENT ON FUNCTION initialize_system_blocks IS 'Initialize required system blocks for a document';
