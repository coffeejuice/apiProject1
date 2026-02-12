"""Document Heading block type handler"""
from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select
from uuid import UUID
from .base import BlockTypeHandler


class DocumentHeadingHandler(BlockTypeHandler):
    """
    Handler for Document Heading block.

    This system block displays document metadata in a table format,
    mimicking an industrial document report title page.
    Data is stored in the 'documents' and 'document_versions' tables.
    """

    @property
    def block_type_name(self) -> str:
        return "document_heading"

    @property
    def is_system_block(self) -> bool:
        return True

    @property
    def is_removable(self) -> bool:
        return False

    @property
    def fixed_position(self) -> int:
        return 0  # Always first block

    @property
    def allow_multiple_instances(self) -> bool:
        return False  # Only one instance per document

    def get_default_props(self) -> Dict[str, Any]:
        """Default props for document heading block - all fields are strings"""
        return {
            "heat_no": "",
            "finished_size": "",
            "stock_size": "",
            "stock_weight": "",
            "remarks": "",
            "preview_status": "empty",
        }

    def validate_props(self, props: Dict[str, Any]) -> bool:
        """Document heading props are read-only"""
        return True

    def serialize_for_frontend(self, db: Session, block_id: UUID, document_id: int, props: Dict[str, Any]) -> Dict[str, Any]:
        """
        Return block props merged with document metadata.
        Data is stored in block props, but we also include document table metadata.
        """
        from app.models.document.document import Document, DocumentVersion

        # Get document data for metadata only
        document = db.execute(
            select(Document).filter(Document.document_id == document_id)
        ).scalars().first()

        if not document:
            return props

        # Start with props data
        data = dict(props)

        # Add document metadata
        data["name"] = document.name
        data["project_id"] = document.project_id
        data["source_document_id"] = document.source_document_id
        data["editor_user_id"] = document.editor_user_id
        data["created_at"] = document.created_at.isoformat() if document.created_at else None
        data["updated_at"] = document.updated_at.isoformat() if document.updated_at else None

        # Get latest document version (if exists)
        version = db.execute(
            select(DocumentVersion)
            .filter(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.document_version_id.desc())
        ).scalars().first()

        # Add version data if exists
        if version:
            data["version"] = {
                "document_version_id": version.document_version_id,
                "name": version.name,
                "is_editable": version.is_editable,
                "execution_order": version.execution_order,
                "operations_count": version.operations_count,
                "created_at": version.created_at.isoformat() if version.created_at else None,
                "last_modified": version.last_modified.isoformat() if version.last_modified else None,
            }

        return data

    def on_update(self, db: Session, block_id: UUID, document_id: int, props: Dict[str, Any]) -> None:
        """
        Validate and update block props. Also update document name if provided.
        Data is now stored in block props only.
        """
        from app.models.document.document import Document, DocumentVersion

        # Validate field lengths before updating (all fields are strings)
        field_limits = {
            "name": 1024,
            "heat_no": 511,
            "finished_size": 511,
            "stock_size": 511,
            "stock_weight": 511,
            "remarks": 4095,
        }

        validation_errors = []
        for field, max_len in field_limits.items():
            if field in props and props[field] is not None:
                value = str(props[field])
                if len(value) > max_len:
                    validation_errors.append(
                        f"Field '{field}' is too long: {len(value)} characters (max {max_len})"
                    )

        if validation_errors:
            raise ValueError("Validation failed:\n" + "\n".join(validation_errors))

        # Update document name if provided
        if "name" in props:
            document = db.execute(
                select(Document).filter(Document.document_id == document_id)
            ).scalars().first()

            if document:
                document.name = props["name"]

        # Update version fields if provided
        if "version" in props and isinstance(props["version"], dict):
            version_data = props["version"]

            # Get latest version
            version = db.execute(
                select(DocumentVersion)
                .filter(DocumentVersion.document_id == document_id)
                .order_by(DocumentVersion.document_version_id.desc())
            ).scalars().first()

            if version:
                version_fields = ["name", "is_editable"]
                for field in version_fields:
                    if field in version_data:
                        setattr(version, field, version_data[field])

        db.flush()

    def get_editable_fields(self):
        """Return list of fields that can be edited"""
        return [
            "name", "heat_no", "finished_size",
            "stock_size", "stock_weight",
            "remarks",
            "preview_status"
        ]
