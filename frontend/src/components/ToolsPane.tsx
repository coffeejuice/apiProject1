import { useEffect, useMemo, useState } from 'react'
import { useDocumentsStore } from '../stores/useDocumentsStore'
import { useSessionStore } from '../stores/useSessionStore'
import { useBlockClipboardStore } from '../stores/useBlockClipboardStore'
import Tooltip from './ui/Tooltip'
import ClipboardPane from './clipboard/ClipboardPane'
import type { ToolView } from './ToolsSwitcher'
import type { LibraryEditorView } from './editorPaneTypes'
import type { BlockEditorMeta } from './BlockEditor'

interface ToolsPaneProps {
  activeView: ToolView | null
  libraryView: LibraryEditorView
  onLibraryViewChange: (view: LibraryEditorView) => void
  editorMeta: BlockEditorMeta
  onCopySelectedBlockToClipboard: () => void
  onCutSelectedBlockToClipboard: () => void
  onRemoveSelectedBlock: () => void
  onPasteAfterSelectedBlock: () => void
  onClearSelectedBlocks: () => void
  onPasteClipboardClip: (clipId?: string) => void
}

function LibraryDiesIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <path
        d="M4 6.5h12v2.25c0 .97-.78 1.75-1.75 1.75h-1v3h-6.5v-3h-1A1.75 1.75 0 0 1 4 8.75V6.5Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M6.75 13.5h6.5M8 16h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
}

function LibraryDieAssembliesIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <rect x="3.5" y="4" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.5" />
      <rect x="11.5" y="4" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.5" />
      <rect x="7.5" y="11" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.5" />
      <path d="M8.5 6.5h3M10 9v2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
}

function LibraryPressesIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <path
        d="M6 3.5h8M7 3.5v4m6-4v4M5 7.5h10v2H5v-2Zm1 2v7h8v-7M8.25 12.5h3.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function LibraryMaterialsIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <path
        d="M4.5 14V6.75c0-.44.2-.86.54-1.14L9.5 2.5l5 3.11c.34.28.54.7.54 1.14V14l-5 3-5-3Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M7.5 9.25h5M10 6.75v5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
}

function CopyIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <rect x="7" y="6" width="8" height="10" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
      <path
        d="M5 13.5H4.5A1.5 1.5 0 0 1 3 12V4.5A1.5 1.5 0 0 1 4.5 3H11a1.5 1.5 0 0 1 1.5 1.5V5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  )
}

function NewDocumentIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <path
        d="M5 3.5h6.25L15 7.25V16a1.5 1.5 0 0 1-1.5 1.5h-7A1.5 1.5 0 0 1 5 16V3.5Z"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinejoin="round"
      />
      <path d="M11 3.75V7.5h3.75M7.75 12h4.5M10 9.75v4.5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function CutIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <path d="M4 4l12 12M16 4L4 16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <circle cx="5" cy="15" r="2" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="15" cy="15" r="2" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  )
}

function RemoveIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <path d="M4 6h12M8 6V4h4v2M6.5 6.5l.75 9h5.5l.75-9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function PasteAfterIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <path d="M7 4h6l1.5 2v9.5A1.5 1.5 0 0 1 13 17H7a1.5 1.5 0 0 1-1.5-1.5v-10A1.5 1.5 0 0 1 7 4Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M8 10h4M10 8v4M14.5 6H12V4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function ClearSelectionIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <rect x="4" y="4" width="12" height="12" rx="2" stroke="currentColor" strokeWidth="1.5" strokeDasharray="2 2" />
      <path d="M7 7l6 6M13 7l-6 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
}

function DocumentActionIconButton({
  label,
  onClick,
  disabled,
  variant = 'default',
  Icon,
}: {
  label: string
  onClick: () => void
  disabled: boolean
  variant?: 'default' | 'primary' | 'danger'
  Icon: ({ className }: { className?: string }) => React.ReactNode
}) {
  const className = variant === 'primary'
    ? 'ui-btn-primary h-9 w-9 shrink-0 p-0'
    : variant === 'danger'
      ? 'ui-btn-danger h-9 w-9 shrink-0 p-0'
      : 'ui-btn h-9 w-9 shrink-0 p-0'

  return (
    <Tooltip content={label}>
      <button
        type="button"
        onClick={onClick}
        disabled={disabled}
        className={className}
        aria-label={label}
      >
        <Icon className="h-6 w-6" />
      </button>
    </Tooltip>
  )
}

function ActionIconButton({
  label,
  onClick,
  disabled,
  variant = 'default',
  Icon,
}: {
  label: string
  onClick: () => void
  disabled: boolean
  variant?: 'default' | 'primary' | 'danger'
  Icon: ({ className }: { className?: string }) => React.ReactNode
}) {
  const className = variant === 'primary'
    ? 'ui-btn-primary h-7 w-7 p-0'
    : variant === 'danger'
      ? 'ui-btn-danger h-7 w-7 p-0'
      : 'ui-btn h-7 w-7 p-0'

  return (
    <Tooltip content={label}>
      <button
        type="button"
        onClick={onClick}
        disabled={disabled}
        className={className}
        aria-label={label}
      >
        <Icon className="h-4 w-4" />
      </button>
    </Tooltip>
  )
}

const LIBRARY_VIEW_ITEMS: Array<{
  id: LibraryEditorView
  label: string
  icon: ({ className }: { className?: string }) => React.ReactNode
}> = [
  { id: 'dies', label: 'Dies', icon: LibraryDiesIcon },
  { id: 'dieAssemblies', label: 'Die Assemblies', icon: LibraryDieAssembliesIcon },
  { id: 'presses', label: 'Presses', icon: LibraryPressesIcon },
  { id: 'materials', label: 'Materials', icon: LibraryMaterialsIcon },
]

export default function ToolsPane({
  activeView,
  libraryView,
  onLibraryViewChange,
  editorMeta,
  onCopySelectedBlockToClipboard,
  onCutSelectedBlockToClipboard,
  onRemoveSelectedBlock,
  onPasteAfterSelectedBlock,
  onClearSelectedBlocks,
  onPasteClipboardClip,
}: ToolsPaneProps) {
  const [projectsFilter, setProjectsFilter] = useState('')
  const [documentsFilter, setDocumentsFilter] = useState('')
  const [showProjectModal, setShowProjectModal] = useState(false)
  const [showNewDocModal, setShowNewDocModal] = useState(false)
  const [showCopyModal, setShowCopyModal] = useState(false)
  const [newProjectName, setNewProjectName] = useState('')
  const [newDocName, setNewDocName] = useState('')
  const [copySourceDocId, setCopySourceDocId] = useState('')
  const [copyName, setCopyName] = useState('')
  const [isCreatingProject, setIsCreatingProject] = useState(false)
  const [isCreatingDocument, setIsCreatingDocument] = useState(false)
  const [isCopyingDocument, setIsCopyingDocument] = useState(false)
  const [isDeletingProject, setIsDeletingProject] = useState(false)
  const [isDeletingDocuments, setIsDeletingDocuments] = useState(false)

  const {
    projects,
    currentProjectId,
    setCurrentProject,
    createProject,
    deleteProject,
    documents,
    currentDocId,
    setCurrentDoc,
    selectedDocIds,
    initializeDocumentSelection,
    toggleDocSelection,
    createDocument,
    copyDocument,
    deleteMultipleDocuments,
    isLoading,
  } = useDocumentsStore()

  const { user, baseUrl, logout } = useSessionStore()
  const activeBlocksPaneTab = useBlockClipboardStore((state) => state.activePaneTab)
  const setActiveBlocksPaneTab = useBlockClipboardStore((state) => state.setActivePaneTab)
  const clipboardClipsCount = useBlockClipboardStore((state) => state.clips.length)
  const activeClipboardClip = useBlockClipboardStore((state) =>
    state.clips.find((clip) => clip.id === state.activeClipId) ?? null
  )

  const filteredProjects = useMemo(() => {
    const needle = projectsFilter.trim().toLowerCase()
    if (!needle) {
      return projects
    }
    return projects.filter((project) => project.name.toLowerCase().includes(needle))
  }, [projects, projectsFilter])

  const filteredDocuments = useMemo(() => {
    const needle = documentsFilter.trim().toLowerCase()
    if (!needle) {
      return documents
    }
    return documents.filter((entry) => entry.name.toLowerCase().includes(needle))
  }, [documents, documentsFilter])

  const selectedDocumentIds = useMemo(() => Array.from(selectedDocIds), [selectedDocIds])

  useEffect(() => {
    if (activeView === 'documents') {
      initializeDocumentSelection()
    }
  }, [activeView, documents.length, initializeDocumentSelection])

  const openCopyModal = () => {
    setCopySourceDocId(selectedDocumentIds.length === 1 ? selectedDocumentIds[0] : '')
    setCopyName('')
    setShowCopyModal(true)
  }

  const createProjectFromModal = async (event: React.FormEvent) => {
    event.preventDefault()
    const trimmedName = newProjectName.trim()
    if (!trimmedName) {
      return
    }

    setIsCreatingProject(true)
    const created = await createProject(trimmedName)
    setIsCreatingProject(false)

    if (created) {
      setNewProjectName('')
      setShowProjectModal(false)
    }
  }

  const createDocumentFromModal = async (event: React.FormEvent) => {
    event.preventDefault()
    const trimmedName = newDocName.trim()
    if (!trimmedName) {
      return
    }

    setIsCreatingDocument(true)
    const created = await createDocument(trimmedName)
    setIsCreatingDocument(false)

    if (created) {
      setCurrentDoc(created.id)
      setNewDocName('')
      setShowNewDocModal(false)
    }
  }

  const deleteCurrentProject = async () => {
    if (!currentProjectId) {
      return
    }
    const project = projects.find((entry) => entry.id === currentProjectId)
    const projectName = project?.name ? ` "${project.name}"` : ''
    if (!window.confirm(`Remove selected project${projectName}?`)) {
      return
    }

    setIsDeletingProject(true)
    try {
      await deleteProject(currentProjectId)
    } finally {
      setIsDeletingProject(false)
    }
  }

  const copyDocumentFromModal = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!copySourceDocId) {
      return
    }

    setIsCopyingDocument(true)
    const copied = await copyDocument(copySourceDocId, copyName.trim() || undefined)
    setIsCopyingDocument(false)

    if (copied) {
      setCurrentDoc(copied.id)
      setShowCopyModal(false)
    }
  }

  const deleteSelectedDocuments = async () => {
    if (selectedDocumentIds.length === 0) {
      return
    }
    const message = selectedDocumentIds.length === 1
      ? 'Remove selected document?'
      : `Remove ${selectedDocumentIds.length} selected documents?`
    if (!window.confirm(message)) {
      return
    }

    setIsDeletingDocuments(true)
    try {
      await deleteMultipleDocuments(selectedDocumentIds)
    } finally {
      setIsDeletingDocuments(false)
    }
  }

  if (!activeView) {
    return null
  }

  if (activeView === 'simulation' || activeView === 'operations') {
    return null
  }

  const paneWidthClass = activeView === 'library' ? 'w-16 shrink-0' : 'w-80 shrink-0'
  const selectedBlockCount = editorMeta.selectedDocumentBlockIds.length
  const hasSingleSelectedBlock = selectedBlockCount === 1
  const hasActiveFallbackBlock = selectedBlockCount === 0 && Boolean(editorMeta.activeDocumentBlockId)
  const canUseActiveSingleBlock = hasSingleSelectedBlock || hasActiveFallbackBlock
  const selectedBlockLabel =
    editorMeta.selectedDocumentBlockLabel || editorMeta.activeDocumentBlockLabel || 'Selected block'
  const selectionActionDisabled = editorMeta.structureEditDisabled || !hasSingleSelectedBlock
  const singleBlockActionDisabled = editorMeta.structureEditDisabled || !canUseActiveSingleBlock

  return (
    <aside className={`ui-pane ${paneWidthClass}`}>
      {activeView !== 'library' ? (
        <div className="ui-pane-header">
          <h2 className="ui-pane-title">
            {activeView === 'projects' && 'Projects'}
            {activeView === 'documents' && 'Documents'}
            {activeView === 'blocks' && 'Blocks'}
            {activeView === 'users' && 'Users'}
          </h2>
        </div>
      ) : null}

      {activeView === 'projects' && (
        <div className="ui-pane-body">
          <div className="flex items-center gap-1.5">
            <input
              type="text"
              value={projectsFilter}
              onChange={(event) => setProjectsFilter(event.target.value)}
              placeholder="Filter projects..."
              className="ui-input flex-1"
            />
            <DocumentActionIconButton
              label="New project"
              onClick={() => setShowProjectModal(true)}
              disabled={false}
              variant="primary"
              Icon={NewDocumentIcon}
            />
            <DocumentActionIconButton
              label="Remove selected project"
              onClick={() => void deleteCurrentProject()}
              disabled={!currentProjectId || isDeletingProject}
              variant="danger"
              Icon={RemoveIcon}
            />
          </div>

          <div className="space-y-2">
            {filteredProjects.length === 0 ? (
              <div className="text-sm text-gray-500">No projects found.</div>
            ) : (
              filteredProjects.map((project) => {
                const isActive = project.id === currentProjectId
                return (
                  <button
                    key={project.id}
                    type="button"
                    onClick={() => setCurrentProject(project.id)}
                    className={`ui-list-item ${isActive ? 'ui-list-item-active' : ''}`}
                  >
                    <div className="font-medium text-sm truncate">{project.name}</div>
                    <div className="text-xs text-gray-500">ID: {project.project_id || project.id}</div>
                  </button>
                )
              })
            )}
          </div>
        </div>
      )}

      {activeView === 'documents' && (
        <div className="ui-pane-body">
          <div className="text-xs text-gray-500">
            Current project:{' '}
            <span className="font-medium text-gray-700">{currentProjectId || 'None selected'}</span>
          </div>

          <div className="flex items-center gap-1.5">
            <input
              type="text"
              value={documentsFilter}
              onChange={(event) => setDocumentsFilter(event.target.value)}
              placeholder="Filter documents..."
              className="ui-input flex-1"
              disabled={!currentProjectId}
            />
            <DocumentActionIconButton
              label="New document"
              onClick={() => setShowNewDocModal(true)}
              disabled={!currentProjectId}
              variant="primary"
              Icon={NewDocumentIcon}
            />
            <DocumentActionIconButton
              label="Copy selected document"
              onClick={openCopyModal}
              disabled={!currentProjectId || selectedDocIds.size !== 1}
              Icon={CopyIcon}
            />
            <DocumentActionIconButton
              label={selectedDocIds.size <= 1 ? 'Remove selected document' : 'Remove selected documents'}
              onClick={() => void deleteSelectedDocuments()}
              disabled={!currentProjectId || selectedDocIds.size === 0 || isDeletingDocuments}
              variant="danger"
              Icon={RemoveIcon}
            />
          </div>

          <div className="text-xs text-gray-500">
            Selected: {selectedDocIds.size}
            {selectedDocIds.size === 1 ? ` | active document ${currentDocId}` : ' | editor disabled'}
          </div>

          <div className="space-y-2">
            {isLoading && documents.length === 0 ? (
              <div className="text-sm text-gray-500">Loading documents...</div>
            ) : filteredDocuments.length === 0 ? (
              <div className="text-sm text-gray-500">No documents in this project.</div>
            ) : (
              filteredDocuments.map((entry) => {
                const entryId = String(entry.id)
                const isSelected = selectedDocIds.has(entryId)

                return (
                  <button
                    key={entryId}
                    type="button"
                    onClick={() => toggleDocSelection(entryId)}
                    aria-pressed={isSelected}
                    className={`ui-list-item ${isSelected ? 'ui-list-item-active' : ''}`}
                  >
                    <div className="font-medium text-sm truncate">{entry.name}</div>
                    <div className="text-xs text-gray-500">
                      ID: {entry.document_id || entry.id}
                      {entry.source_document_id ? ` | copy of ${entry.source_document_id}` : ''}
                    </div>
                  </button>
                )
              })
            )}
          </div>
        </div>
      )}

      {activeView === 'blocks' && (
        <div className="ui-pane-body">
          <div className="grid grid-cols-2 gap-1 rounded border border-[rgba(55,53,47,0.09)] bg-[rgba(242,241,238,0.55)] p-1">
            <button
              type="button"
              onClick={() => setActiveBlocksPaneTab('actions')}
              className={activeBlocksPaneTab === 'actions' ? 'ui-btn-primary' : 'ui-btn'}
            >
              Actions
            </button>
            <button
              type="button"
              onClick={() => setActiveBlocksPaneTab('clipboard')}
              className={activeBlocksPaneTab === 'clipboard' ? 'ui-btn-primary' : 'ui-btn'}
            >
              Clipboard {clipboardClipsCount > 0 ? `(${clipboardClipsCount})` : ''}
            </button>
          </div>

          {activeBlocksPaneTab === 'actions' ? (
            <div className="ui-card ui-card-body space-y-1.5 p-2">
              <div className="flex min-w-0 items-center gap-1">
                <span className="ui-badge shrink-0 px-1.5 py-0.5 text-[10px]">S:{selectedBlockCount}</span>
                <span className="ui-badge shrink-0 px-1.5 py-0.5 text-[10px]">
                  C:{activeClipboardClip?.blocks.length ?? 0}
                </span>
                <span className="min-w-0 flex-1 truncate text-xs font-medium text-gray-800">
                  {canUseActiveSingleBlock ? selectedBlockLabel : '-'}
                </span>
              </div>

              <div className="flex items-center gap-1">
                <ActionIconButton
                  label="Copy selected block"
                  onClick={onCopySelectedBlockToClipboard}
                  disabled={selectionActionDisabled}
                  Icon={CopyIcon}
                />
                <ActionIconButton
                  label="Cut selected block"
                  onClick={onCutSelectedBlockToClipboard}
                  disabled={singleBlockActionDisabled}
                  variant="danger"
                  Icon={CutIcon}
                />
                <ActionIconButton
                  label="Remove selected block"
                  onClick={onRemoveSelectedBlock}
                  disabled={singleBlockActionDisabled}
                  variant="danger"
                  Icon={RemoveIcon}
                />
                <ActionIconButton
                  label="Paste after selected block"
                  onClick={onPasteAfterSelectedBlock}
                  disabled={selectionActionDisabled || !activeClipboardClip}
                  variant="primary"
                  Icon={PasteAfterIcon}
                />
                <ActionIconButton
                  label="Clear selection"
                  onClick={onClearSelectedBlocks}
                  disabled={selectedBlockCount === 0}
                  Icon={ClearSelectionIcon}
                />
              </div>
            </div>
          ) : (
            <ClipboardPane onPasteClip={onPasteClipboardClip} />
          )}
        </div>
      )}

      {activeView === 'library' && (
        <div className="ui-pane-body items-center py-2">
          <div className="flex flex-col items-center gap-2">
            {LIBRARY_VIEW_ITEMS.map((item) => {
              const isActive = libraryView === item.id
              const Icon = item.icon

              return (
                <Tooltip key={item.id} content={item.label}>
                  <button
                    type="button"
                    onClick={() => onLibraryViewChange(item.id)}
                    aria-label={item.label}
                    className={`ui-btn w-10 h-10 p-0 ${
                      isActive
                        ? 'border-blue-600 bg-blue-50 text-blue-700'
                        : 'text-gray-700'
                    }`}
                  >
                    <Icon className="h-5 w-5" />
                  </button>
                </Tooltip>
              )
            })}
          </div>
        </div>
      )}

      {activeView === 'users' && (
        <div className="ui-pane-body space-y-3">
          <div className="ui-card ui-card-body">
            <div className="text-xs uppercase tracking-wide text-gray-500 mb-1">Current User</div>
            {user ? (
              <>
                <div className="font-medium text-sm text-gray-900">{user.login}</div>
                <div className="text-sm text-gray-600">{user.email}</div>
                <div className="text-xs text-gray-500 mt-1">ID: {user.user_id}</div>
              </>
            ) : (
              <div className="text-sm text-gray-500">No user loaded.</div>
            )}
          </div>

          <div className="ui-card ui-card-body">
            <div className="text-xs uppercase tracking-wide text-gray-500 mb-1">Connection</div>
            <div className="text-sm text-gray-700 break-all">{baseUrl}</div>
          </div>

          <button
            type="button"
            onClick={logout}
            className="ui-btn w-full"
          >
            Logout
          </button>
        </div>
      )}

      {showProjectModal && (
        <div className="ui-modal-overlay">
          <div className="ui-modal w-96">
            <h3 className="ui-pane-title mb-3">Create Project</h3>
            <form onSubmit={createProjectFromModal}>
              <input
                type="text"
                value={newProjectName}
                onChange={(event) => setNewProjectName(event.target.value)}
                placeholder="Project name..."
                className="ui-input mb-3"
                autoFocus
                disabled={isCreatingProject}
              />
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowProjectModal(false)}
                  className="ui-btn"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isCreatingProject || !newProjectName.trim()}
                  className="ui-btn-primary"
                >
                  {isCreatingProject ? 'Creating...' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showNewDocModal && (
        <div className="ui-modal-overlay">
          <div className="ui-modal w-96">
            <h3 className="ui-pane-title mb-3">Create Document</h3>
            <form onSubmit={createDocumentFromModal}>
              <input
                type="text"
                value={newDocName}
                onChange={(event) => setNewDocName(event.target.value)}
                placeholder="Document name..."
                className="ui-input mb-3"
                autoFocus
                disabled={isCreatingDocument}
              />
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowNewDocModal(false)}
                  className="ui-btn"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isCreatingDocument || !newDocName.trim() || !currentProjectId}
                  className="ui-btn-primary"
                >
                  {isCreatingDocument ? 'Creating...' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showCopyModal && (
        <div className="ui-modal-overlay">
          <div className="ui-modal w-96">
            <h3 className="ui-pane-title mb-3">Copy Document</h3>
            <form onSubmit={copyDocumentFromModal} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">Source</label>
                <select
                  value={copySourceDocId}
                  onChange={(event) => setCopySourceDocId(event.target.value)}
                  className="ui-select"
                >
                  <option value="">Select source document...</option>
                  {documents.map((entry) => (
                    <option key={entry.id} value={entry.id}>
                      {entry.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  New name (optional)
                </label>
                <input
                  type="text"
                  value={copyName}
                  onChange={(event) => setCopyName(event.target.value)}
                  placeholder="Copied document name..."
                  className="ui-input"
                />
              </div>

              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowCopyModal(false)}
                  className="ui-btn"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isCopyingDocument || !copySourceDocId}
                  className="ui-btn-secondary"
                >
                  {isCopyingDocument ? 'Copying...' : 'Copy'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </aside>
  )
}
