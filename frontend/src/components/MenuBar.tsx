import { Link } from 'react-router-dom'

import type { BlockEditorMeta } from './BlockEditor'

interface MenuBarProps {
  meta: BlockEditorMeta
  hasDocument: boolean
  isTopEditorVisible: boolean
  showTopEditorToggle: boolean
  onToggleTopEditor: () => void
  onSave: () => void
  onCancel: () => void
  onUndo: () => void
  onRedo: () => void
  onShowLineage: () => void
  onShowSessions: () => void
}

export default function MenuBar({
  meta,
  hasDocument,
  isTopEditorVisible,
  showTopEditorToggle,
  onToggleTopEditor,
  onSave,
  onCancel,
  onUndo,
  onRedo,
  onShowLineage,
  onShowSessions,
}: MenuBarProps) {
  const disabled = !hasDocument || meta.isLoading

  return (
    <header className="ui-toolbar">
      <div className="min-w-0">
        <div className="ui-toolbar-title">
          {hasDocument ? meta.draftDocumentName || 'Untitled Document' : 'No document selected'}
        </div>
        <div className="ui-toolbar-meta">
          Source document: {meta.sourceDocumentId ?? 'None'}
        </div>
      </div>

      <div className="flex items-center gap-2 flex-wrap justify-end">
        <Link to="/setup" className="ui-btn">
          Setup
        </Link>

        {showTopEditorToggle && (
          <button
            type="button"
            onClick={onToggleTopEditor}
            className="ui-btn"
          >
            {isTopEditorVisible ? 'Hide TopEditorPane' : 'Show TopEditorPane'}
          </button>
        )}

        <button
          type="button"
          onClick={onSave}
          disabled={disabled || !meta.hasUnsavedChanges || meta.saveStatus === 'saving'}
          className="ui-btn-primary"
        >
          Save
        </button>

        <button
          type="button"
          onClick={onCancel}
          disabled={disabled || !meta.hasUnsavedChanges || meta.saveStatus === 'saving'}
          className="ui-btn"
        >
          Cancel
        </button>

        <button
          type="button"
          onClick={onUndo}
          disabled={disabled || !meta.canUndo}
          className="ui-btn"
        >
          Undo
        </button>

        <button
          type="button"
          onClick={onRedo}
          disabled={disabled || !meta.canRedo}
          className="ui-btn"
        >
          Redo
        </button>

        <button
          type="button"
          onClick={onShowLineage}
          disabled={disabled || meta.isLineageLoading}
          className="ui-btn"
        >
          {meta.isLineageLoading ? 'Loading...' : 'Lineage'}
        </button>

        <button
          type="button"
          onClick={onShowSessions}
          disabled={disabled || meta.isSessionsLoading}
          className="ui-btn"
        >
          {meta.isSessionsLoading ? 'Loading...' : 'Sessions'}
        </button>

        <div className="ui-badge min-w-[110px] text-center">
          {meta.saveStatus === 'saving' && <span className="text-blue-600">Saving...</span>}
          {meta.saveStatus === 'saved' && <span className="text-green-600">Saved</span>}
          {meta.saveStatus === 'error' && (
            <span className="text-red-600" title={meta.saveError || 'Error'}>
              Error
            </span>
          )}
          {meta.saveStatus === 'idle' && (
            <span className={meta.hasUnsavedChanges ? 'text-amber-600' : 'text-gray-500'}>
              {meta.hasUnsavedChanges ? `${meta.changedBlocksCount} unsaved` : 'Up to date'}
            </span>
          )}
        </div>
      </div>
    </header>
  )
}
