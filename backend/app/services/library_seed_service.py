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
        "die_types",
        "dies",
        "die_assemblies",
        "presses",
        "press_modes",
        "press_die_map",
    ]

    def __init__(self, library_json_path: Optional[Path] = None) -> None:
        backend_root = Path(__file__).resolve().parents[2]
        self.library_json_path = library_json_path or backend_root / "data" / "config" / "library.json"

    def get_status(self, db: Session) -> dict[str, Any]:
        file_exists = self.library_json_path.exists()
        file_hash = self._file_hash(self.library_json_path) if file_exists else None

        counts: dict[str, int] = {}
        for table_name in self.SEED_ORDER:
            counts[table_name] = self._count_rows(db, table_name)

        needs_seed = any(counts[name] == 0 for name in self.SEED_ORDER)
        can_seed_without_auth = counts.get("users", 0) == 0
        last_run = self._get_last_run(db)

        return {
            "file_exists": file_exists,
            "file_path": str(self.library_json_path),
            "file_hash": file_hash,
            "counts": counts,
            "needs_seed": needs_seed,
            "is_seeded": not needs_seed,
            "can_seed_without_auth": can_seed_without_auth,
            "last_run": last_run,
        }

    def seed_library(
        self,
        db: Session,
        only_missing: bool = False,
        triggered_by_user_id: Optional[int] = None,
    ) -> dict[str, Any]:
        if not self.library_json_path.exists():
            raise LibrarySeedError(f"library.json not found: {self.library_json_path}")

        self._ensure_seed_runs_table(db)
        db.commit()

        file_hash = self._file_hash(self.library_json_path)
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
        with self.library_json_path.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)

        if not isinstance(raw, dict):
            raise LibrarySeedError("Invalid library.json format: expected object at root")

        payload: dict[str, list[dict[str, Any]]] = {}
        for raw_key, value in raw.items():
            table_name = self.TABLE_ALIASES.get(raw_key, raw_key)
            if table_name not in self.SEED_ORDER:
                continue
            if not isinstance(value, list):
                raise LibrarySeedError(f"Invalid section '{raw_key}': expected list")
            payload[table_name] = [dict(item) for item in value if isinstance(item, dict)]

        for table_name in self.SEED_ORDER:
            payload.setdefault(table_name, [])

        return payload

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

        owner_sections = {
            "materials": "owner_id",
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
        die_type_ids = self._available_ids(db, "die_types", "id", payload["die_types"])
        die_ids = self._available_ids(db, "dies", "id", payload["dies"])
        press_ids = self._available_ids(db, "presses", "id", payload["presses"])
        press_mode_ids = self._available_ids(db, "press_modes", "id", payload["press_modes"])

        for row in payload["materials"]:
            owner_id = row.get("owner_id")
            if owner_id is not None and owner_id not in user_ids:
                errors.append(f"materials[{row.get('material_id')}]: owner_id '{owner_id}' not found")

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
            file_hash=self._file_hash(self.library_json_path),
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
                if col.name == "created_at":
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
