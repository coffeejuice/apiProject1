import type { BlockComponentProps } from './BlockRegistry'

function normalizeValue(value: unknown): string {
  return value === null || value === undefined ? '' : String(value)
}

function renderResetButton(onClick: () => void, isReadOnly: boolean, isDirty: boolean) {
  if (isReadOnly || !isDirty) {
    return null
  }

  return (
    <button
      type="button"
      onClick={onClick}
      className="ui-btn-danger h-8 w-8 p-0 flex-shrink-0"
      title="Revert this parameter"
    >
      ↺
    </button>
  )
}

export default function BasicContentBlock({
  block,
  baselineProps,
  onUpdate,
  isReadOnly = false,
}: BlockComponentProps) {
  const currentText = normalizeValue(block.props?.text)
  const baselineText = normalizeValue(baselineProps?.text)
  const isTextDirty = currentText !== baselineText

  const updateText = (text: string) => {
    onUpdate(block.block_id, {
      ...(block.props || {}),
      text,
    })
  }

  const resetText = () => {
    updateText(baselineText)
  }

  if (block.block_type_id === 'divider') {
    return (
      <div className="ui-card ui-card-body">
        <hr className="border-gray-300" />
      </div>
    )
  }

  if (block.block_type_id === 'todo') {
    const currentChecked = Boolean(block.props?.checked)
    const baselineChecked = Boolean(baselineProps?.checked)
    const isCheckedDirty = currentChecked !== baselineChecked

    return (
      <div className="ui-card ui-card-body">
        <div className="flex items-start gap-2">
          <input
            type="checkbox"
            checked={currentChecked}
            disabled={isReadOnly}
            onChange={(event) => {
              onUpdate(block.block_id, {
                ...(block.props || {}),
                checked: event.target.checked,
              })
            }}
            className="mt-2"
          />
          {isReadOnly ? (
            <p className="text-gray-900 flex-1">{currentText || 'Todo item'}</p>
          ) : (
            <input
              type="text"
              value={currentText}
              onChange={(event) => updateText(event.target.value)}
              className={`ui-input flex-1 ${
                isTextDirty ? 'border-red-300 bg-red-50' : 'border-gray-300'
              }`}
              placeholder="Todo item"
            />
          )}
          {renderResetButton(resetText, isReadOnly, isTextDirty)}
          {renderResetButton(
            () => {
              onUpdate(block.block_id, {
                ...(block.props || {}),
                checked: baselineChecked,
              })
            },
            isReadOnly,
            isCheckedDirty
          )}
        </div>
      </div>
    )
  }

  const isHeading = block.block_type_id === 'heading1' || block.block_type_id === 'heading2'
  const headingClass =
    block.block_type_id === 'heading1' ? 'text-sm font-bold' : 'text-xs font-semibold'
  const isCode = block.block_type_id === 'code'
  const isQuote = block.block_type_id === 'quote'
  const isList = block.block_type_id === 'list'

  return (
    <div className="ui-card ui-card-body text-sm">
      <div className="flex items-start gap-2">
        {isReadOnly ? (
          <div
            className={`flex-1 whitespace-pre-wrap text-gray-900 ${
              isHeading ? headingClass : isCode ? 'font-mono' : ''
            } ${isQuote ? 'border-l-4 border-gray-300 pl-4 italic text-gray-700' : ''}`}
          >
            {currentText || 'Empty block'}
          </div>
        ) : isHeading ? (
          <input
            type="text"
            value={currentText}
            onChange={(event) => updateText(event.target.value)}
            className={`ui-input flex-1 ${headingClass} ${
              isTextDirty ? 'border-red-300 bg-red-50' : 'border-gray-300'
            }`}
            placeholder={block.block_type_id === 'heading1' ? 'Heading 1' : 'Heading 2'}
          />
        ) : isCode ? (
          <textarea
            value={currentText}
            onChange={(event) => updateText(event.target.value)}
            className={`flex-1 px-2 py-1 border rounded font-mono text-sm bg-gray-900 text-gray-100 ${
              isTextDirty ? 'border-red-300' : 'border-gray-700'
            }`}
            rows={4}
            placeholder="Code block"
          />
        ) : isQuote ? (
          <textarea
            value={currentText}
            onChange={(event) => updateText(event.target.value)}
            className={`flex-1 px-2 py-1 text-xs border-l-4 border-gray-300 italic rounded-r ${
              isTextDirty ? 'border-red-300 bg-red-50' : 'border-gray-300 bg-gray-50'
            }`}
            rows={3}
            placeholder="Quote"
          />
        ) : (
          <textarea
            value={currentText}
            onChange={(event) => updateText(event.target.value)}
            className={`ui-textarea flex-1 ${
              isTextDirty ? 'border-red-300 bg-red-50' : 'border-gray-300'
            }`}
            rows={isList ? 4 : 3}
            placeholder={isList ? 'One list item per line' : 'Text'}
          />
        )}

        {renderResetButton(resetText, isReadOnly, isTextDirty)}
      </div>

      {isList && (
        <div className="text-xs text-gray-500 mt-2">
          Each line is treated as a separate list item.
        </div>
      )}
    </div>
  )
}
