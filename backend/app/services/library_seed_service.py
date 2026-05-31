import json
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable, Optional

from sqlalchemy import Integer, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from sqlalchemy.sql.schema import Table

import app.models  # noqa: F401 - ensure all models are registered on Base.metadata
from app.database import Base
from app.models.user import User


class LibrarySeedError(Exception):
    pass


@dataclass
class SeedReport:
    file_hash: str
    tables_processed: dict[str, int]
    only_missing: bool
    triggered_by_user_id: Optional[int]


class LibrarySeedService:
    TABLE_ALIASES = {
        "die_type_id": "die_types",
    }
    SEED_ORDER = [
        "users",
        "materials",
        "material_standards_catalog",
        "materials_designations",
        "materials_designations_standard_chemistry",
        "publications_catalog",
        "materials_test_records",
        "materials_chemistry_tests_results",
        "materials_property_tables",
        "materials_property_table_to_columns_connectivity",
        "materials_property_column_values",
        "material_classification_axes",
        "material_classification_values",
        "material_classification_assignments",
        "die_types",
        "dies",
        "die_assemblies",
        "presses",
        "press_modes",
        "press_die_map",
    ]
    MANDATORY_SEED_TABLES = [
        "users",
        "materials",
        "die_types",
        "dies",
        "die_assemblies",
        "presses",
        "press_modes",
        "press_die_map",
    ]

    def __init__(self, seed_root: Optional[Path] = None) -> None:
        backend_root = Path(__file__).resolve().parents[2]
        self.seed_root = seed_root or backend_root / "data" / "database_seeding"
        self.library_json_path = self.seed_root / "library.json"
        self.materials_json_path = self.seed_root / "materials.json"

    def get_status(self, db: Session) -> dict[str, Any]:
        seed_files = self._seed_files()
        file_exists = all(path.exists() for path in seed_files)
        file_hash = self._combined_file_hash(seed_files) if file_exists else None

        counts: dict[str, int] = {}
        for table_name in self.SEED_ORDER:
            counts[table_name] = self._count_rows(db, table_name)

        expected_tables = self._expected_seed_tables(db) if file_exists else list(self.MANDATORY_SEED_TABLES)
        needs_seed = any(counts[name] == 0 for name in expected_tables)
        can_seed_without_auth = counts.get("users", 0) == 0
        last_run = self._get_last_run(db)

        return {
            "file_exists": file_exists,
            "file_path": str(self.seed_root),
            "file_paths": [str(path) for path in seed_files],
            "file_hash": file_hash,
            "counts": counts,
            "needs_seed": needs_seed,
            "is_seeded": not needs_seed,
            "can_seed_without_auth": can_seed_without_auth,
            "last_run": last_run,
        }

    def _expected_seed_tables(self, db: Session) -> list[str]:
        expected = set(self.MANDATORY_SEED_TABLES)
        try:
            payload = self._load_payload()
            self._normalize_payload(db, payload)
        except Exception:
            return [table_name for table_name in self.SEED_ORDER if table_name in expected]

        for table_name in self.SEED_ORDER:
            if payload.get(table_name):
                expected.add(table_name)

        return [table_name for table_name in self.SEED_ORDER if table_name in expected]

    def seed_library(
        self,
        db: Session,
        only_missing: bool = False,
        triggered_by_user_id: Optional[int] = None,
    ) -> dict[str, Any]:
        missing_files = [path for path in self._seed_files() if not path.exists()]
        if missing_files:
            missing_paths = ", ".join(str(path) for path in missing_files)
            raise LibrarySeedError(f"Seed file(s) not found: {missing_paths}")

        self._ensure_seed_runs_table(db)
        db.commit()

        file_hash = self._combined_file_hash(self._seed_files())
        run_id = self._insert_seed_run(
            db,
            seed_name="library",
            file_hash=file_hash,
            status="running",
            details={
                "only_missing": only_missing,
                "triggered_by_user_id": triggered_by_user_id,
            },
        )
        db.commit()

        try:
            payload = self._load_payload()
            self._normalize_payload(db, payload)
            self._validate_payload(db, payload)
            report = self._upsert_payload(db, payload, only_missing, triggered_by_user_id)
            db.commit()
        except Exception as exc:
            db.rollback()
            error_message = self._format_seed_exception(exc)
            self._update_seed_run(
                db,
                run_id,
                status="failed",
                details={"error": error_message},
            )
            db.commit()
            raise LibrarySeedError(error_message) from exc

        self._update_seed_run(
            db,
            run_id,
            status="success",
            details={
                "tables_processed": report.tables_processed,
                "only_missing": report.only_missing,
                "triggered_by_user_id": report.triggered_by_user_id,
                "file_hash": report.file_hash,
            },
        )
        db.commit()

        return {
            "ok": True,
            "run_id": run_id,
            "file_hash": report.file_hash,
            "tables_processed": report.tables_processed,
            "only_missing": only_missing,
        }

    def _load_payload(self) -> dict[str, list[dict[str, Any]]]:
        payload: dict[str, list[dict[str, Any]]] = {}
        for path in self._seed_files():
            raw = self._load_seed_file(path)
            for raw_key, value in raw.items():
                table_name = self.TABLE_ALIASES.get(raw_key, raw_key)
                if table_name not in self.SEED_ORDER:
                    continue
                if not isinstance(value, list):
                    raise LibrarySeedError(f"Invalid section '{raw_key}' in {path.name}: expected list")
                if table_name in payload:
                    raise LibrarySeedError(
                        f"Duplicate seed section '{raw_key}' detected while loading {path.name}"
                    )
                payload[table_name] = [dict(item) for item in value if isinstance(item, dict)]

        for table_name in self.SEED_ORDER:
            payload.setdefault(table_name, [])

        return payload

    def _seed_files(self) -> list[Path]:
        return [self.library_json_path, self.materials_json_path]

    def _load_seed_file(self, path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)
        if not isinstance(raw, dict):
            raise LibrarySeedError(f"Invalid {path.name} format: expected object at root")
        return raw

    def _normalize_payload(self, db: Session, payload: dict[str, list[dict[str, Any]]]) -> None:
        users = payload.get("users", [])
        for row in users:
            if "id" in row and "user_id" not in row:
                row["user_id"] = row.pop("id")
            if "created_at" not in row or row["created_at"] in ("", None):
                row["created_at"] = datetime.utcnow()
            else:
                row["created_at"] = self._parse_dt(row["created_at"])
            if "password_hashed" in row and isinstance(row["password_hashed"], str):
                row["password_hashed"] = row["password_hashed"].encode("utf-8")
            if "user_priority_enum" in row and isinstance(row["user_priority_enum"], str):
                row["user_priority_enum"] = row["user_priority_enum"].strip().lower()

        seed_login_to_id: dict[str, int] = {}
        for row in users:
            login = row.get("login")
            user_id = row.get("user_id")
            if isinstance(login, str) and isinstance(user_id, int):
                seed_login_to_id[login] = user_id

        existing_login_to_id = {
            login: user_id
            for user_id, login in db.execute(select(User.user_id, User.login)).all()
        }

        for row in payload.get("materials", []):
            if "file_name" in row and "deform_file_name" not in row:
                row["deform_file_name"] = row.pop("file_name")
            deform_file_name = row.get("deform_file_name")
            if isinstance(deform_file_name, str):
                normalized_file_name = deform_file_name.strip()
                row["deform_file_name"] = normalized_file_name or None

        self._derive_material_classification_payload(db, payload)

        owner_sections = {
            "materials": "owner_id",
            "material_classification_axes": "created_by_user_id",
            "material_classification_values": "created_by_user_id",
            "material_classification_assignments": "created_by_user_id",
            "dies": "owner_user_id",
            "die_assemblies": "owner_user_id",
            "presses": "owner_user_id",
            "press_modes": "owner_user_id",
            "press_die_map": "owner_user_id",
        }
        for section, owner_field in owner_sections.items():
            for row in payload.get(section, []):
                if owner_field not in row:
                    continue
                row[owner_field] = self._resolve_owner_user_id(
                    row[owner_field],
                    seed_login_to_id,
                    existing_login_to_id,
                )

        for table_name in ("presses", "press_modes"):
            table = self._table_or_raise(table_name)
            columns = {c.name for c in table.columns}
            for row in payload.get(table_name, []):
                if table_name == "presses" and "id" in row and "id" not in columns and "press_id" in columns:
                    row["press_id"] = row.pop("id")
                if table_name == "press_modes" and "id" in row and "id" not in columns and "press_mode_id" in columns:
                    row["press_mode_id"] = row.pop("id")
                if "is_default_press_mode" in row and "is_default_press_mode" not in columns and "default_press_mode" in columns:
                    row["default_press_mode"] = row.pop("is_default_press_mode")
                if "default_press_mode" in row and "default_press_mode" not in columns and "is_default_press_mode" in columns:
                    row["is_default_press_mode"] = row.pop("default_press_mode")

    def _derive_material_classification_payload(self, db: Session, payload: dict[str, list[dict[str, Any]]]) -> None:
        materials = payload.get("materials", [])
        axis_rows = payload.setdefault("material_classification_axes", [])
        value_rows = payload.setdefault("material_classification_values", [])
        assignment_rows = payload.setdefault("material_classification_assignments", [])

        axis_table = self._table_or_raise("material_classification_axes")
        value_table = self._table_or_raise("material_classification_values")

        existing_axis_id_by_key: dict[str, int] = {}
        if self._table_exists(db, "material_classification_axes"):
            for row in db.execute(
                select(axis_table.c.axis_id, axis_table.c.key)
            ).mappings().all():
                axis_id = row.get("axis_id")
                axis_key = row.get("key")
                if isinstance(axis_id, int) and isinstance(axis_key, str) and axis_key.strip():
                    existing_axis_id_by_key[axis_key.strip()] = axis_id

        existing_value_id_by_ref: dict[tuple[int, str], int] = {}
        if self._table_exists(db, "material_classification_values"):
            for row in db.execute(
                select(value_table.c.value_id, value_table.c.axis_id, value_table.c.key)
            ).mappings().all():
                value_id = row.get("value_id")
                axis_id = row.get("axis_id")
                value_key = row.get("key")
                if (
                    isinstance(value_id, int)
                    and isinstance(axis_id, int)
                    and isinstance(value_key, str)
                    and value_key.strip()
                ):
                    existing_value_id_by_ref[(axis_id, value_key.strip())] = value_id

        next_axis_id = max(self._available_ids(db, "material_classification_axes", "axis_id", axis_rows), default=0) + 1
        next_value_id = max(self._available_ids(db, "material_classification_values", "value_id", value_rows), default=0) + 1

        axis_rows_by_key: dict[str, dict[str, Any]] = {}
        next_axis_sort_order = 0
        for index, row in enumerate(axis_rows):
            axis_key = self._normalize_classification_text(row.get("key"), f"material_classification_axes[{index}].key")
            axis_id = row.get("axis_id")
            if not isinstance(axis_id, int):
                axis_id = existing_axis_id_by_key.get(axis_key)
                if axis_id is None:
                    axis_id = next_axis_id
                    next_axis_id += 1
                row["axis_id"] = axis_id
            row["key"] = axis_key
            row.setdefault("name", self._build_localized_label(self._humanize_classification_key(axis_key)))
            row.setdefault("selection_mode", "multi")
            row["hierarchy_level"] = self._normalize_classification_hierarchy_level(
                row.get("hierarchy_level"),
                f"material_classification_axes[{index}].hierarchy_level",
                axis_key,
            )
            row.setdefault("sort_order", next_axis_sort_order)
            row.setdefault("is_filter_visible", True)
            row.setdefault("is_obsolete", False)
            axis_rows_by_key[axis_key] = row
            next_axis_sort_order = max(next_axis_sort_order, int(row.get("sort_order", 0)) + 1)

        value_rows_by_ref: dict[tuple[int, str], dict[str, Any]] = {}
        next_value_sort_order_by_axis: dict[int, int] = {}
        for index, row in enumerate(value_rows):
            value_key = self._normalize_classification_text(row.get("key"), f"material_classification_values[{index}].key")
            axis_id = row.get("axis_id")
            if not isinstance(axis_id, int):
                raise LibrarySeedError(
                    f"material_classification_values[{index}]: axis_id must be an integer"
                )
            value_id = row.get("value_id")
            if not isinstance(value_id, int):
                value_id = existing_value_id_by_ref.get((axis_id, value_key))
                if value_id is None:
                    value_id = next_value_id
                    next_value_id += 1
                row["value_id"] = value_id
            row["axis_id"] = axis_id
            row["key"] = value_key
            row.setdefault("name", self._build_localized_label(value_key))
            row.setdefault("sort_order", next_value_sort_order_by_axis.get(axis_id, 0))
            row.setdefault("is_obsolete", False)
            value_rows_by_ref[(axis_id, value_key)] = row
            next_value_sort_order_by_axis[axis_id] = max(
                next_value_sort_order_by_axis.get(axis_id, 0),
                int(row.get("sort_order", 0)) + 1,
            )

        assignment_keys = {
            (row.get("material_id"), row.get("value_id"))
            for row in assignment_rows
            if isinstance(row.get("material_id"), int) and isinstance(row.get("value_id"), int)
        }

        for material_index, row in enumerate(materials):
            classification = row.get("classification")
            if classification in (None, {}):
                continue
            if not isinstance(classification, dict):
                raise LibrarySeedError(
                    f"materials[{material_index}]: classification must be an object"
                )

            material_id = row.get("material_id")
            if not isinstance(material_id, int):
                raise LibrarySeedError(
                    f"materials[{material_index}]: material_id is required for classification seeding"
                )

            for axis_key_raw, raw_values in classification.items():
                axis_key = self._normalize_classification_text(
                    axis_key_raw,
                    f"materials[{material_index}].classification axis",
                )
                axis_row = axis_rows_by_key.get(axis_key)
                if axis_row is None:
                    axis_id = existing_axis_id_by_key.get(axis_key)
                    if axis_id is None:
                        axis_id = next_axis_id
                        next_axis_id += 1
                    axis_row = {
                        "axis_id": axis_id,
                        "key": axis_key,
                        "name": self._build_localized_label(self._humanize_classification_key(axis_key)),
                        "selection_mode": "multi",
                        "hierarchy_level": self._default_classification_hierarchy_level(axis_key),
                        "sort_order": next_axis_sort_order,
                        "is_filter_visible": True,
                        "is_obsolete": False,
                    }
                    next_axis_sort_order += 1
                    axis_rows.append(axis_row)
                    axis_rows_by_key[axis_key] = axis_row

                axis_id = axis_row["axis_id"]
                values = self._normalize_classification_values(
                    raw_values,
                    f"materials[{material_index}].classification.{axis_key}",
                )

                for value_key in values:
                    ref = (axis_id, value_key)
                    value_row = value_rows_by_ref.get(ref)
                    if value_row is None:
                        value_id = existing_value_id_by_ref.get(ref)
                        if value_id is None:
                            value_id = next_value_id
                            next_value_id += 1
                        value_row = {
                            "value_id": value_id,
                            "axis_id": axis_id,
                            "key": value_key,
                            "name": self._build_localized_label(value_key),
                            "sort_order": next_value_sort_order_by_axis.get(axis_id, 0),
                            "is_obsolete": False,
                        }
                        next_value_sort_order_by_axis[axis_id] = next_value_sort_order_by_axis.get(axis_id, 0) + 1
                        value_rows.append(value_row)
                        value_rows_by_ref[ref] = value_row

                    assignment_key = (material_id, value_row["value_id"])
                    if assignment_key in assignment_keys:
                        continue
                    assignment_rows.append(
                        {
                            "material_id": material_id,
                            "value_id": value_row["value_id"],
                            "created_by_user_id": row.get("owner_id"),
                        }
                    )
                    assignment_keys.add(assignment_key)

    def _normalize_classification_values(self, raw_values: Any, context: str) -> list[str]:
        if isinstance(raw_values, str):
            values = [raw_values]
        elif isinstance(raw_values, list):
            values = raw_values
        else:
            raise LibrarySeedError(f"{context}: expected string or list of strings")

        normalized_values: list[str] = []
        seen: set[str] = set()
        for index, item in enumerate(values):
            normalized = self._normalize_classification_text(item, f"{context}[{index}]")
            if normalized in seen:
                continue
            normalized_values.append(normalized)
            seen.add(normalized)
        return normalized_values

    def _normalize_classification_text(self, value: Any, context: str) -> str:
        if not isinstance(value, str):
            raise LibrarySeedError(f"{context}: expected non-empty string")
        normalized = value.strip()
        if not normalized:
            raise LibrarySeedError(f"{context}: expected non-empty string")
        return normalized

    def _build_localized_label(self, value: str) -> dict[str, str]:
        return {"EN": value}

    def _default_classification_hierarchy_level(self, axis_key: str) -> int:
        if axis_key == "object_type":
            return 1
        if axis_key == "composition":
            return 2
        return 3

    def _normalize_classification_hierarchy_level(
        self,
        raw_value: Any,
        context: str,
        axis_key: str,
    ) -> int:
        if raw_value is None:
            return self._default_classification_hierarchy_level(axis_key)
        if not isinstance(raw_value, int):
            raise LibrarySeedError(f"{context}: expected integer 1, 2, or 3")
        if raw_value not in (1, 2, 3):
            raise LibrarySeedError(f"{context}: expected integer 1, 2, or 3")
        return raw_value

    def _humanize_classification_key(self, axis_key: str) -> str:
        return " ".join(token.capitalize() for token in axis_key.split("_"))

    def _validate_payload(self, db: Session, payload: dict[str, list[dict[str, Any]]]) -> None:
        errors: list[str] = []

        enum_values = {item["enumlabel"] for item in self._get_priority_enum_values(db)}
        for row in payload["users"]:
            if "user_id" not in row:
                errors.append("users: missing user_id")
            if "login" not in row:
                errors.append("users: missing login")
            if "email" not in row:
                errors.append("users: missing email")
            if "password_hashed" not in row:
                errors.append(f"users[{row.get('user_id')}]: missing password_hashed")
            if "user_priority_enum" in row and row["user_priority_enum"] not in enum_values:
                errors.append(
                    f"users[{row.get('user_id')}]: invalid user_priority_enum '{row['user_priority_enum']}'"
                )

        user_ids = self._available_ids(db, "users", "user_id", payload["users"])
        material_ids = self._available_ids(db, "materials", "material_id", payload["materials"])
        material_standard_ids = self._available_ids(
            db,
            "material_standards_catalog",
            "standard_id",
            payload["material_standards_catalog"],
        )
        publication_ids = self._available_ids(
            db,
            "publications_catalog",
            "publication_id",
            payload["publications_catalog"],
        )
        material_test_record_ids = self._available_ids(
            db,
            "materials_test_records",
            "test_record_id",
            payload["materials_test_records"],
        )
        material_property_table_ids = self._available_ids(
            db,
            "materials_property_tables",
            "table_id",
            payload["materials_property_tables"],
        )
        material_property_column_ids = self._available_ids(
            db,
            "materials_property_table_to_columns_connectivity",
            "column_id",
            payload["materials_property_table_to_columns_connectivity"],
        )
        material_classification_axis_ids = self._available_ids(
            db,
            "material_classification_axes",
            "axis_id",
            payload["material_classification_axes"],
        )
        material_classification_value_ids = self._available_ids(
            db,
            "material_classification_values",
            "value_id",
            payload["material_classification_values"],
        )
        die_type_ids = self._available_ids(db, "die_types", "id", payload["die_types"])
        die_ids = self._available_ids(db, "dies", "id", payload["dies"])
        press_ids = self._available_ids(db, "presses", "id", payload["presses"])
        press_mode_ids = self._available_ids(db, "press_modes", "id", payload["press_modes"])

        for row in payload["materials"]:
            owner_id = row.get("owner_id")
            if owner_id is not None and owner_id not in user_ids:
                errors.append(f"materials[{row.get('material_id')}]: owner_id '{owner_id}' not found")

        for row in payload["material_standards_catalog"]:
            predecessor_standard_id = row.get("predecessor_standard_id")
            if predecessor_standard_id is not None and predecessor_standard_id not in material_standard_ids:
                errors.append(
                    "material_standards_catalog"
                    f"[{row.get('standard_id')}]: predecessor_standard_id '{predecessor_standard_id}' not found"
                )

        for row in payload["materials_designations"]:
            designation_id = row.get("designation_id")
            material_id = row.get("material_id")
            standard_id = row.get("standard_id")
            if material_id not in material_ids:
                errors.append(
                    f"materials_designations[{designation_id}]: material_id '{material_id}' not found"
                )
            if standard_id is not None and standard_id not in material_standard_ids:
                errors.append(
                    f"materials_designations[{designation_id}]: standard_id '{standard_id}' not found"
                )

        designation_ids = self._available_ids(
            db,
            "materials_designations",
            "designation_id",
            payload["materials_designations"],
        )

        for row in payload["materials_designations_standard_chemistry"]:
            designation_id = row.get("designation_id")
            if designation_id not in designation_ids:
                errors.append(
                    "materials_designations_standard_chemistry"
                    f"[{row.get('standard_chemistry_id')}]: designation_id '{designation_id}' not found"
                )

        for row in payload["materials_test_records"]:
            test_record_id = row.get("test_record_id")
            material_id = row.get("material_id")
            designation_id = row.get("designation_id")
            publication_id = row.get("publication_id")
            if material_id not in material_ids:
                errors.append(
                    f"materials_test_records[{test_record_id}]: material_id '{material_id}' not found"
                )
            if designation_id is not None and designation_id not in designation_ids:
                errors.append(
                    f"materials_test_records[{test_record_id}]: designation_id '{designation_id}' not found"
                )
            if publication_id is not None and publication_id not in publication_ids:
                errors.append(
                    f"materials_test_records[{test_record_id}]: publication_id '{publication_id}' not found"
                )

        for row in payload["materials_chemistry_tests_results"]:
            test_record_id = row.get("test_record_id")
            if test_record_id not in material_test_record_ids:
                errors.append(
                    "materials_chemistry_tests_results"
                    f"[{test_record_id},{row.get('element_symbol')}]: test_record_id '{test_record_id}' not found"
                )

        for row in payload["materials_property_tables"]:
            table_id = row.get("table_id")
            test_record_id = row.get("test_record_id")
            if test_record_id not in material_test_record_ids:
                errors.append(
                    f"materials_property_tables[{table_id}]: test_record_id '{test_record_id}' not found"
                )

        for row in payload["materials_property_table_to_columns_connectivity"]:
            column_id = row.get("column_id")
            table_id = row.get("table_id")
            if table_id not in material_property_table_ids:
                errors.append(
                    "materials_property_table_to_columns_connectivity"
                    f"[{column_id}]: table_id '{table_id}' not found"
                )

        for row in payload["materials_property_column_values"]:
            column_id = row.get("column_id")
            if column_id not in material_property_column_ids:
                errors.append(
                    "materials_property_column_values"
                    f"[{column_id},{row.get('point_index')}]: column_id '{column_id}' not found"
                )

        for row in payload["material_classification_axes"]:
            created_by_user_id = row.get("created_by_user_id")
            if created_by_user_id is not None and created_by_user_id not in user_ids:
                errors.append(
                    f"material_classification_axes[{row.get('axis_id')}]: created_by_user_id '{created_by_user_id}' not found"
                )

        for row in payload["material_classification_values"]:
            axis_id = row.get("axis_id")
            if axis_id not in material_classification_axis_ids:
                errors.append(
                    f"material_classification_values[{row.get('value_id')}]: axis_id '{axis_id}' not found"
                )
            created_by_user_id = row.get("created_by_user_id")
            if created_by_user_id is not None and created_by_user_id not in user_ids:
                errors.append(
                    f"material_classification_values[{row.get('value_id')}]: created_by_user_id '{created_by_user_id}' not found"
                )

        for row in payload["material_classification_assignments"]:
            material_id = row.get("material_id")
            value_id = row.get("value_id")
            if material_id not in material_ids:
                errors.append(
                    f"material_classification_assignments[{material_id},{value_id}]: material_id '{material_id}' not found"
                )
            if value_id not in material_classification_value_ids:
                errors.append(
                    f"material_classification_assignments[{material_id},{value_id}]: value_id '{value_id}' not found"
                )
            created_by_user_id = row.get("created_by_user_id")
            if created_by_user_id is not None and created_by_user_id not in user_ids:
                errors.append(
                    f"material_classification_assignments[{material_id},{value_id}]: created_by_user_id '{created_by_user_id}' not found"
                )

        for row in payload["dies"]:
            if row.get("die_type_id") not in die_type_ids:
                errors.append(f"dies[{row.get('id')}]: die_type_id '{row.get('die_type_id')}' not found")
            owner_user_id = row.get("owner_user_id")
            if owner_user_id is not None and owner_user_id not in user_ids:
                errors.append(f"dies[{row.get('id')}]: owner_user_id '{owner_user_id}' not found")

        for row in payload["die_assemblies"]:
            owner_user_id = row.get("owner_user_id")
            if owner_user_id is not None and owner_user_id not in user_ids:
                errors.append(f"die_assemblies[{row.get('id')}]: owner_user_id '{owner_user_id}' not found")
            for key in ("top_die_id", "bottom_die_id", "left_die_id", "right_die_id"):
                value = row.get(key)
                if value is not None and value not in die_ids:
                    errors.append(f"die_assemblies[{row.get('id')}]: {key} '{value}' not found")

        for row in payload["presses"]:
            owner_user_id = row.get("owner_user_id")
            if owner_user_id is not None and owner_user_id not in user_ids:
                errors.append(f"presses[{row.get('id')}]: owner_user_id '{owner_user_id}' not found")

        for row in payload["press_modes"]:
            owner_user_id = row.get("owner_user_id")
            if owner_user_id is not None and owner_user_id not in user_ids:
                errors.append(f"press_modes[{row.get('id')}]: owner_user_id '{owner_user_id}' not found")
            press_id = row.get("press_id")
            if press_id is not None and press_id not in press_ids:
                errors.append(f"press_modes[{row.get('id')}]: press_id '{press_id}' not found")

        for row in payload["press_die_map"]:
            if row.get("press_id") not in press_ids:
                errors.append(
                    f"press_die_map[{row.get('press_id')},{row.get('die_id')}]: press_id not found"
                )
            if row.get("die_id") not in die_ids:
                errors.append(
                    f"press_die_map[{row.get('press_id')},{row.get('die_id')}]: die_id not found"
                )
            owner_user_id = row.get("owner_user_id")
            if owner_user_id is not None and owner_user_id not in user_ids:
                errors.append(
                    f"press_die_map[{row.get('press_id')},{row.get('die_id')}]: owner_user_id '{owner_user_id}' not found"
                )

        if errors:
            raise LibrarySeedError("Validation failed: " + "; ".join(errors))

        if len(payload["press_modes"]) and not press_mode_ids:
            raise LibrarySeedError("Validation failed: press_modes IDs could not be resolved")

        if len(payload["presses"]) and not press_ids:
            raise LibrarySeedError("Validation failed: presses IDs could not be resolved")

        if len(payload["die_types"]) and not die_type_ids:
            raise LibrarySeedError("Validation failed: die_types IDs could not be resolved")

    def _upsert_payload(
        self,
        db: Session,
        payload: dict[str, list[dict[str, Any]]],
        only_missing: bool,
        triggered_by_user_id: Optional[int],
    ) -> SeedReport:
        processed: dict[str, int] = {}

        for table_name in self.SEED_ORDER:
            table = self._table_or_raise(table_name)
            if not self._table_exists(db, table_name):
                raise LibrarySeedError(f"Target table does not exist: {table_name}")

            rows = payload.get(table_name, [])
            if not rows:
                processed[table_name] = 0
                continue

            normalized_rows = [self._filter_row_by_columns(table, row) for row in rows]
            normalized_rows = [row for row in normalized_rows if row]
            if not normalized_rows:
                processed[table_name] = 0
                continue

            pk_cols = [col.name for col in table.primary_key.columns]
            if not pk_cols:
                raise LibrarySeedError(f"No primary key configured for table: {table_name}")

            stmt = pg_insert(table).values(normalized_rows)
            if only_missing:
                stmt = stmt.on_conflict_do_nothing(index_elements=pk_cols)
            else:
                updatable_cols = [
                    col.name for col in table.columns if col.name not in pk_cols
                ]
                set_map = {col: getattr(stmt.excluded, col) for col in updatable_cols}
                stmt = stmt.on_conflict_do_update(
                    index_elements=pk_cols,
                    set_=set_map,
                )

            db.execute(stmt)
            processed[table_name] = len(normalized_rows)

            self._sync_sequence(db, table)

        return SeedReport(
            file_hash=self._combined_file_hash(self._seed_files()),
            tables_processed=processed,
            only_missing=only_missing,
            triggered_by_user_id=triggered_by_user_id,
        )

    def _available_ids(
        self,
        db: Session,
        table_name: str,
        id_col: str,
        payload_rows: list[dict[str, Any]],
    ) -> set[int]:
        ids = {row[id_col] for row in payload_rows if isinstance(row.get(id_col), int)}
        if not self._table_exists(db, table_name):
            return ids
        table = self._table_or_raise(table_name)
        if id_col not in table.columns:
            return ids
        ids.update(
            value
            for (value,) in db.execute(select(table.c[id_col])).all()
            if isinstance(value, int)
        )
        return ids

    def _resolve_owner_user_id(
        self,
        value: Any,
        seed_login_to_id: dict[str, int],
        existing_login_to_id: dict[str, int],
    ) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            text_value = value.strip()
            if not text_value:
                return None
            if text_value.isdigit():
                return int(text_value)
            if text_value in seed_login_to_id:
                return seed_login_to_id[text_value]
            if text_value in existing_login_to_id:
                return existing_login_to_id[text_value]
        raise LibrarySeedError(f"Cannot resolve owner_user_id '{value}'")

    def _filter_row_by_columns(self, table: Table, row: dict[str, Any]) -> dict[str, Any]:
        table_cols = {col.name for col in table.columns}
        filtered = {k: v for k, v in row.items() if k in table_cols}
        for col in table.columns:
            if col.name in filtered:
                continue
            if not col.nullable and col.default is None and col.server_default is None and not col.primary_key:
                # Required column with no default and no value in payload.
                if col.name in {"created_at", "updated_at"}:
                    filtered[col.name] = datetime.utcnow()
        return filtered

    def _table_or_raise(self, table_name: str) -> Table:
        table = Base.metadata.tables.get(table_name)
        if table is None:
            raise LibrarySeedError(f"Unknown model table: {table_name}")
        return table

    def _count_rows(self, db: Session, table_name: str) -> int:
        if not self._table_exists(db, table_name):
            return 0
        table = self._table_or_raise(table_name)
        return int(db.execute(select(func.count()).select_from(table)).scalar_one())

    def _table_exists(self, db: Session, table_name: str) -> bool:
        return bool(
            db.execute(
                text("SELECT to_regclass(:name) IS NOT NULL"),
                {"name": f"public.{table_name}"},
            ).scalar()
        )

    def _parse_dt(self, value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is not None:
                parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
            return parsed
        raise LibrarySeedError(f"Invalid datetime value: {value}")

    def _file_hash(self, path: Path) -> str:
        h = sha256()
        with path.open("rb") as fh:
            h.update(fh.read())
        return h.hexdigest()

    def _combined_file_hash(self, paths: Iterable[Path]) -> str:
        h = sha256()
        for path in sorted(paths, key=lambda item: item.name):
            h.update(path.name.encode("utf-8"))
            h.update(b"\0")
            with path.open("rb") as fh:
                h.update(fh.read())
            h.update(b"\0")
        return h.hexdigest()

    def _ensure_seed_runs_table(self, db: Session) -> None:
        db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS seed_runs (
                    id BIGSERIAL PRIMARY KEY,
                    seed_name VARCHAR(255) NOT NULL,
                    file_hash VARCHAR(128) NOT NULL,
                    status VARCHAR(32) NOT NULL,
                    started_at TIMESTAMP NOT NULL DEFAULT now(),
                    finished_at TIMESTAMP NULL,
                    details JSONB NULL
                )
                """
            )
        )

    def _format_seed_exception(self, exc: Exception) -> str:
        if isinstance(exc, LibrarySeedError):
            return str(exc)

        message = str(exc).strip()
        if isinstance(exc, DBAPIError):
            db_message = str(exc.orig).strip() if exc.orig is not None else message
            compact_message = db_message.splitlines()[0] if db_message else "Database error"
            normalized_message = compact_message.lower()
            if (
                "undefinedcolumn" in normalized_message
                or "undefinedtable" in normalized_message
                or " does not exist" in normalized_message
            ):
                return (
                    "Database schema is out of date for library seeding. "
                    "Run `alembic upgrade head` and retry. "
                    f"Database error: {compact_message}"
                )
            return f"Database error during library seeding: {compact_message}"

        return message or "Library seeding failed unexpectedly."

    def _seed_runs_exists(self, db: Session) -> bool:
        return bool(
            db.execute(
                text("SELECT to_regclass('public.seed_runs') IS NOT NULL")
            ).scalar()
        )

    def _insert_seed_run(
        self,
        db: Session,
        seed_name: str,
        file_hash: str,
        status: str,
        details: Optional[dict[str, Any]] = None,
    ) -> int:
        row = db.execute(
            text(
                """
                INSERT INTO seed_runs (seed_name, file_hash, status, details)
                VALUES (:seed_name, :file_hash, :status, CAST(:details AS JSONB))
                RETURNING id
                """
            ),
            {
                "seed_name": seed_name,
                "file_hash": file_hash,
                "status": status,
                "details": json.dumps(details or {}),
            },
        ).mappings().first()
        if row is None:
            raise LibrarySeedError("Failed to create seed_runs row")
        return int(row["id"])

    def _update_seed_run(
        self,
        db: Session,
        run_id: int,
        status: str,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        db.execute(
            text(
                """
                UPDATE seed_runs
                SET status = :status,
                    details = CAST(:details AS JSONB),
                    finished_at = now()
                WHERE id = :run_id
                """
            ),
            {
                "run_id": run_id,
                "status": status,
                "details": json.dumps(details or {}),
            },
        )

    def _get_last_run(self, db: Session) -> Optional[dict[str, Any]]:
        if not self._seed_runs_exists(db):
            return None
        row = db.execute(
            text(
                """
                SELECT id, seed_name, file_hash, status, started_at, finished_at, details
                FROM seed_runs
                WHERE seed_name = 'library'
                ORDER BY id DESC
                LIMIT 1
                """
            )
        ).mappings().first()
        return dict(row) if row else None

    def _sync_sequence(self, db: Session, table: Table) -> None:
        pk_cols = [col for col in table.primary_key.columns]
        if len(pk_cols) != 1:
            return
        pk_col = pk_cols[0]
        if not isinstance(pk_col.type, Integer):
            return

        seq_name = db.execute(
            text("SELECT pg_get_serial_sequence(:table_name, :column_name)"),
            {"table_name": table.name, "column_name": pk_col.name},
        ).scalar()
        if not seq_name:
            return

        db.execute(
            text(
                f"""
                SELECT setval(
                    CAST(:seq_name AS regclass),
                    COALESCE((SELECT MAX({pk_col.name}) FROM {table.name}), 1),
                    true
                )
                """
            ),
            {"seq_name": seq_name},
        )

    def _get_priority_enum_values(self, db: Session) -> Iterable[dict[str, Any]]:
        rows = db.execute(
            text(
                """
                SELECT e.enumlabel
                FROM pg_type t
                JOIN pg_enum e ON t.oid = e.enumtypid
                JOIN pg_namespace n ON n.oid = t.typnamespace
                WHERE n.nspname = 'public' AND t.typname = 'priority_enum'
                ORDER BY e.enumsortorder
                """
            )
        ).mappings().all()
        return [dict(row) for row in rows]


library_seed_service = LibrarySeedService()
