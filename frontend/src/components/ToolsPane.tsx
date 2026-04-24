import { DragEvent, useEffect, useMemo, useState } from 'react'
import { useDocumentsStore } from '../stores/useDocumentsStore'
import { useSessionStore } from '../stores/useSessionStore'
import { useBlockClipboardStore } from '../stores/useBlockClipboardStore'
import { apiClient } from '../lib/apiClient'
import Tooltip from './ui/Tooltip'
import ClipboardPane from './clipboard/ClipboardPane'
import type { ToolView } from './ToolsSwitcher'
import type { LibraryEditorView } from './editorPaneTypes'
import type { OperationBlockTypeRecord } from '../types/api'

interface ToolsPaneProps {
  activeView: ToolView | null
  libraryView: LibraryEditorView
  onLibraryViewChange: (view: LibraryEditorView) => void
  onInsertBlockType: (blockTypeId: string) => void
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
  onInsertBlockType,
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
  const [blocksFilter, setBlocksFilter] = useState('')
  const [operationTypes, setOperationTypes] = useState<OperationBlockTypeRecord[]>([])
  const [operationTypesLoading, setOperationTypesLoading] = useState(false)
  const [operationTypesError, setOperationTypesError] = useState<string | null>(null)
  const [isCreatingProject, setIsCreatingProject] = useState(false)
  const [isCreatingDocument, setIsCreatingDocument] = useState(false)
  const [isCopyingDocument, setIsCopyingDocument] = useState(false)

  const {
    projects,
    currentProjectId,
    setCurrentProject,
    createProject,
    documents,
    currentDocId,
    setCurrentDoc,
    selectedDocIds,
    initializeDocumentSelection,
    toggleDocSelection,
    createDocument,
    copyDocument,
    isLoading,
  } = useDocumentsStore()

  const { user, baseUrl, logout } = useSessionStore()
  const activeBlocksPaneTab = useBlockClipboardStore((state) => state.activePaneTab)
  const setActiveBlocksPaneTab = useBlockClipboardStore((state) => state.setActivePaneTab)
  const clipboardClipsCount = useBlockClipboardStore((state) => state.clips.length)

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

  const filteredOperationTypes = useMemo(() => {
    const needle = blocksFilter.trim().toLowerCase()
    if (!needle) {
      return operationTypes
    }
    return operationTypes.filter((entry) => {
      const haystack = [
        String(entry.type_id),
        entry.library_name,
        entry.process_name,
        entry.text_id,
        ...entry.db_column_names,
      ].join(' ').toLowerCase()
      return haystack.includes(needle)
    })
  }, [blocksFilter, operationTypes])

  useEffect(() => {
    if (activeView !== 'blocks') {
      return
    }

    let isActive = true
    setOperationTypesLoading(true)
    setOperationTypesError(null)

    const loadOperationTypes = async () => {
      const response = await apiClient.get<OperationBlockTypeRecord[]>(
        '/library/db/document-block-types',
        {
          params: {
            insertable_only: true,
          },
        }
      )

      if (!isActive) {
        return
      }

      if (response.ok && response.data) {
        setOperationTypes(response.data)
      } else {
        setOperationTypesError(response.errorMessage || 'Failed to load operation block types')
      }
      setOperationTypesLoading(false)
    }

    void loadOperationTypes()

    return () => {
      isActive = false
    }
  }, [activeView])

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

  const handleBlockDragStart = (event: DragEvent<HTMLElement>, blockTypeId: string) => {
    event.dataTransfer.setData('application/x-forgelab-block-type', blockTypeId)
    event.dataTransfer.setData('text/plain', blockTypeId)
    event.dataTransfer.effectAllowed = 'copy'
  }

  if (!activeView) {
    return null
  }

  if (activeView === 'simulation') {
    return null
  }

  const paneWidthClass = activeView === 'library' ? 'w-16 shrink-0' : 'w-80 shrink-0'

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
          <div className="flex gap-2">
            <input
              type="text"
              value={projectsFilter}
              onChange={(event) => setProjectsFilter(event.target.value)}
              placeholder="Filter projects..."
              className="ui-input flex-1"
            />
            <button
              type="button"
              onClick={() => setShowProjectModal(true)}
              className="ui-btn"
            >
              Create new
            </button>
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

          <div className="flex gap-2">
            <input
              type="text"
              value={documentsFilter}
              onChange={(event) => setDocumentsFilter(event.target.value)}
              placeholder="Filter documents..."
              className="ui-input flex-1"
              disabled={!currentProjectId}
            />
          </div>

          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setShowNewDocModal(true)}
              disabled={!currentProjectId}
              className="ui-btn-primary flex-1"
            >
              New
            </button>
            <button
              type="button"
              onClick={openCopyModal}
              disabled={!currentProjectId || selectedDocIds.size !== 1}
              className="ui-btn-secondary flex-1"
            >
              Copy
            </button>
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
          <div className="grid grid-cols-2 gap-1 rounded border border-gray-200 bg-gray-50 p-1">
            <button
              type="button"
              onClick={() => setActiveBlocksPaneTab('catalog')}
              className={activeBlocksPaneTab === 'catalog' ? 'ui-btn-primary' : 'ui-btn'}
            >
              Catalog
            </button>
            <button
              type="button"
              onClick={() => setActiveBlocksPaneTab('clipboard')}
              className={activeBlocksPaneTab === 'clipboard' ? 'ui-btn-primary' : 'ui-btn'}
            >
              Clipboard {clipboardClipsCount > 0 ? `(${clipboardClipsCount})` : ''}
            </button>
          </div>

          {activeBlocksPaneTab === 'catalog' ? (
            <>
              <div className="text-xs text-gray-500">
                Drag an operation card into BlockEditor, or double-click it to insert.
              </div>

              <input
                type="text"
                value={blocksFilter}
                onChange={(event) => setBlocksFilter(event.target.value)}
                placeholder="Filter operations..."
                className="ui-input"
              />

              {operationTypesError && (
                <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded px-2 py-1">
                  {operationTypesError}
                </div>
              )}

              {operationTypesLoading && operationTypes.length === 0 ? (
                <div className="text-sm text-gray-500">Loading operation types...</div>
              ) : null}

              {!operationTypesLoading && filteredOperationTypes.length === 0 ? (
                <div className="text-sm text-gray-500">No operation types found.</div>
              ) : null}

              <div className="space-y-2">
                {filteredOperationTypes.map((entry) => {
                  const blockTypeId = String(entry.type_id)
                  const columnSummary = entry.db_column_names.length > 0
                    ? entry.db_column_names.join(', ')
                    : 'no fields'

                  return (
                    <Tooltip key={entry.type_id} content={`Drag or double-click ${entry.library_name}`}>
                      <div
                        draggable
                        role="button"
                        tabIndex={0}
                        onDragStart={(event) => handleBlockDragStart(event, blockTypeId)}
                        onDoubleClick={() => onInsertBlockType(blockTypeId)}
                        onKeyDown={(event) => {
                          if (event.key === 'Enter') {
                            onInsertBlockType(blockTypeId)
                          }
                        }}
                        className="ui-card ui-card-body flex cursor-grab items-center gap-2 active:cursor-grabbing hover:border-blue-300 hover:bg-blue-50/30"
                        aria-label={`Drag or double-click ${entry.library_name}`}
                      >
                        <div className="ui-btn pointer-events-none w-10 h-10 p-0 font-semibold">
                          OP
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium truncate">{entry.library_name}</div>
                          <div className="text-xs text-gray-500 truncate">
                            #{entry.type_id} | {columnSummary}
                          </div>
                        </div>
                      </div>
                    </Tooltip>
                  )
                })}
              </div>
            </>
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
