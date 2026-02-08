-- Safe Migration: Add system block support without deleting existing blocks
-- This migration:
-- 1. Adds new block types to BlockType enum
-- 2. Adds system block metadata columns to blocks table
-- 3. Does NOT delete existing blocks

-- Step 1: Add new columns to blocks table
ALTER TABLE blocks
ADD COLUMN IF NOT EXISTS is_system BOOLEAN NOT NULL DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS is_removable BOOLEAN NOT NULL DEFAULT TRUE,
ADD COLUMN IF NOT EXISTS fixed_position SMALLINT NULL;

-- Step 2: Add new enum values to existing enum
-- Note: PostgreSQL allows adding enum values but not removing them easily
ALTER TYPE blocktype ADD VALUE IF NOT EXISTS 'document_heading';
ALTER TYPE blocktype ADD VALUE IF NOT EXISTS 'input_workpiece';

-- Step 3: Create function to initialize system blocks for a document
CREATE OR REPLACE FUNCTION initialize_system_blocks(p_document_id BIGINT)
RETURNS VOID AS $$
DECLARE
    v_order_key_1 VARCHAR(100);
    v_order_key_2 VARCHAR(100);
    v_exists_heading INTEGER;
    v_exists_workpiece INTEGER;
BEGIN
    -- Check if system blocks already exist
    SELECT COUNT(*) INTO v_exists_heading
    FROM blocks
    WHERE document_id = p_document_id AND block_type = 'document_heading';

    SELECT COUNT(*) INTO v_exists_workpiece
    FROM blocks
    WHERE document_id = p_document_id AND block_type = 'input_workpiece';

    -- Generate order keys for fixed positions
    v_order_key_1 := lpad('0', 20, '0') || '-1000';
    v_order_key_2 := lpad('1000000000000000000', 20, '0') || '-1000';

    -- Insert document_heading block if not exists (position 0)
    IF v_exists_heading = 0 THEN
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
    END IF;

    -- Insert input_workpiece block if not exists (position 1)
    IF v_exists_workpiece = 0 THEN
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
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Step 4: Initialize system blocks for existing documents (only if they don't exist)
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
COMMENT ON FUNCTION initialize_system_blocks IS 'Initialize required system blocks for a document (idempotent)';
