import type { BlockComponentProps } from './BlockRegistry'
import Tooltip from '../ui/Tooltip'

interface OperationTypeMetadata {
  type_id?: number
  library_name?: string
  process_name?: string
  labels?: string[]
  db_column_names?: string[]
  field_options?: Record<string, OperationFieldOption[]>
}

interface OperationFieldOption {
  value: string | number
  label: string
}

const DEFORMATION_TYPE_ID = 24
const DIE_TYPE_ID = 8
const UPSETTING_FEED_SPEED_TYPE_ID = 13
const PROLONGATION_FEED_SPEED_TYPE_ID = 15
const TRANSVERSAL_FEED_SPEED_TYPE_ID = 14
const FEED_DIRECTION_DEFAULT_VALUE = '3'
const FEED_DIRECTION_OPTIONS: OperationFieldOption[] = [
  { value: '3', label: '<--' },
  { value: '4', label: '<->' },
  { value: '2', label: '-->' },
]
const TITLE_ONLY_TYPE_IDS = new Set([String(DIE_TYPE_ID)])
const FEED_SPEED_BLOCK_CONFIGS = {
  [String(UPSETTING_FEED_SPEED_TYPE_ID)]: {
    directionField: 'feed_direction_upsetting_id',
    speedField: 'speed_upsetting',
    feedLengthFields: [],
  },
  [String(PROLONGATION_FEED_SPEED_TYPE_ID)]: {
    directionField: 'feed_direction_prolongation_id',
    speedField: 'speed_prolongation',
    feedLengthFields: ['feed_first', 'feed_middle', 'feed_last'],
  },
  [String(TRANSVERSAL_FEED_SPEED_TYPE_ID)]: {
    directionField: 'feed_direction_transversal_cogging_id',
    speedField: 'speed_transversal_cogging',
    feedLengthFields: [],
  },
} as const

type FeedSpeedBlockConfig =
  (typeof FEED_SPEED_BLOCK_CONFIGS)[keyof typeof FEED_SPEED_BLOCK_CONFIGS]

const DEFORMATION_FEED_SPEED_ROWS: { label: string; config: FeedSpeedBlockConfig }[] = [
  { label: 'Prolongation:', config: FEED_SPEED_BLOCK_CONFIGS[String(PROLONGATION_FEED_SPEED_TYPE_ID)] },
  { label: 'Upsetting:', config: FEED_SPEED_BLOCK_CONFIGS[String(UPSETTING_FEED_SPEED_TYPE_ID)] },
  { label: 'Transversal cogging:', config: FEED_SPEED_BLOCK_CONFIGS[String(TRANSVERSAL_FEED_SPEED_TYPE_ID)] },
]

function normalizeValue(value: unknown): string {
  return value === null || value === undefined ? '' : String(value)
}

function getOperationMetadata(props: Record<string, unknown> | undefined): OperationTypeMetadata {
  const metadata = props?.operation_type
  return metadata && typeof metadata === 'object' ? metadata as OperationTypeMetadata : {}
}

function renderResetButton(onClick: () => void, isReadOnly: boolean, isDirty: boolean) {
  if (isReadOnly || !isDirty) {
    return null
  }

  return (
    <Tooltip content="Revert this parameter">
      <button
        type="button"
        onClick={onClick}
        className="ui-btn-danger h-8 w-8 p-0 flex-shrink-0"
        aria-label="Revert this parameter"
      >
        ↺
      </button>
    </Tooltip>
  )
}

function renderOptionButtons(
  field: string,
  label: string,
  options: OperationFieldOption[],
  selectedValue: string,
  isDirty: boolean,
  updateField: (field: string, value: string) => void,
) {
  return (
    <div
      className={`flex flex-wrap gap-1.5 rounded-md border p-1 ${
        isDirty ? 'border-red-300 bg-red-50' : 'border-gray-200 bg-gray-50'
      }`}
      role="radiogroup"
      aria-label={label}
    >
      {options.map((option) => {
        const optionValue = normalizeValue(option.value)
        const selected = optionValue === selectedValue

        return (
          <button
            key={optionValue}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => updateField(field, optionValue)}
            className={`rounded px-2.5 py-1 text-xs font-semibold transition ${
              selected
                ? 'border border-gray-900 bg-gray-900 text-white shadow-sm'
                : 'border border-gray-200 bg-white text-gray-700 hover:border-gray-400 hover:bg-gray-100'
            }`}
          >
            {option.label}
          </button>
        )
      })}
    </div>
  )
}

export default function OperationBlock({
  block,
  baselineProps,
  onUpdate,
  isReadOnly = false,
}: BlockComponentProps) {
  const metadata = getOperationMetadata(block.props)
  const columns = metadata.db_column_names || block.editable_fields || []
  const labels = metadata.labels || []
  const fieldOptions = metadata.field_options || {}
  const title = normalizeValue(block.props?.title) || metadata.library_name || `Operation ${block.block_type_id}`
  const operationTypeId = normalizeValue(metadata.type_id || block.block_type_id)
  const isMergedDeformationBlock = operationTypeId === String(DEFORMATION_TYPE_ID)
  const isTitleOnlyBlock = TITLE_ONLY_TYPE_IDS.has(operationTypeId)
  const feedSpeedConfig =
    FEED_SPEED_BLOCK_CONFIGS[operationTypeId as keyof typeof FEED_SPEED_BLOCK_CONFIGS]

  const updateField = (field: string, value: string) => {
    onUpdate(block.block_id, {
      ...(block.props || {}),
      [field]: value,
    })
  }

  const resetField = (field: string) => {
    updateField(field, normalizeValue(baselineProps?.[field]))
  }

  const isFieldDirty = (field: string) =>
    normalizeValue(block.props?.[field]) !== normalizeValue(baselineProps?.[field])

  const fieldLabel = (field: string) => {
    const index = columns.indexOf(field)
    return index >= 0 ? labels[index] || field : field
  }

  const renderFieldRow = (columnName: string) => {
    const label = fieldLabel(columnName)
    const currentValue = normalizeValue(block.props?.[columnName])
    const options = fieldOptions[columnName] || []
    const selectedValue = currentValue || normalizeValue(options[0]?.value)
    const selectedLabel = options.find((option) => normalizeValue(option.value) === selectedValue)?.label
    const dirty = isFieldDirty(columnName)

    return (
      <tr key={columnName} className="border-b last:border-b-0">
        <td className="py-1 px-2 font-semibold bg-gray-50 w-1/2">{label}</td>
        <td className="py-1 px-2">
          {isReadOnly ? (
            <div className="ui-field-readonly">{selectedLabel || currentValue || '-'}</div>
          ) : (
            <div className="flex items-start gap-2">
              {options.length > 0 ? (
                renderOptionButtons(
                  columnName,
                  label,
                  options,
                  selectedValue,
                  dirty,
                  updateField,
                )
              ) : (
                <input
                  type="text"
                  value={currentValue}
                  onChange={(event) => updateField(columnName, event.target.value)}
                  className={`ui-input ${dirty ? 'border-red-300 bg-red-50' : 'border-gray-300'}`}
                  placeholder={label}
                />
              )}
              {renderResetButton(() => resetField(columnName), isReadOnly, dirty)}
            </div>
          )}
        </td>
      </tr>
    )
  }

  const renderFeedSpeedRow = (config: FeedSpeedBlockConfig, rowLabel?: string) => {
    const directionValue =
      normalizeValue(block.props?.[config.directionField]) || FEED_DIRECTION_DEFAULT_VALUE
    const directionLabel =
      FEED_DIRECTION_OPTIONS.find((option) => normalizeValue(option.value) === directionValue)?.label ||
      directionValue
    const directionDirty = isFieldDirty(config.directionField)
    const speedValue = normalizeValue(block.props?.[config.speedField])
    const speedDirty = isFieldDirty(config.speedField)

    return (
      <tr key={`${config.directionField}-${config.speedField}`} className="border-b last:border-b-0">
        {rowLabel ? (
          <td className="py-1 px-2 font-semibold bg-gray-50 w-1/3">{rowLabel}</td>
        ) : null}
        <td className="py-1 px-2" colSpan={rowLabel ? 1 : 2}>
          {isReadOnly ? (
            <div className="flex flex-wrap items-center gap-2">
              <div className="ui-field-readonly min-w-16 text-center">{directionLabel}</div>
              <div className="ui-field-readonly min-w-24">{speedValue || '-'}</div>
              <span className="text-xs text-gray-500">mm/s</span>
            </div>
          ) : (
            <div className="flex flex-wrap items-start gap-2">
              {renderOptionButtons(
                config.directionField,
                'Feed direction',
                FEED_DIRECTION_OPTIONS,
                directionValue,
                directionDirty,
                updateField,
              )}
              <input
                type="text"
                value={speedValue}
                onChange={(event) => updateField(config.speedField, event.target.value)}
                className={`ui-input max-w-40 ${
                  speedDirty ? 'border-red-300 bg-red-50' : 'border-gray-300'
                }`}
                placeholder="Speed"
              />
              <span className="self-center text-xs text-gray-500">mm/s</span>
              {renderResetButton(() => resetField(config.directionField), isReadOnly, directionDirty)}
              {renderResetButton(() => resetField(config.speedField), isReadOnly, speedDirty)}
            </div>
          )}
        </td>
      </tr>
    )
  }

  const renderFeedLengthRow = (fields: readonly string[]) => {
    if (fields.length === 0) {
      return null
    }

    return (
      <tr key="feed-lengths" className="border-b last:border-b-0">
        <td className="py-1 px-2 font-semibold bg-gray-50 w-1/3">
          First, Middle, Last feed length [mm]:
        </td>
        <td className="py-1 px-2">
          <div className="flex flex-wrap items-start gap-2">
            {fields.map((field, index) => {
              const value = normalizeValue(block.props?.[field])
              const dirty = isFieldDirty(field)
              const placeholder = ['First', 'Middle', 'Last'][index] || field

              if (isReadOnly) {
                return (
                  <div key={field} className="ui-field-readonly min-w-20">
                    {value || '-'}
                  </div>
                )
              }

              return (
                <div key={field} className="flex items-start gap-1">
                  <input
                    type="text"
                    value={value}
                    onChange={(event) => updateField(field, event.target.value)}
                    className={`ui-input max-w-24 ${dirty ? 'border-red-300 bg-red-50' : 'border-gray-300'}`}
                    placeholder={placeholder}
                  />
                  {renderResetButton(() => resetField(field), isReadOnly, dirty)}
                </div>
              )
            })}
          </div>
        </td>
      </tr>
    )
  }

  const renderFeedSpeedFields = (config: FeedSpeedBlockConfig) => {
    const handledFields = new Set<string>([
      config.directionField,
      config.speedField,
      ...config.feedLengthFields,
    ])
    const remainingFields = columns.filter((field) => !handledFields.has(field))

    return (
      <table className="w-full border-collapse">
        <tbody>
          {renderFeedSpeedRow(config)}
          {renderFeedLengthRow(config.feedLengthFields.filter((field) => columns.includes(field)))}
          {remainingFields.map(renderFieldRow)}
        </tbody>
      </table>
    )
  }

  const renderMergedDeformationFields = () => {
    const handledFields = new Set<string>([
      'press_id',
      'feed_direction_prolongation_id',
      'speed_prolongation',
      'feed_direction_upsetting_id',
      'speed_upsetting',
      'feed_direction_transversal_cogging_id',
      'speed_transversal_cogging',
      'feed_first',
      'feed_middle',
      'feed_last',
    ])
    const remainingFields = columns.filter((field) => !handledFields.has(field))

    return (
      <div className="grid gap-3">
        <div className="ui-card ui-card-body text-sm">
          <h3 className="mb-3 text-sm font-bold text-gray-900">Press</h3>
          <table className="w-full border-collapse">
            <tbody>
              {columns.includes('press_id') ? renderFieldRow('press_id') : null}
            </tbody>
          </table>
        </div>

        <div className="ui-card ui-card-body text-sm">
          <h3 className="mb-2 text-sm font-bold text-gray-900">Die</h3>
          <div className="ui-field-readonly">Die properties are not defined yet.</div>
        </div>

        <div className="ui-card ui-card-body text-sm">
          <h3 className="mb-3 text-sm font-bold text-gray-900">
            Feed direction and working speed [mm/s]
          </h3>
          <table className="w-full border-collapse">
            <tbody>
              {DEFORMATION_FEED_SPEED_ROWS.map((row) =>
                renderFeedSpeedRow(row.config, row.label),
              )}
            </tbody>
          </table>
          <div className="mt-3 border-t pt-3">
            <table className="w-full border-collapse">
              <tbody>
                {renderFeedLengthRow(['feed_first', 'feed_middle', 'feed_last'].filter((field) =>
                  columns.includes(field),
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {remainingFields.length > 0 ? (
          <table className="w-full border-collapse">
            <tbody>{remainingFields.map(renderFieldRow)}</tbody>
          </table>
        ) : null}
      </div>
    )
  }

  return (
    <div className="ui-card ui-card-body text-sm">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="min-w-0">
          <h2 className="text-sm font-bold text-gray-900 truncate">{title}</h2>
          <div className="text-xs text-gray-500">
            Type {block.block_type_id}
            {metadata.library_name ? ` | ${metadata.library_name}` : ''}
          </div>
        </div>
      </div>

      {isMergedDeformationBlock ? (
        renderMergedDeformationFields()
      ) : isTitleOnlyBlock ? null : columns.length === 0 ? (
        <div className="ui-field-readonly">This operation type has no editable fields.</div>
      ) : feedSpeedConfig ? (
        renderFeedSpeedFields(feedSpeedConfig)
      ) : (
        <table className="w-full border-collapse">
          <tbody>
            {columns.map(renderFieldRow)}
          </tbody>
        </table>
      )}
    </div>
  )
}
