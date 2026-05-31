import { useEffect, useMemo, useState } from 'react'

import { apiClient } from '../../lib/apiClient'
import type {
  DocumentSimulationStepListResponse,
  DocumentSimulationStepRecord,
  DocumentSimulationStepSurfaceResponse,
  SimulationStepDiagnosticsRecord,
  SimulationStepRecord,
  SimulationStepStatusRecord,
} from '../../types/api'
import type { BlockData } from '../blocks'
import { StepGeometryPreviewGrid } from '../simulationSteps/SimulationStepsView'

const HEATING_BLOCK_TYPE_ID = 'heating'
const DEFORMATION_BLOCK_TYPE_ID = 'deformation'
const FURNACE_BLOCK_TYPE_ID = 'furnace'
const OPERATION_BLOCK_TYPE_ID = 'operation'

type SimulationStepViewRecord = SimulationStepRecord & {
  simulation_step: SimulationStepRecord
  diagnostics: SimulationStepDiagnosticsRecord
  simulation_step_status?: SimulationStepStatusRecord | null
}

function toStepViewRecord(record: DocumentSimulationStepRecord): SimulationStepViewRecord {
  const simulationStep = record.simulation_step
  const normalizedStep: SimulationStepRecord = {
    ...simulationStep,
    pre_input: simulationStep.pre_input || simulationStep.control_parameters || {},
    pre_output: simulationStep.pre_output || simulationStep.step_specific_parameters || {},
    calculations: simulationStep.calculations || simulationStep.metrics || {},
  }
  const simulationStepStatus = record.simulation_step_status || null
  return {
    ...normalizedStep,
    simulation_step: normalizedStep,
    diagnostics: record.diagnostics || {
      response_sources: {},
      related_log_query: {},
      api_messages: [],
    },
    simulation_step_status: simulationStepStatus,
  }
}

interface DocumentInlineResultsProps {
  documentId: string | null
  blocks: BlockData[]
  contextBlockId: string
  showPreprocessor: boolean
  showPostprocessor: boolean
  hasUnsavedChanges: boolean
}

function isTopLevelSection(block: BlockData): boolean {
  return block.block_type_id === HEATING_BLOCK_TYPE_ID || block.block_type_id === DEFORMATION_BLOCK_TYPE_ID
}

function blockDisplayName(block: BlockData | undefined): string {
  if (!block) {
    return 'Selected block'
  }
  if (block.block_type_id === HEATING_BLOCK_TYPE_ID) {
    return 'Heating'
  }
  if (block.block_type_id === DEFORMATION_BLOCK_TYPE_ID) {
    return 'Deformation'
  }
  if (block.block_type_id === FURNACE_BLOCK_TYPE_ID) {
    return 'Furnace'
  }
  if (block.block_type_id !== OPERATION_BLOCK_TYPE_ID) {
    return 'Selected block'
  }

  const template = block.props.operation_template || block.props.template_snapshot
  if (template && typeof template === 'object') {
    const label = (template as { display_name?: unknown; label?: unknown }).display_name
      || (template as { display_name?: unknown; label?: unknown }).label
    if (typeof label === 'string' && label.trim()) {
      return label.trim()
    }
  }

  const title = block.props.title
  if (typeof title === 'string' && title.trim()) {
    return title.trim()
  }

  return 'Operation'
}

function relatedSourceBlockIds(blocks: BlockData[], blockId: string): Set<string> {
  const blockIndex = blocks.findIndex((block) => block.block_id === blockId)
  if (blockIndex < 0) {
    return new Set()
  }

  const block = blocks[blockIndex]
  if (block.block_type_id === OPERATION_BLOCK_TYPE_ID || block.block_type_id === FURNACE_BLOCK_TYPE_ID) {
    return new Set([block.block_id])
  }

  if (!isTopLevelSection(block)) {
    return new Set()
  }

  const childType = block.block_type_id === HEATING_BLOCK_TYPE_ID ? FURNACE_BLOCK_TYPE_ID : OPERATION_BLOCK_TYPE_ID
  const related = new Set<string>()
  for (let index = blockIndex + 1; index < blocks.length; index += 1) {
    const candidate = blocks[index]
    if (isTopLevelSection(candidate)) {
      break
    }
    if (candidate.block_type_id === childType) {
      related.add(candidate.block_id)
    }
  }
  return related
}

function statusLabel(step: SimulationStepViewRecord): string {
  const calculationStatus = typeof step.calculations?.preprocessor_status === 'string'
    ? step.calculations.preprocessor_status
    : null
  return calculationStatus || step.simulation_step_status?.status || (step.preprocess_ready ? 'ready' : 'not ready')
}

function operationTitle(step: SimulationStepViewRecord): string {
  return step.operation_label_snapshot || step.operation_template_id || step.operation_kind
}

export default function DocumentInlineResults({
  documentId,
  blocks,
  contextBlockId,
  showPreprocessor,
  showPostprocessor,
  hasUnsavedChanges,
}: DocumentInlineResultsProps) {
  const [steps, setSteps] = useState<SimulationStepViewRecord[]>([])
  const [selectedStepId, setSelectedStepId] = useState<number | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [surfaceMesh, setSurfaceMesh] = useState<DocumentSimulationStepSurfaceResponse | null>(null)
  const [isSurfaceLoading, setIsSurfaceLoading] = useState(false)
  const [surfaceError, setSurfaceError] = useState<string | null>(null)

  const contextBlock = useMemo(
    () => blocks.find((block) => block.block_id === contextBlockId),
    [blocks, contextBlockId]
  )
  const relatedBlockIds = useMemo(
    () => relatedSourceBlockIds(blocks, contextBlockId),
    [blocks, contextBlockId]
  )
  const visibleSteps = useMemo(
    () => steps.filter((step) => step.source_block_id && relatedBlockIds.has(step.source_block_id)),
    [relatedBlockIds, steps]
  )
  const selectedStep = useMemo(() => {
    if (visibleSteps.length === 0) {
      return null
    }
    return visibleSteps.find((step) => step.document_operation_id === selectedStepId) || visibleSteps[visibleSteps.length - 1]
  }, [selectedStepId, visibleSteps])

  useEffect(() => {
    if (!showPreprocessor || !documentId) {
      setSteps([])
      setSelectedStepId(null)
      setError(null)
      return
    }

    let isCancelled = false
    setIsLoading(true)
    setError(null)

    apiClient
      .get<DocumentSimulationStepListResponse>(`/documents/${documentId}/simulation-steps`)
      .then((response) => {
        if (isCancelled) {
          return
        }
        if (!response.ok || !response.data) {
          setSteps([])
          setSelectedStepId(null)
          setError(response.errorMessage || 'Failed to load Pre results.')
          return
        }
        setSteps((response.data.steps || []).map(toStepViewRecord))
      })
      .finally(() => {
        if (!isCancelled) {
          setIsLoading(false)
        }
      })

    return () => {
      isCancelled = true
    }
  }, [documentId, showPreprocessor])

  useEffect(() => {
    setSelectedStepId((previous) => {
      if (previous && visibleSteps.some((step) => step.document_operation_id === previous)) {
        return previous
      }
      return visibleSteps[visibleSteps.length - 1]?.document_operation_id ?? null
    })
  }, [visibleSteps])

  useEffect(() => {
    if (!showPreprocessor || !documentId || !selectedStep) {
      setSurfaceMesh(null)
      setSurfaceError(null)
      setIsSurfaceLoading(false)
      return
    }

    let isCancelled = false
    setSurfaceMesh(null)
    setSurfaceError(null)
    setIsSurfaceLoading(true)

    apiClient
      .get<DocumentSimulationStepSurfaceResponse>(
        `/documents/${documentId}/simulation-steps/${selectedStep.document_operation_id}/surface`,
        { params: { max_outline_points: 128 } }
      )
      .then((response) => {
        if (isCancelled) {
          return
        }
        if (!response.ok || !response.data) {
          setSurfaceError(response.errorMessage || 'Failed to load surface mesh.')
          return
        }
        setSurfaceMesh(response.data)
      })
      .finally(() => {
        if (!isCancelled) {
          setIsSurfaceLoading(false)
        }
      })

    return () => {
      isCancelled = true
    }
  }, [documentId, selectedStep, showPreprocessor])

  if (!showPreprocessor && !showPostprocessor) {
    return null
  }

  return (
    <section
      data-document-activatable-block="true"
      className="my-3 rounded-2xl border border-[rgba(55,53,47,0.12)] bg-[#f8f7f4] p-3 shadow-sm"
    >
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="text-[12px] font-semibold text-[rgba(55,53,47,0.72)]">
          Inline results: {blockDisplayName(contextBlock)}
        </div>
        {hasUnsavedChanges ? (
          <div className="rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[10px] font-medium text-amber-700">
            Saved data only
          </div>
        ) : null}
      </div>

      {showPreprocessor ? (
        <div className="space-y-2">
          {visibleSteps.length > 1 ? (
            <div className="flex gap-1 overflow-x-auto pb-1">
              {visibleSteps.map((step) => {
                const isSelected = selectedStep?.document_operation_id === step.document_operation_id
                return (
                  <button
                    key={step.document_operation_id}
                    type="button"
                    onClick={() => setSelectedStepId(step.document_operation_id)}
                    className={`shrink-0 rounded-full border px-2 py-1 text-[10px] font-semibold transition ${
                      isSelected
                        ? 'border-[rgba(55,53,47,0.32)] bg-[rgba(55,53,47,0.86)] text-white'
                        : 'border-[rgba(55,53,47,0.12)] bg-white text-[rgba(55,53,47,0.62)] hover:bg-[rgba(55,53,47,0.04)]'
                    }`}
                    title={operationTitle(step)}
                  >
                    {step.execution_order}. {operationTitle(step)}
                  </button>
                )
              })}
            </div>
          ) : null}

          {isLoading ? (
            <div className="rounded-xl border border-[rgba(55,53,47,0.10)] bg-white px-3 py-5 text-center text-[12px] text-[rgba(55,53,47,0.48)]">
              Loading Pre results...
            </div>
          ) : error ? (
            <div className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
              {error}
            </div>
          ) : selectedStep ? (
            <div className="space-y-2 overflow-x-auto">
              <div className="min-w-[920px]">
                <StepGeometryPreviewGrid
                  step={selectedStep}
                  surfaceMesh={surfaceMesh}
                  isSurfaceLoading={isSurfaceLoading}
                  meshViewMode="overlay"
                />
              </div>
              <div className="flex flex-wrap items-center gap-2 text-[10px] text-[rgba(55,53,47,0.52)]">
                <span>Step {selectedStep.execution_order}</span>
                <span>{operationTitle(selectedStep)}</span>
                <span>Status: {statusLabel(selectedStep)}</span>
              </div>
              {surfaceError ? (
                <div className="rounded-lg border border-amber-200 bg-amber-50 px-2 py-1.5 text-[11px] text-amber-800">
                  {surfaceError}
                </div>
              ) : null}
            </div>
          ) : (
            <div className="rounded-xl border border-[rgba(55,53,47,0.10)] bg-white px-3 py-5 text-center text-[12px] text-[rgba(55,53,47,0.48)]">
              No Pre result rows for this block yet.
            </div>
          )}
        </div>
      ) : null}

      {showPostprocessor ? (
        <div className="mt-2 rounded-xl border border-[rgba(55,53,47,0.10)] bg-white px-3 py-3 text-[12px] text-[rgba(55,53,47,0.55)]">
          Postprocessor inline results are not available yet. This toggle reserves the document UI path for the later Post migration.
        </div>
      ) : null}
    </section>
  )
}
