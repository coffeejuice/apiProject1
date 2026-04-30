import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { BlockComponentProps } from './BlockRegistry'
import Tooltip from '../ui/Tooltip'

interface OperationTemplateField {
  path: string
  type?: string
  label?: string
  unit?: string | null
  default?: unknown
  options?: Array<{ value?: unknown; label?: unknown }>
}

interface SelectorNode {
  id: string
  label?: string
  value?: unknown
  template_id?: string
  children?: SelectorNode[]
}

interface OperationTypeSelector {
  tree?: SelectorNode[]
}

interface ParametersCalculationModeSelector {
  target_path?: string
  default?: unknown
  tree?: SelectorNode[]
}

interface OperationTemplate {
  id?: string
  version?: number
  label?: string
  display_name?: string
  category?: string
  operation_kind?: string
  compiler_handler?: string
  insertable?: boolean
  materialize?: boolean
  input_method?: string
  input_schema?: OperationTemplateField[]
  target_schema?: OperationTemplateField[]
}

interface RoundingTableRow {
  size?: string
  feed?: string
  angle?: string
  rotations_per_feed?: string
  speed?: string
}

const HEATING_BLOCK_TYPE_ID = 'heating'
const FURNACE_BLOCK_TYPE_ID = 'furnace'
const DEFORMATION_PROPERTIES = 'deformation_properties'
const HEATING_PROPERTIES = 'heating_properties'
const FURNACE_PROPERTIES = 'furnace_properties'
const OPERATION_PROPERTIES = 'operation_properties'
const STANDARD_RIGHT_ARROW = '→'
const RIGHT_ARROW_SYMBOLS = [
  '→', '↠', '↣', '↦', '↪', '↬', '⇀', '⇁', '⇉', '⇛', '⇝', '⇢',
  '⇨', '⇒', '⇾', '➔', '➙', '➜', '➝', '➞', '➟', '➠', '➡',
  '➢', '➣', '➤', '➥', '➦', '➧', '➨', '➩', '➪', '➫', '➬',
  '➭', '➮', '➯', '➱', '➲', '➳', '➵', '➸', '➺', '➻', '➼',
  '➽', '➾', '⟶', '⟴', '⟹', '⟼', '⟾', '⟿', '⤀', '⤏', '⤐',
  '⤳', '⥤', '⭢', '⮕',
]
const ROUNDING_TABLE_PATH = `${OPERATION_PROPERTIES}.rounding_table`
const ROUNDING_TABLE_COLUMNS: Array<{ key: keyof RoundingTableRow; label: string; minChars: number }> = [
  { key: 'size', label: 'Size', minChars: 4 },
  { key: 'feed', label: 'Feed, mm', minChars: 8 },
  { key: 'angle', label: 'Angle, °', minChars: 8 },
  { key: 'rotations_per_feed', label: 'Rotations\nper Feed', minChars: 9 },
  { key: 'speed', label: 'Speed, mm/s', minChars: 11 },
]

function maxVisualLineLength(value: string): number {
  return Math.max(...value.split('\n').map((line) => line.length))
}

function normalizeValue(value: unknown): string {
  return value === null || value === undefined ? '' : String(value)
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

const RIGHT_ARROW_PATTERN = new RegExp(`-->|->|${RIGHT_ARROW_SYMBOLS.map(escapeRegExp).join('|')}`, 'g')

function normalizeRightArrows(value: string): string {
  return value.replace(RIGHT_ARROW_PATTERN, STANDARD_RIGHT_ARROW)
}

function normalizeRightArrowsWithSelection(
  value: string,
  selectionStart: number,
  selectionEnd: number,
): { value: string; selectionStart: number; selectionEnd: number } {
  return {
    value: normalizeRightArrows(value),
    selectionStart: normalizeRightArrows(value.slice(0, selectionStart)).length,
    selectionEnd: normalizeRightArrows(value.slice(0, selectionEnd)).length,
  }
}

function emptyRoundingRow(): RoundingTableRow {
  return {
    size: '',
    feed: '',
    angle: '',
    rotations_per_feed: '',
    speed: '',
  }
}

function normalizeRoundingRows(value: unknown): RoundingTableRow[] {
  if (!Array.isArray(value)) {
    return []
  }
  return value
    .filter((entry): entry is Record<string, unknown> => Boolean(entry && typeof entry === 'object'))
    .map((entry) => ({
      size: normalizeValue(entry.size),
      feed: normalizeValue(entry.feed),
      angle: normalizeValue(entry.angle),
      rotations_per_feed: normalizeValue(entry.rotations_per_feed),
      speed: normalizeValue(entry.speed),
    }))
}

function rowsForDisplay(rows: RoundingTableRow[]): RoundingTableRow[] {
  return rows.length > 0 ? rows : [emptyRoundingRow()]
}

function stringifyJson(value: unknown): string {
  return JSON.stringify(value ?? null)
}

function asSelectorNodes(value: unknown): SelectorNode[] {
  return Array.isArray(value) ? value.filter((entry): entry is SelectorNode => Boolean(entry && typeof entry === 'object')) : []
}

function getOperationTemplate(props: Record<string, unknown> | undefined): OperationTemplate {
  const current = props?.operation_template
  if (current && typeof current === 'object') {
    return current as OperationTemplate
  }
  const snapshot = props?.template_snapshot
  return snapshot && typeof snapshot === 'object' ? snapshot as OperationTemplate : {}
}

function getAvailableTemplates(props: Record<string, unknown> | undefined): OperationTemplate[] {
  const templates = props?.operation_templates
  return Array.isArray(templates)
    ? templates.filter((entry): entry is OperationTemplate => Boolean(entry && typeof entry === 'object'))
    : []
}

function getNestedValue(source: Record<string, unknown>, dottedPath: string): unknown {
  const parts = dottedPath.split('.').filter(Boolean)
  let cursor: unknown = source
  for (const part of parts) {
    if (!cursor || typeof cursor !== 'object' || !(part in cursor)) {
      return undefined
    }
    cursor = (cursor as Record<string, unknown>)[part]
  }
  return cursor
}

function getOperationTemplateId(props: Record<string, unknown> | undefined): string {
  const rawProps = props || {}
  const operationProperties = rawProps[OPERATION_PROPERTIES]
  const namespaced =
    operationProperties && typeof operationProperties === 'object'
      ? (operationProperties as Record<string, unknown>).operation_template_id
      : undefined
  return normalizeValue(rawProps.operation_template_id ?? namespaced)
}

function isConcreteOperationTemplateId(templateId: string): boolean {
  return Boolean(templateId && templateId !== 'operation.empty')
}

function setNestedValue(source: Record<string, unknown>, dottedPath: string, value: unknown): Record<string, unknown> {
  const parts = dottedPath.split('.').filter(Boolean)
  if (parts.length === 0) {
    return { ...source }
  }

  const result = JSON.parse(JSON.stringify(source || {})) as Record<string, unknown>
  let cursor = result
  parts.slice(0, -1).forEach((part) => {
    const existing = cursor[part]
    if (!existing || typeof existing !== 'object' || Array.isArray(existing)) {
      cursor[part] = {}
    }
    cursor = cursor[part] as Record<string, unknown>
  })
  cursor[parts[parts.length - 1]] = value
  return result
}

function setTargetDefault(target: Record<string, unknown>, path: string, value: unknown) {
  if (!path.startsWith('target.')) {
    return
  }
  const nested = setNestedValue({ target }, path, value)
  const nextTarget = nested.target
  if (nextTarget && typeof nextTarget === 'object') {
    Object.assign(target, nextTarget)
  }
}

function findPathByTemplateId(nodes: SelectorNode[], templateId: string): SelectorNode[] {
  for (const node of nodes) {
    if (node.template_id === templateId) {
      return [node]
    }
    const childPath = findPathByTemplateId(asSelectorNodes(node.children), templateId)
    if (childPath.length > 0) {
      return [node, ...childPath]
    }
  }
  return []
}

function findPathByValue(nodes: SelectorNode[], value: string): SelectorNode[] {
  for (const node of nodes) {
    if (normalizeValue(node.value) === value) {
      return [node]
    }
    const childPath = findPathByValue(asSelectorNodes(node.children), value)
    if (childPath.length > 0) {
      return [node, ...childPath]
    }
  }
  return []
}

function findFirstLeafValue(node: SelectorNode): unknown {
  const children = asSelectorNodes(node.children)
  if (children.length === 0) {
    return node.value
  }
  return findFirstLeafValue(children[0])
}

function getColumns(tree: SelectorNode[], path: SelectorNode[]): SelectorNode[][] {
  const columns: SelectorNode[][] = [tree]
  for (const node of path) {
    const children = asSelectorNodes(node.children)
    if (children.length > 0) {
      columns.push(children)
    }
  }
  return columns
}

function buildTargetDefaults(
  template: OperationTemplate,
  calculationSelector: ParametersCalculationModeSelector,
  previousTarget: unknown
): Record<string, unknown> {
  const target: Record<string, unknown> = {}
  const calculationPath = calculationSelector.target_path || 'target.parameters_calculation_mode'
  const previousCalculationMode =
    previousTarget && typeof previousTarget === 'object'
      ? (previousTarget as Record<string, unknown>).parameters_calculation_mode
      : undefined
  setTargetDefault(target, calculationPath, previousCalculationMode ?? calculationSelector.default ?? 'manual')

  for (const field of template.target_schema || []) {
    if (field.path === calculationPath) {
      continue
    }
    setTargetDefault(target, field.path, field.default ?? '')
  }
  return target
}

function renderResetButton(onClick: () => void, isDirty: boolean) {
  if (!isDirty) {
    return null
  }

  return (
    <Tooltip content="Revert this parameter">
      <button
        type="button"
        onClick={onClick}
        className="doc-reset"
        aria-label="Revert this parameter"
      >
        ↺
      </button>
    </Tooltip>
  )
}

export default function OperationBlock({
  block,
  baselineProps,
  isActive,
  saveStatus,
  sectionNumber,
  onUpdate,
}: BlockComponentProps) {
  const props = block.props || {}
  const operationTextPath = `${OPERATION_PROPERTIES}.operation_text`
  const operationTextValue = normalizeValue(getNestedValue(props, operationTextPath) ?? props.operation_text)
  const roundingRows = normalizeRoundingRows(getNestedValue(props, ROUNDING_TABLE_PATH) ?? props.rounding_table)
  const baselineRoundingRows = normalizeRoundingRows(
    getNestedValue(baselineProps || {}, ROUNDING_TABLE_PATH) ?? baselineProps?.rounding_table
  )
  const template = getOperationTemplate(props)
  const availableTemplates = getAvailableTemplates(props)
  const targetSchema = template.target_schema || []
  const currentTemplateId = getOperationTemplateId(props)
  const baselineTemplateId = getOperationTemplateId(baselineProps)
  const hasSelectedOperationType = isConcreteOperationTemplateId(currentTemplateId)
  const hasSavedOperationType = isConcreteOperationTemplateId(baselineTemplateId)
  const hasUnsavedOperationTypeChange = currentTemplateId !== baselineTemplateId
  const [operationPathIds, setOperationPathIds] = useState<string[]>([])
  const [isOperationSelectorOpen, setIsOperationSelectorOpen] = useState(false)
  const operationTextareaRef = useRef<HTMLTextAreaElement | null>(null)
  const operationTextSelectionRef = useRef<{ start: number; end: number } | null>(null)
  const operationTypeSelector = (props.operation_type_selector || {}) as OperationTypeSelector
  const calculationSelector = (props.parameters_calculation_mode_selector || {}) as ParametersCalculationModeSelector
  const operationTree = asSelectorNodes(operationTypeSelector.tree)
  const calculationTree = asSelectorNodes(calculationSelector.tree)
  const calculationPath = calculationSelector.target_path || 'target.parameters_calculation_mode'

  const operationPath = useMemo(() => {
    if (operationPathIds.length > 0) {
      let currentColumn = operationTree
      const path: SelectorNode[] = []
      for (const id of operationPathIds) {
        const node = currentColumn.find((entry) => entry.id === id)
        if (!node) {
          break
        }
        path.push(node)
        currentColumn = asSelectorNodes(node.children)
      }
      return path
    }
    return hasSelectedOperationType ? findPathByTemplateId(operationTree, currentTemplateId) : []
  }, [currentTemplateId, hasSelectedOperationType, operationPathIds, operationTree])
  const savedOperationPath = useMemo(
    () => hasSavedOperationType ? findPathByTemplateId(operationTree, baselineTemplateId) : [],
    [baselineTemplateId, hasSavedOperationType, operationTree]
  )

  const calculationValue = normalizeValue(getNestedValue(props, calculationPath) ?? calculationSelector.default ?? 'manual')
  const calculationPathNodes = useMemo(
    () => findPathByValue(calculationTree, calculationValue),
    [calculationTree, calculationValue]
  )
  const calculationModeDefault = normalizeValue(calculationSelector.default ?? 'manual')
  const calculationModeNode =
    calculationPathNodes.length > 0 ? calculationPathNodes[calculationPathNodes.length - 1] : undefined
  const calculationModeLabel = normalizeValue(
    calculationModeNode?.label ?? calculationModeNode?.value ?? calculationValue
  )
  const titleCalculationMode =
    calculationValue && calculationValue !== calculationModeDefault
      ? calculationValue === 'optimization'
        ? 'OPT'
        : calculationModeLabel.toUpperCase()
      : ''

  const operationTitle = hasSelectedOperationType
    ? template.display_name || template.label || currentTemplateId
    : 'Empty operation'
  const shouldShowOperationTypeSelector =
    !hasSavedOperationType || isOperationSelectorOpen || hasUnsavedOperationTypeChange
  const usesRoundingTable = template.input_method === 'rounding_table' || currentTemplateId === 'operation.rounding'

  useEffect(() => {
    setOperationPathIds([])
  }, [currentTemplateId])

  useEffect(() => {
    if (!isActive && hasSavedOperationType) {
      setIsOperationSelectorOpen(false)
    }
  }, [hasSavedOperationType, isActive])

  useEffect(() => {
    if (saveStatus === 'saved' && hasSavedOperationType) {
      setIsOperationSelectorOpen(false)
    }
  }, [hasSavedOperationType, saveStatus])

  useLayoutEffect(() => {
    const selection = operationTextSelectionRef.current
    const textarea = operationTextareaRef.current
    if (!selection || !textarea || document.activeElement !== textarea) {
      return
    }

    const start = Math.min(selection.start, operationTextValue.length)
    const end = Math.min(selection.end, operationTextValue.length)
    textarea.setSelectionRange(start, end)
    operationTextSelectionRef.current = null
  }, [operationTextValue])

  const updatePath = (path: string, value: unknown) => {
    onUpdate(block.block_id, setNestedValue(props, path, value))
  }

  const resetPath = (path: string) => {
    updatePath(path, getNestedValue(baselineProps || {}, path) ?? '')
  }

  const isPathDirty = (path: string) =>
    normalizeValue(getNestedValue(props, path)) !== normalizeValue(getNestedValue(baselineProps || {}, path))

  if (block.block_type_id === 'deformation') {
    const renderDeformationVariableField = (field: string, label: string, unit: string) => {
      const path = `${DEFORMATION_PROPERTIES}.deformation_variables.${field}`
      const value = normalizeValue(getNestedValue(props, path))
      const dirty = isPathDirty(path)

      return (
        <tr key={field} className="doc-table-row">
          <td className="doc-label">
            {label}
            <span className="ml-1 doc-muted">[{unit}]</span>
          </td>
          <td className="doc-value">
            <div className="doc-field-row">
              <input
                type="number"
                value={value}
                onChange={(event) => updatePath(path, event.target.value)}
                className={`doc-field ${dirty ? 'doc-field-dirty' : ''}`}
                step="0.001"
                placeholder={label}
              />
              {renderResetButton(() => resetPath(path), dirty)}
            </div>
          </td>
        </tr>
      )
    }

    return (
      <div className="doc-content">
        <h2 className="doc-title doc-title-parent">
          {sectionNumber ? `${sectionNumber} ` : ''}
          Deformation
        </h2>
        <table className="doc-table">
          <tbody>
            {renderDeformationVariableField('tail_chamfering_stroke', 'Tail chamfering stroke', 'mm')}
            {renderDeformationVariableField('tail_flattening_stroke', 'Tail flattening stroke', 'mm')}
            {renderDeformationVariableField('radial_feed', 'Radial feed', 'mm')}
          </tbody>
        </table>
      </div>
    )
  }

  if (block.block_type_id === HEATING_BLOCK_TYPE_ID || block.block_type_id === FURNACE_BLOCK_TYPE_ID) {
    const namespace = block.block_type_id === HEATING_BLOCK_TYPE_ID ? HEATING_PROPERTIES : FURNACE_PROPERTIES
    const title = block.block_type_id === HEATING_BLOCK_TYPE_ID ? 'Heating' : 'Furnace'
    const renderHeatingField = (field: string, label: string) => {
      const path = `${namespace}.${field}`
      const value = normalizeValue(getNestedValue(props, path) ?? props[field])
      const dirty = normalizeValue(getNestedValue(props, path) ?? props[field]) !==
        normalizeValue(getNestedValue(baselineProps || {}, path) ?? baselineProps?.[field])
      return (
        <tr key={field} className="doc-table-row">
          <td className="doc-label">{label}</td>
          <td className="doc-value">
            <div className="doc-field-row">
              <input
                type="text"
                value={value}
                onChange={(event) => updatePath(path, event.target.value)}
                className={`doc-field ${dirty ? 'doc-field-dirty' : ''}`}
                placeholder={label}
              />
              {renderResetButton(() => resetPath(path), dirty)}
            </div>
          </td>
        </tr>
      )
    }

    return (
      <div className="doc-content">
        <h2 className={`doc-title ${
          block.block_type_id === HEATING_BLOCK_TYPE_ID ? 'doc-title-parent' : 'doc-title-child'
        }`}>
          {sectionNumber ? `${sectionNumber} ` : ''}
          {title}
        </h2>
        <table className="doc-table">
          <tbody>
            {renderHeatingField('furnace_class_id', 'Furnace class')}
            {renderHeatingField('temperature', 'Temperature')}
          </tbody>
        </table>
      </div>
    )
  }

  const selectOperationTemplate = (templateId: string) => {
    const nextTemplate = availableTemplates.find((entry) => entry.id === templateId)
    if (!nextTemplate) {
      return
    }

    const nextTarget = buildTargetDefaults(nextTemplate, calculationSelector, props.target)
    const nextRoundingTable =
      nextTemplate.input_method === 'rounding_table' && roundingRows.length === 0
        ? [emptyRoundingRow()]
        : roundingRows
    onUpdate(block.block_id, {
      ...props,
      operation_template_id: nextTemplate.id,
      operation_template_version: nextTemplate.version,
      operation_kind: nextTemplate.operation_kind,
      rounding_table: nextRoundingTable,
      target: nextTarget,
      template_snapshot: nextTemplate,
      operation_template: nextTemplate,
      title: nextTemplate.display_name || nextTemplate.label || nextTemplate.id,
    })
    setOperationPathIds(findPathByTemplateId(operationTree, templateId).map((node) => node.id))
  }

  const renderSelectorRow = (
    columns: SelectorNode[][],
    selectedPathIds: string[],
    onSelect: (node: SelectorNode, depth: number) => void,
    wrap = false,
    isDirty = false,
    savedPathIds: string[] = [],
    compact = false
  ) => (
    <div className={`flex items-center gap-1 ${compact ? '' : 'pb-1'} ${wrap ? 'flex-wrap' : 'overflow-x-auto'}`}>
      {columns.map((column, depth) => (
        <div key={`row-${depth}`} className={`flex items-center gap-1 ${wrap ? 'flex-wrap' : 'shrink-0'}`}>
          {depth > 0 ? <span className="doc-muted px-1">/</span> : null}
          {column.map((node) => {
            const selected = selectedPathIds[depth] === node.id
            const saved = savedPathIds[depth] === node.id
            return (
              <button
                key={node.id}
                type="button"
                onClick={() => onSelect(node, depth)}
                className={[
                  'doc-selector-button',
                  saved && !selected ? 'doc-selector-button-saved' : '',
                  selected ? 'doc-selector-button-selected' : '',
                  selected && isDirty ? 'doc-selector-button-dirty' : '',
                ].filter(Boolean).join(' ')}
              >
                {node.label || node.id}
              </button>
            )
          })}
        </div>
      ))}
    </div>
  )

  const renderOperationTypeArea = () => {
    return (
      <section className="doc-section mt-0">
        {operationTree.length === 0 ? (
          <div className="doc-readonly">Operation type selector is not defined.</div>
        ) : (
          renderSelectorRow(
            getColumns(operationTree, operationPath),
            operationPath.map((node) => node.id),
            (node, depth) => {
              const children = asSelectorNodes(node.children)
              setOperationPathIds([...operationPath.slice(0, depth).map((entry) => entry.id), node.id])
              if (children.length === 0 && node.template_id) {
                selectOperationTemplate(node.template_id)
              }
            },
            true,
            hasUnsavedOperationTypeChange,
            savedOperationPath.map((node) => node.id)
          )
        )}
      </section>
    )
  }

  const renderCalculationModeSelector = () => {
    if (calculationTree.length === 0) {
      return null
    }

    return (
      <div
        className="doc-title-mode-controls"
        onClick={(event) => event.stopPropagation()}
        onDoubleClick={(event) => event.stopPropagation()}
      >
        {renderSelectorRow(
          getColumns(calculationTree, calculationPathNodes),
          calculationPathNodes.map((node) => node.id),
          (node) => {
            const value = asSelectorNodes(node.children).length > 0 ? findFirstLeafValue(node) : node.value
            updatePath(calculationPath, value ?? calculationSelector.default ?? 'manual')
          },
          false,
          isPathDirty(calculationPath),
          [],
          true
        )}
      </div>
    )
  }

  const renderOperationTextArea = () => {
    const dirty =
      operationTextValue !== normalizeValue(getNestedValue(baselineProps || {}, operationTextPath) ?? baselineProps?.operation_text)
    const rowCount = Math.max(1, operationTextValue.split(/\r\n|\r|\n/).length)

    return (
      <section className="doc-section">
        <div className="doc-field-row">
          <textarea
            ref={operationTextareaRef}
            value={operationTextValue}
            onChange={(event) => {
              const normalized = normalizeRightArrowsWithSelection(
                event.target.value,
                event.target.selectionStart,
                event.target.selectionEnd,
              )
              operationTextSelectionRef.current = {
                start: normalized.selectionStart,
                end: normalized.selectionEnd,
              }
              updatePath(operationTextPath, normalized.value)
            }}
            className={`doc-textarea ${dirty ? 'doc-field-dirty' : ''}`}
            placeholder={`Use ${STANDARD_RIGHT_ARROW} between operations. Line breaks and spacing are visual only.`}
            rows={rowCount}
          />
          {renderResetButton(
            () => updatePath(operationTextPath, getNestedValue(baselineProps || {}, operationTextPath) ?? baselineProps?.operation_text ?? ''),
            dirty
          )}
        </div>
      </section>
    )
  }

  const renderRoundingTable = () => {
    const displayRows = rowsForDisplay(roundingRows)
    const baselineDisplayRows = rowsForDisplay(baselineRoundingRows)
    const columnWidths = ROUNDING_TABLE_COLUMNS.map((column) =>
      Math.max(
        column.minChars,
        maxVisualLineLength(column.label) + 1,
        Math.max(1, ...displayRows.map((row) => normalizeValue(row[column.key]).length)) + 2,
      )
    )
    const dirty = stringifyJson(roundingRows) !== stringifyJson(baselineRoundingRows)

    const updateRows = (nextRows: RoundingTableRow[]) => {
      updatePath(ROUNDING_TABLE_PATH, rowsForDisplay(nextRows))
    }

    const updateCell = (rowIndex: number, key: keyof RoundingTableRow, value: string) => {
      const nextRows = displayRows.map((row) => ({ ...row }))
      nextRows[rowIndex] = {
        ...nextRows[rowIndex],
        [key]: value,
      }
      updateRows(nextRows)
    }

    const insertRow = (rowIndex: number, offset: 0 | 1) => {
      const nextRows = displayRows.map((row) => ({ ...row }))
      nextRows.splice(rowIndex + offset, 0, emptyRoundingRow())
      updateRows(nextRows)
    }

    const removeRow = (rowIndex: number) => {
      const nextRows = displayRows.filter((_, index) => index !== rowIndex)
      updateRows(nextRows.length > 0 ? nextRows : [emptyRoundingRow()])
    }

    return (
      <section className="doc-section">
        <div className="doc-field-row">
          <div className="doc-operation-table-wrap">
            <table className="doc-operation-table">
              <colgroup>
                <col className="doc-operation-pass-col" />
                {ROUNDING_TABLE_COLUMNS.map((column, columnIndex) => (
                  <col key={column.key} style={{ width: `${columnWidths[columnIndex]}ch` }} />
                ))}
                <col className="doc-operation-actions-col" />
              </colgroup>
              <thead>
                <tr>
                  <th>Pass</th>
                  {ROUNDING_TABLE_COLUMNS.map((column) => (
                    <th key={column.key}>{column.label}</th>
                  ))}
                  <th className="doc-operation-actions-header" aria-label="Row actions" />
                </tr>
              </thead>
              <tbody>
                {displayRows.map((row, rowIndex) => (
                  <tr key={rowIndex}>
                    <td className="doc-operation-pass">{rowIndex + 1}</td>
                    {ROUNDING_TABLE_COLUMNS.map((column) => (
                      <td key={column.key}>
                        <input
                          type="text"
                          value={normalizeValue(row[column.key])}
                          onChange={(event) => updateCell(rowIndex, column.key, event.target.value)}
                          className={`doc-field ${
                            normalizeValue(row[column.key]) !== normalizeValue(baselineDisplayRows[rowIndex]?.[column.key])
                              ? 'doc-field-dirty'
                              : ''
                          }`}
                        />
                      </td>
                    ))}
                    <td className="doc-operation-actions-cell">
                      <div className="doc-table-actions">
                        <button type="button" onClick={() => insertRow(rowIndex, 0)} aria-label="Insert row above">
                          ↑+
                        </button>
                        <button type="button" onClick={() => insertRow(rowIndex, 1)} aria-label="Insert row below">
                          ↓+
                        </button>
                        <button type="button" onClick={() => removeRow(rowIndex)} aria-label="Remove row">
                          ×
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {renderResetButton(() => updatePath(ROUNDING_TABLE_PATH, baselineRoundingRows), dirty)}
        </div>
      </section>
    )
  }

  const renderTemplateField = (field: OperationTemplateField) => {
    const path = field.path
    if (path === calculationPath) {
      return null
    }
    const label = field.label || path
    const currentValue = normalizeValue(getNestedValue(props, path))
    const dirty = isPathDirty(path)
    const options = field.options || []
    const inputType = field.type === 'decimal' || field.type === 'integer' ? 'number' : 'text'

    return (
      <tr key={path} className="doc-table-row">
        <td className="doc-label">
          {label}
          {field.unit ? <span className="ml-1 doc-muted">[{field.unit}]</span> : null}
        </td>
        <td className="doc-value">
          <div className="doc-field-row">
            {options.length > 0 ? (
              <select
                value={currentValue}
                onChange={(event) => updatePath(path, event.target.value)}
                className={`doc-select ${dirty ? 'doc-field-dirty' : ''}`}
              >
                {options.map((option) => (
                  <option key={normalizeValue(option.value)} value={normalizeValue(option.value)}>
                    {normalizeValue(option.label || option.value)}
                  </option>
                ))}
              </select>
            ) : (
              <input
                type={inputType}
                value={currentValue}
                onChange={(event) => updatePath(path, event.target.value)}
                className={`doc-field ${dirty ? 'doc-field-dirty' : ''}`}
                placeholder={label}
                step={field.type === 'integer' ? 1 : undefined}
              />
            )}
            {renderResetButton(() => resetPath(path), dirty)}
          </div>
        </td>
      </tr>
    )
  }

  const renderedTemplateFields = targetSchema.map(renderTemplateField).filter(Boolean)

  return (
    <div className="doc-content">
      <div className="doc-title-row">
        <h2
          className="doc-title doc-title-child cursor-pointer select-none"
          onDoubleClick={(event) => {
            event.stopPropagation()
            setIsOperationSelectorOpen(true)
          }}
        >
          {sectionNumber ? `${sectionNumber} ` : ''}
          {operationTitle}
          {titleCalculationMode ? (
            <span className="doc-title-mode-label">{titleCalculationMode}</span>
          ) : null}
        </h2>
        {renderCalculationModeSelector()}
      </div>

      {shouldShowOperationTypeSelector ? renderOperationTypeArea() : null}
      {hasSelectedOperationType ? (usesRoundingTable ? renderRoundingTable() : renderOperationTextArea()) : null}

      {hasSelectedOperationType && renderedTemplateFields.length > 0 ? (
        <section className="doc-section">
          <table className="doc-table">
            <tbody>{renderedTemplateFields}</tbody>
          </table>
        </section>
      ) : null}
    </div>
  )
}
