"""Preprocessing services that compile documents into control programs."""

from .compiler import (
    CompiledControlProgram,
    CompiledControlProgramRow,
    PreprocessorCompiler,
    PreprocessorCompileError,
    ProcessCard,
)
from .control_program_builder import (
    ControlProgramError,
    OperationLibrarySnapshot,
    OperationTypeDefinition,
    TimeBetweenOperationDefinition,
    build_operations_tree,
    build_ordered_children_by_parent,
    flatten_operations_tree,
    load_operation_library_snapshot,
)
from .geometry import (
    GEOMETRY_TYPES,
    GeneratedGeometry,
    GeometryBuilder,
    GeometryError,
    GeometryTypeDefinition,
)
from .prolongation import (
    ProlongationComputationResult,
    ProlongationMathError,
    calculate_prolongation,
)
from .cutting import (
    CuttingComputationResult,
    CuttingMathError,
    calculate_cutting,
)
from .operation_keys import (
    AXIAL_PROLONGATION_TEMPLATE_IDS,
    CUTTING_TEMPLATE_IDS,
    FULL_DIE_TEMPLATE_IDS,
    PROLONGATION_TEMPLATE_IDS,
    RADIAL_PROLONGATION_TEMPLATE_IDS,
    SPIRAL_PROLONGATION_TEMPLATE_IDS,
    UPSETTING_TEMPLATE_IDS,
)
from .upsetting import (
    DieDimensions,
    PressModeParameters,
    UpsettingComputationResult,
    UpsettingMathError,
    calculate_upsetting,
)

__all__ = [
    "CompiledControlProgram",
    "CompiledControlProgramRow",
    "ControlProgramError",
    "CUTTING_TEMPLATE_IDS",
    "CuttingComputationResult",
    "CuttingMathError",
    "AXIAL_PROLONGATION_TEMPLATE_IDS",
    "FULL_DIE_TEMPLATE_IDS",
    "GEOMETRY_TYPES",
    "GeneratedGeometry",
    "GeometryBuilder",
    "GeometryError",
    "GeometryTypeDefinition",
    "DieDimensions",
    "OperationLibrarySnapshot",
    "OperationTypeDefinition",
    "PressModeParameters",
    "PreprocessorCompiler",
    "PreprocessorCompileError",
    "ProcessCard",
    "PROLONGATION_TEMPLATE_IDS",
    "ProlongationComputationResult",
    "ProlongationMathError",
    "RADIAL_PROLONGATION_TEMPLATE_IDS",
    "SPIRAL_PROLONGATION_TEMPLATE_IDS",
    "TimeBetweenOperationDefinition",
    "UpsettingComputationResult",
    "UpsettingMathError",
    "build_operations_tree",
    "build_ordered_children_by_parent",
    "calculate_cutting",
    "calculate_prolongation",
    "calculate_upsetting",
    "flatten_operations_tree",
    "load_operation_library_snapshot",
    "UPSETTING_TEMPLATE_IDS",
]
