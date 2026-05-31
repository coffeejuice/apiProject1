"""Document block type handler."""
from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select
from uuid import UUID
from .base import BlockTypeHandler
from .document_geometry import serialize_billet_geometry_props, validate_billet_geometry_props
from app.services.block_props import DOCUMENT_PROPERTIES, extract_namespace, normalize_document_block_props


class DocumentHandler(BlockTypeHandler):
    """
    Handler for the root Document block.

    This system block displays document metadata in a table format,
    mimicking an industrial document report title page.
    Data is stored in the 'documents' and 'document_versions' tables.
    """
    FIELD_LIMITS = {
        "name": 1024,
        "heat_no": 511,
        "finished_size": 511,
        "remarks": 4095,
    }

    @property
    def block_type_name(self) -> str:
        return "document"

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
        """Default props for the root document block."""
        return {
            DOCUMENT_PROPERTIES: {
                "heat_no": "",
                "finished_size": "",
                "remarks": "",
                "preview_status": "empty",
                "material_id": "",
                "geometry_type_id": "",
                "weight": 0.0,
                "attributes": {},
                "mesh_elements": 10,
                "section_numbering_start": 2,
            }
        }

    def validate_props(self, props: Dict[str, Any]) -> bool:
        """The semantic document block accepts flexible namespaced props."""
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

        normalized = normalize_document_block_props(props)
        document_properties = extract_namespace(normalized, DOCUMENT_PROPERTIES)
        document_properties.setdefault("section_numbering_start", 2)
        data = {
            DOCUMENT_PROPERTIES: document_properties,
            **document_properties,
        }
        data.update(serialize_billet_geometry_props(document_properties))

        # Add document metadata
        data["name"] = document.name
        data["project_id"] = document.project_id
        data["source_document_id"] = document.source_document_id
        data["editor_user_id"] = document.editor_user_id
        data["material_version_id"] = document.material_version_id
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

        normalized = normalize_document_block_props(props)
        document_properties = extract_namespace(normalized, DOCUMENT_PROPERTIES)
        props.clear()
        props.update(normalized)

        validation_errors = []
        for field, max_len in self.FIELD_LIMITS.items():
            if field in document_properties and document_properties[field] is not None:
                value = str(document_properties[field])
                if len(value) > max_len:
                    validation_errors.append(
                        f"Field '{field}' is too long: {len(value)} characters (max {max_len})"
                    )
        if not validate_billet_geometry_props(document_properties):
            validation_errors.append("Billet geometry props are invalid")
        mesh_elements = document_properties.get("mesh_elements")
        if mesh_elements not in (None, ""):
            try:
                if int(mesh_elements) <= 0:
                    validation_errors.append("mesh_elements must be positive")
            except (TypeError, ValueError):
                validation_errors.append("mesh_elements must be an integer")
        section_numbering_start = document_properties.get("section_numbering_start")
        if section_numbering_start in (None, ""):
            document_properties["section_numbering_start"] = 2
        else:
            try:
                section_numbering_start_int = int(section_numbering_start)
                if section_numbering_start_int <= 0:
                    validation_errors.append("section_numbering_start must be positive")
                else:
                    document_properties["section_numbering_start"] = section_numbering_start_int
            except (TypeError, ValueError):
                validation_errors.append("section_numbering_start must be an integer")

        if validation_errors:
            raise ValueError("Validation failed:\n" + "\n".join(validation_errors))

        # Update document name if provided
        if "name" in document_properties:
            document = db.execute(
                select(Document).filter(Document.document_id == document_id)
            ).scalars().first()

            if document:
                document.name = document_properties["name"]

        # Update version fields if provided
        if "version" in document_properties and isinstance(document_properties["version"], dict):
            version_data = document_properties["version"]

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
            "remarks",
            "preview_status",
            "material_id",
            "geometry_type_id",
            "weight",
            "attributes",
            "mesh_elements",
            "section_numbering_start",
        ]

    def get_field_limits(self) -> Dict[str, int]:
        return dict(self.FIELD_LIMITS)
