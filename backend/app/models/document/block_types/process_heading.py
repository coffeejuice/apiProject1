"""Process Heading block type handler"""
from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select
from uuid import UUID
from .base import BlockTypeHandler


class ProcessHeadingHandler(BlockTypeHandler):
    """
    Handler for Process Heading block.

    This system block displays process metadata in a table format,
    mimicking an industrial process report title page.
    Data is stored in the 'processes' and 'process_versions' tables.
    """

    @property
    def block_type_name(self) -> str:
        return "process_heading"

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
        """Default props for process heading block - all fields are strings"""
        return {
            "heat_no": "",
            "finished_size": "",
            "stock_size": "",
            "stock_weight": "",
            "remarks": "",
            "preview_status": "empty",
        }

    def validate_props(self, props: Dict[str, Any]) -> bool:
        """Process heading props are read-only"""
        return True

    def serialize_for_frontend(self, db: Session, block_id: UUID, process_id: int, props: Dict[str, Any]) -> Dict[str, Any]:
        """
        Return block props merged with process metadata.
        Data is stored in block props, but we also include process table metadata.
        """
        from app.models.document.process import Process, ProcessVersion

        # Get process data for metadata only
        process = db.execute(
            select(Process).filter(Process.process_id == process_id)
        ).scalars().first()

        if not process:
            return props

        # Start with props data
        data = dict(props)

        # Add process metadata
        data["title"] = process.title
        data["user_id"] = process.user_id
        data["material_id"] = process.material_id
        data["created_at"] = process.created_at.isoformat() if process.created_at else None
        data["last_edit_at"] = process.last_edit_at.isoformat() if process.last_edit_at else None
        data["current_rev_number"] = process.current_rev_number

        # Get latest process version (if exists)
        version = db.execute(
            select(ProcessVersion)
            .filter(ProcessVersion.process_id == process_id)
            .order_by(ProcessVersion.process_version_id.desc())
        ).scalars().first()

        # Add version data if exists
        if version:
            data["version"] = {
                "process_version_id": version.process_version_id,
                "name": version.name,
                "is_editable": version.is_editable,
                "execution_order": version.execution_order,
                "operations_count": version.operations_count,
                "created_at": version.created_at.isoformat() if version.created_at else None,
                "last_modified": version.last_modified.isoformat() if version.last_modified else None,
            }

        return data

    def on_update(self, db: Session, block_id: UUID, process_id: int, props: Dict[str, Any]) -> None:
        """
        Validate and update block props. Also update process title if provided.
        Data is now stored in block props only.
        """
        from app.models.document.process import Process, ProcessVersion

        # Validate field lengths before updating (all fields are strings)
        field_limits = {
            "title": 1024,
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

        # Update process title if provided (keep title in process table)
        if "title" in props:
            process = db.execute(
                select(Process).filter(Process.process_id == process_id)
            ).scalars().first()

            if process:
                process.title = props["title"]

        # Update version fields if provided
        if "version" in props and isinstance(props["version"], dict):
            version_data = props["version"]

            # Get latest version
            version = db.execute(
                select(ProcessVersion)
                .filter(ProcessVersion.process_id == process_id)
                .order_by(ProcessVersion.process_version_id.desc())
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
            "title", "heat_no", "finished_size",
            "stock_size", "stock_weight",
            "remarks",
            "preview_status"
        ]
