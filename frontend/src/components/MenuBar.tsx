import { Link } from 'react-router-dom'

import type { BlockEditorMeta } from './BlockEditor'
import Tooltip from './ui/Tooltip'

interface MenuBarProps {
  meta: BlockEditorMeta
  hasDocument: boolean
  documentTitle?: string | null
  onSave: () => void
  onCancel: () => void
  onUndo: () => void
  onRedo: () => void
  onShowLineage: () => void
  onShowSessions: () => void
  showPreprocessorResults: boolean
  showPostprocessorResults: boolean
  onTogglePreprocessorResults: () => void
  onTogglePostprocessorResults: () => void
}

export default function MenuBar({
  meta,
  hasDocument,
  documentTitle = null,
  onSave,
  onCancel,
  onUndo,
  onRedo,
  onShowLineage,
  onShowSessions,
  showPreprocessorResults,
  showPostprocessorResults,
  onTogglePreprocessorResults,
  onTogglePostprocessorResults,
}: MenuBarProps) {
  const disabled = !hasDocument || meta.isLoading
  const title = hasDocument
    ? meta.draftDocumentName || documentTitle || 'Untitled Document'
    : documentTitle || 'No document selected'

  return (
    <header className="ui-toolbar">
      <div className="min-w-0">
        <div className="ui-toolbar-title">{title}</div>
        <div className="ui-toolbar-meta">
          Source document: {meta.sourceDocumentId ?? 'None'}
        </div>
      </div>

      <div className="flex items-center gap-2 flex-wrap justify-end">
        <Link to="/setup" className="ui-btn">
          Setup
        </Link>

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

        <div className="inline-flex rounded-full border border-[rgba(55,53,47,0.12)] bg-white p-0.5 text-[11px] shadow-sm">
          <button
            type="button"
            onClick={onTogglePreprocessorResults}
            disabled={disabled}
            aria-pressed={showPreprocessorResults}
            className={`rounded-full px-2.5 py-1 font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${
              showPreprocessorResults
                ? 'bg-[rgba(55,53,47,0.88)] text-white'
                : 'text-[rgba(55,53,47,0.58)] hover:bg-[rgba(55,53,47,0.06)]'
            }`}
            title="Show or hide inline Preprocessor results in the document"
          >
            Preprocessor
          </button>
          <button
            type="button"
            onClick={onTogglePostprocessorResults}
            disabled={disabled}
            aria-pressed={showPostprocessorResults}
            className={`rounded-full px-2.5 py-1 font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${
              showPostprocessorResults
                ? 'bg-[rgba(55,53,47,0.88)] text-white'
                : 'text-[rgba(55,53,47,0.58)] hover:bg-[rgba(55,53,47,0.06)]'
            }`}
            title="Show or hide inline Postprocessor results in the document"
          >
            Postprocessor
          </button>
        </div>

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
            <Tooltip content={meta.saveError || 'Error'}>
              <span className="text-red-600" aria-label={meta.saveError || 'Error'}>
                Error
              </span>
            </Tooltip>
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
