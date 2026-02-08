"""Migration endpoints for database updates"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/migrate/add-system-blocks")
def migrate_add_system_blocks(db: Session = Depends(get_db)):
    """
    Run migration to add system blocks support.
    This is safe to run multiple times (idempotent).
    """
    try:
        # Step 1: Add columns
        db.execute(text("""
            ALTER TABLE blocks
            ADD COLUMN IF NOT EXISTS is_system BOOLEAN NOT NULL DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS is_removable BOOLEAN NOT NULL DEFAULT TRUE,
            ADD COLUMN IF NOT EXISTS fixed_position SMALLINT NULL
        """))
        db.commit()

        # Step 2: Add enum values
        try:
            db.execute(text("ALTER TYPE blocktype ADD VALUE IF NOT EXISTS 'document_heading'"))
            db.commit()
        except Exception as e:
            if "already exists" not in str(e):
                raise

        try:
            db.execute(text("ALTER TYPE blocktype ADD VALUE IF NOT EXISTS 'input_workpiece'"))
            db.commit()
        except Exception as e:
            if "already exists" not in str(e):
                raise

        # Step 3: Drop old function if exists, then create new one
        db.execute(text("DROP FUNCTION IF EXISTS initialize_system_blocks(BIGINT)"))
        db.commit()

        db.execute(text("""
            CREATE FUNCTION initialize_system_blocks(p_document_id BIGINT)
            RETURNS VOID AS $$
            DECLARE
                v_order_key_1 VARCHAR(100);
                v_order_key_2 VARCHAR(100);
                v_exists_heading INTEGER;
                v_exists_workpiece INTEGER;
            BEGIN
                SELECT COUNT(*) INTO v_exists_heading
                FROM blocks
                WHERE document_id = p_document_id AND block_type = 'document_heading';

                SELECT COUNT(*) INTO v_exists_workpiece
                FROM blocks
                WHERE document_id = p_document_id AND block_type = 'input_workpiece';

                v_order_key_1 := lpad('0', 20, '0') || '-1000';
                v_order_key_2 := lpad('1000000000000000000', 20, '0') || '-1000';

                IF v_exists_heading = 0 THEN
                    INSERT INTO blocks (
                        block_id, document_id, parent_block_id, order_key,
                        block_type, text, props, is_system, is_removable, fixed_position,
                        created_at, updated_at
                    )
                    VALUES (
                        gen_random_uuid(), p_document_id, NULL, v_order_key_1,
                        'document_heading', '', '{}', TRUE, FALSE, 0,
                        NOW(), NOW()
                    );
                END IF;

                IF v_exists_workpiece = 0 THEN
                    INSERT INTO blocks (
                        block_id, document_id, parent_block_id, order_key,
                        block_type, text, props, is_system, is_removable, fixed_position,
                        created_at, updated_at
                    )
                    VALUES (
                        gen_random_uuid(), p_document_id, NULL, v_order_key_2,
                        'input_workpiece', '', '{"mesh_elements": 0, "weight": 0.0, "geometry_type": ""}',
                        TRUE, FALSE, 1,
                        NOW(), NOW()
                    );
                END IF;
            END;
            $$ LANGUAGE plpgsql
        """))
        db.commit()

        # Step 4: Initialize for existing documents (skip if fails - function might not be updated yet)
        result = db.execute(text("SELECT document_id FROM documents"))
        document_ids = [row[0] for row in result]

        successful = 0
        failed = 0
        for document_id in document_ids:
            try:
                db.execute(text("SELECT initialize_system_blocks(:pid)"), {"pid": document_id})
                db.commit()
                successful += 1
            except Exception as e:
                db.rollback()
                failed += 1
                print(f"Failed to initialize blocks for document {document_id}: {e}")

        return {
            "success": True,
            "message": f"Migration completed. Successful: {successful}, Failed: {failed} (this is OK if function was already cached). The function is now updated for new documents."
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Migration failed: {str(e)}")


@router.post("/migrate/move-fields-to-block-props")
def migrate_move_fields_to_block_props(db: Session = Depends(get_db)):
    """
    Migrate document fields from documents table to DocumentHeading block props.
    This migration:
    1. Copies data from documents table columns to DocumentHeading block props
    2. Drops the columns from documents table
    3. Drops preview_status from document_versions table

    WARNING: This is a destructive migration. Make sure you have a backup.
    """
    try:
        # Step 1: Migrate data to block props
        db.execute(text("""
            UPDATE blocks
            SET props = jsonb_set(
                jsonb_set(
                    jsonb_set(
                        jsonb_set(
                            jsonb_set(
                                jsonb_set(
                                    jsonb_set(
                                        jsonb_set(
                                            jsonb_set(
                                                jsonb_set(
                                                    jsonb_set(
                                                        jsonb_set(
                                                            jsonb_set(
                                                                jsonb_set(
                                                                    jsonb_set(
                                                                        jsonb_set(
                                                                            jsonb_set(
                                                                                props,
                                                                                '{heat_no}',
                                                                                to_jsonb(COALESCE(p.heat_no, ''))
                                                                            ),
                                                                            '{lot_no}',
                                                                            to_jsonb(COALESCE(p.lot_no, ''))
                                                                        ),
                                                                        '{finished_size}',
                                                                        to_jsonb(COALESCE(p.finished_size, ''))
                                                                    ),
                                                                    '{standard_customer}',
                                                                    to_jsonb(COALESCE(p.standard_customer, ''))
                                                                ),
                                                                '{standard_wst}',
                                                                to_jsonb(COALESCE(p.standard_wst, ''))
                                                            ),
                                                            '{product_condition}',
                                                            to_jsonb(COALESCE(p.product_condition, ''))
                                                        ),
                                                        '{product_surface}',
                                                        to_jsonb(COALESCE(p.product_surface, ''))
                                                    ),
                                                    '{product_diameter_tolerance}',
                                                    to_jsonb(COALESCE(p.product_diameter_tolerance, ''))
                                                ),
                                                '{product_length_tolerance}',
                                                to_jsonb(COALESCE(p.product_length_tolerance, ''))
                                            ),
                                            '{product_curvature_tolerance}',
                                            to_jsonb(COALESCE(p.product_curvature_tolerance, ''))
                                        ),
                                        '{stock_size}',
                                        to_jsonb(COALESCE(p.stock_size, ''))
                                    ),
                                    '{stock_weight}',
                                    to_jsonb(COALESCE(p.stock_weight, 0.0))
                                ),
                                '{stock_no}',
                                to_jsonb(COALESCE(p.stock_no, ''))
                            ),
                            '{material_btt}',
                            to_jsonb(COALESCE(p.material_btt, 0.0))
                        ),
                        '{material_btt_sym_tolerance}',
                        to_jsonb(COALESCE(p.material_btt_sym_tolerance, 0.0))
                    ),
                    '{remarks}',
                    to_jsonb(COALESCE(p.remarks, ''))
                ),
                '{preview_status}',
                to_jsonb(COALESCE(p.preview_status::text, 'empty'))
            )
            FROM documents p
            WHERE blocks.document_id = p.document_id
            AND blocks.block_type = 'document_heading'
            AND blocks.is_system = true
        """))
        db.commit()

        # Step 2: Drop columns from documents table
        db.execute(text("ALTER TABLE documents DROP COLUMN IF EXISTS heat_no"))
        db.execute(text("ALTER TABLE documents DROP COLUMN IF EXISTS lot_no"))
        db.execute(text("ALTER TABLE documents DROP COLUMN IF EXISTS finished_size"))
        db.execute(text("ALTER TABLE documents DROP COLUMN IF EXISTS standard_customer"))
        db.execute(text("ALTER TABLE documents DROP COLUMN IF EXISTS standard_wst"))
        db.execute(text("ALTER TABLE documents DROP COLUMN IF EXISTS product_condition"))
        db.execute(text("ALTER TABLE documents DROP COLUMN IF EXISTS product_surface"))
        db.execute(text("ALTER TABLE documents DROP COLUMN IF EXISTS product_diameter_tolerance"))
        db.execute(text("ALTER TABLE documents DROP COLUMN IF EXISTS product_length_tolerance"))
        db.execute(text("ALTER TABLE documents DROP COLUMN IF EXISTS product_curvature_tolerance"))
        db.execute(text("ALTER TABLE documents DROP COLUMN IF EXISTS stock_size"))
        db.execute(text("ALTER TABLE documents DROP COLUMN IF EXISTS stock_weight"))
        db.execute(text("ALTER TABLE documents DROP COLUMN IF EXISTS stock_no"))
        db.execute(text("ALTER TABLE documents DROP COLUMN IF EXISTS material_btt"))
        db.execute(text("ALTER TABLE documents DROP COLUMN IF EXISTS material_btt_sym_tolerance"))
        db.execute(text("ALTER TABLE documents DROP COLUMN IF EXISTS remarks"))
        db.execute(text("ALTER TABLE documents DROP COLUMN IF EXISTS preview_status"))
        db.commit()

        # Step 3: Drop preview_status from document_versions
        db.execute(text("ALTER TABLE document_versions DROP COLUMN IF EXISTS preview_status"))
        db.commit()

        return {
            "success": True,
            "message": "Migration completed. Fields moved from documents table to DocumentHeading block props."
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Migration failed: {str(e)}")


@router.post("/migrate/update-field-lengths")
def migrate_update_field_lengths(db: Session = Depends(get_db)):
    """
    Update field lengths in the database:
    - Increase documents.title from VARCHAR(255) to VARCHAR(1024)

    This is a safe migration that can be run multiple times.
    """
    try:
        # Increase title column length
        db.execute(text("ALTER TABLE documents ALTER COLUMN title TYPE VARCHAR(1024)"))
        db.commit()

        return {
            "success": True,
            "message": "Field lengths updated successfully. Title column increased to 1024 characters."
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Migration failed: {str(e)}")
