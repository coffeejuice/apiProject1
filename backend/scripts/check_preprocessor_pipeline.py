"""Smoke-check the document_operations -> Pre -> simulation_steps path."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path
import sys

from sqlalchemy import select, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.document.block import Block
from app.models.document.document import Document, DocumentVersion, PreprocessStatus
from app.models.document.document_operation import DocumentOperation
from app.models.library.die import DieAssembly
from app.models.library.material import Material, MaterialVersion
from app.models.project import Project
from app.models.user import User
from app.models.workflow_runtime import SimulationStep, SimulationStepStatus, SimulationStepStatusEnum
from app.orchestration.channels import PRE_JOBS_CHANNEL
from app.orchestration.pg_notify import broadcast_notify
from app.orchestration.runtime_backend import (
    PreJobClaimer,
    PreJobExecutor,
    _rebuild_simulation_steps,
    build_document_operation_outputs_for_document_version,
)
from app.services.block_props import DEFORMATION_PROPERTIES, DOCUMENT_PROPERTIES, OPERATION_PROPERTIES
from app.services.block_service import (
    DEFORMATION_BLOCK_TYPE_ID,
    DOCUMENT_BLOCK_TYPE_ID,
    OPERATION_BLOCK_TYPE_ID,
    create_block,
)
from app.services.document_operations import regenerate_document_operations
from app.services.operation_blocks import build_operation_props
from app.services.preprocessor.control_program_builder import build_semantic_operation_definitions
from app.services.preprocessor.compiler import PreprocessorCompileError, PreprocessorCompiler
from app.services.preprocessor.operation_keys import (
    AXIAL_PROLONGATION_TEMPLATE_IDS,
    CUTTING_TEMPLATE_IDS,
    DOCUMENT_INITIAL_DATA_TEMPLATE_ID,
    FULL_DIE_TEMPLATE_IDS,
    FURNACE_TEMPLATE_ID,
    GEOMETRY_TEMPLATE_PREFIX,
    HEATING_TEMPERATURE_DURATION_TEMPLATE_ID,
    RADIAL_INITIAL_ROTATIONS,
    RADIAL_PROLONGATION_TEMPLATE_IDS,
    SPIRAL_PROLONGATION_TEMPLATE_IDS,
    UPSETTING_TEMPLATE_IDS,
)


GENERIC_FALLBACK_NOTE = "Control row compiled without operation-family-specific deformation math."
STAGE1_FIXTURE_DOCUMENT_NAME = "Codex Stage1 Pre Fixture"
STAGE1_WORKER_NAME = "pre-stage1-check"
FORBIDDEN_PRE_TABLE_NAMES = (
    "server_pre_main",
    "process_versions",
    "operations_library",
    "document_blocks_library",
)


def _adapter_for_template(template_id: str) -> str:
    if template_id == DOCUMENT_INITIAL_DATA_TEMPLATE_ID or template_id.startswith(GEOMETRY_TEMPLATE_PREFIX):
        return "billet_geometry"
    if template_id == FURNACE_TEMPLATE_ID:
        return "furnace"
    if template_id == HEATING_TEMPERATURE_DURATION_TEMPLATE_ID:
        return "heating_duration"
    if template_id in UPSETTING_TEMPLATE_IDS:
        return "upsetting_math"
    if template_id in AXIAL_PROLONGATION_TEMPLATE_IDS:
        return "axial_prolongation_math"
    if template_id in SPIRAL_PROLONGATION_TEMPLATE_IDS:
        return "spiral_rounding_math"
    if template_id in RADIAL_PROLONGATION_TEMPLATE_IDS:
        return "radial_prolongation_math"
    if template_id == RADIAL_INITIAL_ROTATIONS:
        return "radial_orientation"
    if template_id in FULL_DIE_TEMPLATE_IDS:
        return "full_die_math"
    if template_id in CUTTING_TEMPLATE_IDS:
        return "cutting_math"
    return "generic_fallback"


def _list_support() -> int:
    generic_templates: list[str] = []
    for definition in build_semantic_operation_definitions():
        adapter = _adapter_for_template(definition.operation_template_id)
        if adapter == "generic_fallback":
            generic_templates.append(definition.operation_template_id)
        print(
            "support "
            f"template={definition.operation_template_id} "
            f"adapter={adapter} "
            f"columns={','.join(definition.db_column_names)}"
        )
    if generic_templates:
        print(f"GENERIC_FALLBACK_TEMPLATES={','.join(generic_templates)}", file=sys.stderr)
        return 1
    return 0


def _now_utc_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _latest_version(document_id: int) -> DocumentVersion | None:
    with SessionLocal() as session:
        return session.scalars(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.document_version_id.desc())
        ).first()


def _runtime_counts(document_id: int) -> dict[str, int]:
    with SessionLocal() as session:
        return dict(
            session.execute(
                text(
                    """
                    SELECT COUNT(DISTINCT o.document_operation_id) AS operations_count,
                           COUNT(DISTINCT s.document_operation_id) AS simulation_steps_count,
                           COUNT(DISTINCT s.document_operation_id) FILTER (WHERE s.preprocess_ready) AS preprocess_ready_count
                    FROM document_operations o
                    LEFT JOIN simulation_steps s ON s.document_operation_id = o.document_operation_id
                    WHERE o.document_id = :document_id
                    """
                ),
                {"document_id": document_id},
            ).mappings().one()
        )


def _get_fixture_base_rows(session) -> tuple[User, Project, Material | None, MaterialVersion | None, DieAssembly]:
    user = session.scalars(select(User).order_by(User.user_id.asc())).first()
    if user is None:
        raise RuntimeError("Stage 1 fixture requires at least one user row")

    project = session.scalars(
        select(Project)
        .where(Project.deleted_at.is_(None))
        .order_by(Project.project_id.asc())
    ).first()
    if project is None:
        material = session.scalars(select(Material).order_by(Material.material_id.asc())).first()
        project = Project(
            user_id=user.user_id,
            material_id=material.material_id if material is not None else None,
            name="Codex Stage1 Fixture Project",
            notes="Auto-created by check_preprocessor_pipeline.py --create-stage1-fixture.",
        )
        session.add(project)
        session.flush()

    material: Material | None = None
    material_version: MaterialVersion | None = None
    if project.material_id is not None:
        material = session.get(Material, project.material_id)
    if material is None:
        material = session.scalars(select(Material).order_by(Material.material_id.asc())).first()
        if material is not None:
            project.material_id = material.material_id
    if material is not None:
        material_version = session.scalars(
            select(MaterialVersion)
            .where(MaterialVersion.material_id == material.material_id)
            .order_by(MaterialVersion.version_no.desc(), MaterialVersion.material_version_id.desc())
        ).first()

    die_assembly = session.scalars(
        select(DieAssembly)
        .where(
            DieAssembly.is_obsolete.is_(False),
            DieAssembly.top_die_id.is_not(None),
            DieAssembly.bottom_die_id.is_not(None),
        )
        .order_by(DieAssembly.id.asc())
    ).first()
    if die_assembly is None:
        raise RuntimeError("Stage 1 fixture requires at least one non-obsolete die assembly with top/bottom dies")

    return user, project, material, material_version, die_assembly


def _reset_document_blocks(session, document: Document) -> None:
    document.first_block_id = None
    session.flush()
    for block in session.scalars(
        select(Block).where(Block.document_id == document.document_id)
    ).all():
        session.delete(block)
    session.flush()


def _latest_or_create_version(session, document: Document, *, user: User) -> DocumentVersion:
    version = session.scalars(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document.document_id)
        .order_by(DocumentVersion.document_version_id.desc())
    ).first()
    if version is None:
        version = DocumentVersion(
            document_id=document.document_id,
            is_editable=True,
            name=f"{document.name} working version",
        )
        session.add(version)
        session.flush()
    return version


def _create_stage1_fixture(*, profile: str = "minimal") -> int:
    with SessionLocal() as session:
        user, project, material, material_version, die_assembly = _get_fixture_base_rows(session)
        document = session.scalars(
            select(Document)
            .where(
                Document.project_id == project.project_id,
                Document.name == STAGE1_FIXTURE_DOCUMENT_NAME,
                Document.deleted_at.is_(None),
            )
            .order_by(Document.document_id.asc())
        ).first()
        if document is None:
            document = Document(
                project_id=project.project_id,
                editor_user_id=user.user_id,
                material_version_id=material_version.material_version_id if material_version is not None else None,
                name=STAGE1_FIXTURE_DOCUMENT_NAME,
                notes="Auto-created Stage 1 Pre validation fixture.",
            )
            session.add(document)
            session.flush()
        else:
            document.material_version_id = material_version.material_version_id if material_version is not None else None
            document.updated_at = _now_utc_naive()
            _reset_document_blocks(session, document)

        root_props = {
            DOCUMENT_PROPERTIES: {
                "name": STAGE1_FIXTURE_DOCUMENT_NAME,
                "heat_no": "STAGE1",
                "finished_size": "100 x 100",
                "remarks": f"Fixture profile: {profile}",
                "preview_status": "ok",
                "material_id": material.material_id if material is not None else "",
                "geometry_type_id": 75,
                "weight": 78.5,
                "attributes": {
                    "height": 100.0,
                    "width": 100.0,
                    "density_kg_per_mm3": 7.85e-6,
                },
                "mesh_elements": 10,
                "section_numbering_start": 2,
            }
        }
        root = create_block(
            db=session,
            document_id=document.document_id,
            block_type_id=DOCUMENT_BLOCK_TYPE_ID,
            props=root_props,
            previous_block_id=None,
            is_system=True,
            is_removable=False,
            fixed_position=0,
        )
        deformation_props = {
            DEFORMATION_PROPERTIES: {
                "die_selection_mode": "pair",
                "die_assembly_id": die_assembly.id,
                "speed_prolongation": 10.0,
                "speed_upsetting": 10.0,
                "deformation_variables": {
                    "tail_flattening_stroke": 5.0,
                    "tail_chamfering_stroke": 5.0,
                    "radial_feed": 40.0,
                },
                "feed_settings": {
                    "cogging": {
                        "feed_direction_id": 2,
                        "feed_first": 80.0,
                        "feed_middle": 80.0,
                        "feed_last": 80.0,
                    },
                    "radial": {
                        "feed_direction_id": 2,
                        "feed_first": 40.0,
                        "feed_middle": 40.0,
                        "feed_last": 40.0,
                    },
                    "transversal": {
                        "feed_direction_id": 2,
                        "feed_first": 80.0,
                        "feed_middle": 80.0,
                        "feed_last": 80.0,
                    },
                },
            }
        }
        deformation = create_block(
            db=session,
            document_id=document.document_id,
            block_type_id=DEFORMATION_BLOCK_TYPE_ID,
            props=deformation_props,
            previous_block_id=root.block_id,
        )
        operation = create_block(
            db=session,
            document_id=document.document_id,
            block_type_id=OPERATION_BLOCK_TYPE_ID,
            props={
                OPERATION_PROPERTIES: build_operation_props(
                    "operation.cogging",
                    {
                        "operation_template_id": "operation.cogging",
                        "operation_text": "90",
                    },
                )
            },
            previous_block_id=deformation.block_id,
        )

        version = _latest_or_create_version(session, document, user=user)
        version.name = f"{document.name} working version"
        version.is_editable = True
        version.run_switch_status = False
        version.preprocess_status = PreprocessStatus.ready
        version.preprocess_error = None
        version.last_modified = _now_utc_naive()
        count = regenerate_document_operations(session, document.document_id)
        version.operations_count = count
        session.commit()
        print(
            "stage1_fixture "
            f"document_id={document.document_id} "
            f"document_version_id={version.document_version_id} "
            f"profile={profile} "
            f"operations={count} "
            f"operation_block_id={operation.block_id}"
        )
        return int(document.document_id)


def _regenerate(document_id: int) -> None:
    with SessionLocal() as session:
        count = regenerate_document_operations(session, document_id)
        session.commit()
        print(f"regenerated_operations={count}")


def _verify_billet_output(document_id: int) -> list[str]:
    errors: list[str] = []
    with SessionLocal() as session:
        operation = session.scalars(
            select(DocumentOperation)
            .where(
                DocumentOperation.document_id == document_id,
                DocumentOperation.operation_template_id == DOCUMENT_INITIAL_DATA_TEMPLATE_ID,
            )
            .order_by(DocumentOperation.operation_order.asc())
        ).first()
        if operation is None:
            return ["missing document_initial_data operation row"]

        target = dict(operation.operation_parameters or {})
        for namespace in ("document_info", "production_data", "material", "input_stock", "mesh"):
            if namespace not in target:
                errors.append(f"document_initial_data operation_parameters missing {namespace}")

        step = session.get(SimulationStep, operation.document_operation_id)
        if step is None:
            errors.append(f"missing simulation_steps sibling for document_operation_id={operation.document_operation_id}")
            return errors

        for field in ("initial_geometry", "final_geometry"):
            geometry = getattr(step, field)
            if not isinstance(geometry, dict):
                errors.append(f"simulation_steps.{field} is empty")
                continue
            for key in (
                "type_id",
                "shape",
                "volume_mm3",
                "cross_section_area_mm2",
                "equivalent_diameter_mm",
                "width_mm",
                "height_mm",
                "length_mm",
                "cross_section_outline",
            ):
                if key not in geometry:
                    errors.append(f"simulation_steps.{field} missing {key}")
        calculations = dict(step.calculations or {})
        if "mesh_elements" not in calculations:
            errors.append("simulation_steps.calculations missing mesh_elements")
        if step.operation_template_id != DOCUMENT_INITIAL_DATA_TEMPLATE_ID:
            errors.append(
                f"simulation_steps.operation_template_id expected {DOCUMENT_INITIAL_DATA_TEMPLATE_ID}, got {step.operation_template_id}"
            )
    return errors


def _compile(document_id: int, *, apply: bool, verify_billet: bool = False) -> int:
    version = _latest_version(document_id)
    if version is None:
        print(f"No document version found for document_id={document_id}", file=sys.stderr)
        return 2

    with SessionLocal() as session:
        version = session.get(DocumentVersion, version.document_version_id)
        if version is None:
            print(f"Document version disappeared for document_id={document_id}", file=sys.stderr)
            return 2

        try:
            document_operation_outputs = build_document_operation_outputs_for_document_version(session, version)
            print(
                f"document_id={document_id} document_version_id={version.document_version_id} document_operation_outputs={len(document_operation_outputs)}",
                flush=True,
            )
            compiled = PreprocessorCompiler().compile_from_database(session=session, document_operation_outputs=document_operation_outputs)
        except PreprocessorCompileError as exc:
            print(f"PREPROCESSOR_COMPILE_ERROR: {exc}", file=sys.stderr)
            return 1

        generic_count = 0
        for row in compiled.rows:
            adapter_status = (
                "generic_fallback"
                if GENERIC_FALLBACK_NOTE in row.compiler_notes
                else "ported"
            )
            if adapter_status == "generic_fallback":
                generic_count += 1
            print(
                "row "
                f"order={row.sequence_index + 1} "
                f"document_operation_id={row.document_operation_id} "
                f"template={row.operation_template_id} "
                f"operation_type={row.operation_type} "
                f"adapter={adapter_status}"
            )

        if apply:
            updated = _rebuild_simulation_steps(
                session,
                document_version=version,
                compiled_program=compiled,
            )
            session.commit()
            print(f"updated_simulation_steps={updated}")
        else:
            session.rollback()

        counts = _runtime_counts(document_id)
        print(
            "counts "
            f"operations={counts['operations_count']} "
            f"simulation_steps={counts['simulation_steps_count']} "
            f"preprocess_ready={counts['preprocess_ready_count']} "
            f"compiled_rows={len(compiled.rows)} "
            f"generic_fallback_rows={generic_count}"
        )
        if verify_billet:
            billet_errors = _verify_billet_output(document_id)
            if billet_errors:
                for error in billet_errors:
                    print(f"BILLET_OUTPUT_ERROR: {error}", file=sys.stderr)
                return 1
            print("billet_output=ok")
        return 0


def _audit_stage1_source() -> int:
    checked_paths = (
        Path("app/workers/pre_worker.py"),
        Path("app/workers/base.py"),
        Path("app/orchestration/runtime_backend.py"),
        Path("app/services/preprocessor/compiler.py"),
    )
    found: list[str] = []
    root = Path(__file__).resolve().parents[1]
    for relative_path in checked_paths:
        path = root / relative_path
        text_value = path.read_text(encoding="utf-8")
        for table_name in FORBIDDEN_PRE_TABLE_NAMES:
            if table_name in text_value:
                found.append(f"{relative_path}:{table_name}")
    if found:
        print("STAGE1_SOURCE_AUDIT_FAILED " + " ".join(found), file=sys.stderr)
        return 1
    print("stage1_source_audit=ok")
    return 0


def _queue_pre(document_id: int, *, worker_priority: int = -32768) -> int:
    version = _latest_version(document_id)
    if version is None:
        print(f"No document version found for document_id={document_id}", file=sys.stderr)
        return 2
    with SessionLocal() as session:
        version = session.get(DocumentVersion, version.document_version_id)
        if version is None:
            print(f"Document version disappeared for document_id={document_id}", file=sys.stderr)
            return 2
        version.is_editable = False
        version.run_switch_status = True
        version.preprocess_status = PreprocessStatus.queued
        version.preprocess_error = None
        version.preprocess_worker_name = None
        version.preprocess_started_at = None
        version.preprocess_finished_at = None
        version.simulation_priority = worker_priority
        session.commit()
        print(
            "queued_pre "
            f"document_id={document_id} "
            f"document_version_id={version.document_version_id} "
            f"priority={worker_priority}"
        )
    broadcast_notify((PRE_JOBS_CHANNEL,), "wake")
    return 0


def _run_pre_once(document_id: int, *, worker_name: str = STAGE1_WORKER_NAME) -> int:
    expected_version = _latest_version(document_id)
    if expected_version is None:
        print(f"No document version found for document_id={document_id}", file=sys.stderr)
        return 2

    claimed = PreJobClaimer().claim_next_job(worker_name=worker_name)
    if claimed is None:
        print("No queued Pre job was claimed", file=sys.stderr)
        return 1
    if int(claimed.job_id) != int(expected_version.document_version_id):
        print(
            f"Claimed unexpected Pre job_id={claimed.job_id}, expected document_version_id={expected_version.document_version_id}",
            file=sys.stderr,
        )
        return 1

    PreJobExecutor().execute(claimed)
    with SessionLocal() as session:
        version = session.get(DocumentVersion, expected_version.document_version_id)
        if version is None:
            print("Claimed document version disappeared", file=sys.stderr)
            return 2
        if version.preprocess_status != PreprocessStatus.ready:
            print(
                f"Pre worker one-shot did not finish ready: status={version.preprocess_status} error={version.preprocess_error}",
                file=sys.stderr,
            )
            return 1
        print(
            "pre_worker_once=ok "
            f"document_id={document_id} "
            f"document_version_id={version.document_version_id} "
            f"worker={worker_name}"
        )
    return 0


def _validate_failure_diagnostics(document_id: int) -> int:
    controlled_message = "Stage 1 controlled invalid operation"
    expected_version = _latest_version(document_id)
    if expected_version is None:
        print(f"No document version found for document_id={document_id}", file=sys.stderr)
        return 2

    with SessionLocal() as session:
        operation = session.scalars(
            select(DocumentOperation)
            .where(
                DocumentOperation.document_id == document_id,
                DocumentOperation.operation_template_id != DOCUMENT_INITIAL_DATA_TEMPLATE_ID,
            )
            .order_by(DocumentOperation.operation_order.asc())
        ).first()
        if operation is None:
            print("No non-initial document operation found for controlled failure check", file=sys.stderr)
            return 1

        document_operation_id = int(operation.document_operation_id)
        operation.parse_status = "error"
        operation.parse_errors = [
            {
                "code": "stage1_controlled_failure",
                "message": controlled_message,
            }
        ]

        version = session.get(DocumentVersion, expected_version.document_version_id)
        if version is None:
            print("Document version disappeared before controlled failure check", file=sys.stderr)
            return 2
        version.is_editable = False
        version.run_switch_status = True
        version.preprocess_status = PreprocessStatus.queued
        version.preprocess_error = None
        version.preprocess_worker_name = None
        version.preprocess_started_at = None
        version.preprocess_finished_at = None
        version.simulation_priority = -32767
        session.commit()

    broadcast_notify((PRE_JOBS_CHANNEL,), "wake")
    claimed = PreJobClaimer().claim_next_job(worker_name=f"{STAGE1_WORKER_NAME}-failure")
    if claimed is None:
        print("No queued Pre job was claimed for controlled failure check", file=sys.stderr)
        return 1
    if int(claimed.job_id) != int(expected_version.document_version_id):
        print(
            f"Controlled failure check claimed unexpected Pre job_id={claimed.job_id}, "
            f"expected document_version_id={expected_version.document_version_id}",
            file=sys.stderr,
        )
        return 1

    PreJobExecutor().execute(claimed)

    errors: list[str] = []
    with SessionLocal() as session:
        version = session.get(DocumentVersion, expected_version.document_version_id)
        if version is None:
            print("Document version disappeared after controlled failure check", file=sys.stderr)
            return 2
        if version.preprocess_status != PreprocessStatus.failed:
            errors.append(f"expected preprocess_status=failed, got {version.preprocess_status}")
        if version.run_switch_status:
            errors.append("expected run_switch_status=false after controlled Pre failure")
        if controlled_message not in str(version.preprocess_error or ""):
            errors.append("version.preprocess_error does not include controlled failure message")

        step = session.get(SimulationStep, document_operation_id)
        if step is None:
            errors.append(f"missing simulation_steps sibling for document_operation_id={document_operation_id}")
        else:
            calculations = dict(step.calculations or {})
            if calculations.get("preprocessor_status") != "failed":
                errors.append("simulation_steps.calculations.preprocessor_status is not failed")
            if controlled_message not in str(calculations.get("preprocessor_error") or ""):
                errors.append("simulation_steps.calculations.preprocessor_error does not include controlled failure message")

        step_status = session.get(SimulationStepStatus, document_operation_id)
        if step_status is None:
            errors.append(f"missing status sibling for document_operation_id={document_operation_id}")
        else:
            if step_status.status != SimulationStepStatusEnum.failed:
                errors.append(f"expected status.status=failed, got {step_status.status}")
            if controlled_message not in str(step_status.last_error or ""):
                errors.append("status.last_error does not include controlled failure message")
            error_payload = dict(step_status.error_payload or {})
            if error_payload.get("document_operation_id") != document_operation_id:
                errors.append("status.error_payload has wrong document_operation_id")
            if controlled_message not in str(error_payload.get("message") or ""):
                errors.append("status.error_payload.message does not include controlled failure message")

    if errors:
        for error in errors:
            print(f"FAILURE_DIAGNOSTIC_ERROR: {error}", file=sys.stderr)
        return 1

    print(f"failure_diagnostics=ok document_operation_id={document_operation_id}")
    return 0


def _validate_stage1(document_id: int | None, *, worker_once: bool) -> int:
    if _audit_stage1_source() != 0:
        return 1
    if _list_support() != 0:
        return 1

    target_document_id = document_id if document_id is not None else _create_stage1_fixture()
    _regenerate(target_document_id)
    dry_run_status = _compile(target_document_id, apply=False)
    if dry_run_status != 0:
        return dry_run_status
    apply_status = _compile(target_document_id, apply=True, verify_billet=True)
    if apply_status != 0:
        return apply_status

    if worker_once:
        queue_status = _queue_pre(target_document_id)
        if queue_status != 0:
            return queue_status
        worker_status = _run_pre_once(target_document_id)
        if worker_status != 0:
            return worker_status
        billet_errors = _verify_billet_output(target_document_id)
        if billet_errors:
            for error in billet_errors:
                print(f"BILLET_OUTPUT_ERROR: {error}", file=sys.stderr)
            return 1
        failure_status = _validate_failure_diagnostics(target_document_id)
        _regenerate(target_document_id)
        restore_status = _compile(target_document_id, apply=True, verify_billet=True)
        if failure_status != 0:
            return failure_status
        if restore_status != 0:
            return restore_status

    print(f"STAGE1_VALIDATION_OK document_id={target_document_id}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--document-id", type=int)
    parser.add_argument(
        "--list-support",
        action="store_true",
        help="Print semantic operation ids and current compiler adapter coverage.",
    )
    parser.add_argument(
        "--audit-stage1-source",
        action="store_true",
        help="Check the current Pre worker path for forbidden old-project table references.",
    )
    parser.add_argument(
        "--create-stage1-fixture",
        action="store_true",
        help="Create or reset a minimal valid document for Stage 1 Pre validation.",
    )
    parser.add_argument(
        "--validate-stage1",
        action="store_true",
        help="Run Stage 1 source audit, support audit, fixture/dry-run/apply, and billet-output checks.",
    )
    parser.add_argument(
        "--worker-once",
        action="store_true",
        help="With --validate-stage1, queue the target document and execute one real Pre claimer/executor cycle.",
    )
    parser.add_argument(
        "--verify-billet-output",
        action="store_true",
        help="After --apply, verify document_initial_data wrote geometry into the sibling simulation_steps row.",
    )
    parser.add_argument(
        "--queue-pre",
        action="store_true",
        help="Mark the latest document version queued for the Pre worker and send a wake notification.",
    )
    parser.add_argument(
        "--run-pre-once",
        action="store_true",
        help="Claim and execute one queued Pre job for --document-id using the real claimer/executor path.",
    )
    parser.add_argument(
        "--regenerate",
        action="store_true",
        help="Regenerate document_operations before the dry-run compile.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write compiled output into existing sibling simulation_steps rows.",
    )
    args = parser.parse_args()

    if args.audit_stage1_source:
        return _audit_stage1_source()
    if args.list_support:
        return _list_support()
    if args.create_stage1_fixture:
        _create_stage1_fixture()
        return 0
    if args.validate_stage1:
        return _validate_stage1(args.document_id, worker_once=args.worker_once)
    if args.document_id is None:
        parser.error(
            "--document-id is required unless --list-support, --audit-stage1-source, "
            "--create-stage1-fixture, or --validate-stage1 is used"
        )

    if args.regenerate:
        _regenerate(args.document_id)
    if args.queue_pre:
        return _queue_pre(args.document_id)
    if args.run_pre_once:
        return _run_pre_once(args.document_id)
    return _compile(args.document_id, apply=args.apply, verify_billet=args.verify_billet_output)


if __name__ == "__main__":
    raise SystemExit(main())
