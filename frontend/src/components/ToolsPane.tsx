import { DragEvent, useMemo, useState } from 'react'
import { useDocumentsStore } from '../stores/useDocumentsStore'
import { useSessionStore } from '../stores/useSessionStore'
import { BLOCK_LIBRARY_TYPES, getBlockTypeIcon, getBlockTypeLabel } from '../lib/blockTypeMeta'
import type { ToolView } from './ToolsSwitcher'
import type { LibraryEditorView } from './editorPaneTypes'

interface ToolsPaneProps {
  activeView: ToolView | null
  libraryView: LibraryEditorView
  onLibraryViewChange: (view: LibraryEditorView) => void
  onInsertBlockType: (blockTypeId: string) => void
}

export default function ToolsPane({
  activeView,
  libraryView,
  onLibraryViewChange,
  onInsertBlockType,
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

  const {
    projects,
    currentProjectId,
    setCurrentProject,
    createProject,
    documents,
    currentDocId,
    setCurrentDoc,
    createDocument,
    copyDocument,
    isLoading,
  } = useDocumentsStore()

  const { user, baseUrl, logout } = useSessionStore()

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

  const openCopyModal = () => {
    setCopySourceDocId(currentDocId || documents[0]?.id || '')
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

  const handleBlockDragStart = (event: DragEvent<HTMLButtonElement>, blockTypeId: string) => {
    event.dataTransfer.setData('application/x-forgelab-block-type', blockTypeId)
    event.dataTransfer.effectAllowed = 'copy'
  }

  if (!activeView) {
    return null
  }

  const paneWidthClass = activeView === 'library' ? 'w-44 shrink-0' : 'w-80 shrink-0'

  return (
    <aside className={`ui-pane ${paneWidthClass}`}>
      <div className="ui-pane-header">
        <h2 className="ui-pane-title">
          {activeView === 'projects' && 'Projects'}
          {activeView === 'documents' && 'Documents'}
          {activeView === 'blocks' && 'Blocks'}
          {activeView === 'library' && 'Library'}
          {activeView === 'users' && 'Users'}
        </h2>
      </div>

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
              disabled={!currentProjectId || documents.length === 0}
              className="ui-btn-secondary flex-1"
            >
              Copy
            </button>
          </div>

          <div className="space-y-2">
            {isLoading && documents.length === 0 ? (
              <div className="text-sm text-gray-500">Loading documents...</div>
            ) : filteredDocuments.length === 0 ? (
              <div className="text-sm text-gray-500">No documents in this project.</div>
            ) : (
              filteredDocuments.map((entry) => {
                const entryId = String(entry.id)
                const isActive = currentDocId === entryId

                return (
                  <button
                    key={entryId}
                    type="button"
                    onClick={() => setCurrentDoc(entryId)}
                    className={`ui-list-item ${isActive ? 'ui-list-item-active' : ''}`}
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
          <div className="text-xs text-gray-500">
            Drag a block type into BlockEditor or use Insert.
          </div>

          <div className="space-y-2">
            {BLOCK_LIBRARY_TYPES.map((entry) => (
              <div key={entry.id} className="ui-card ui-card-body flex items-center gap-2">
                <button
                  type="button"
                  draggable
                  onDragStart={(event) => handleBlockDragStart(event, entry.id)}
                  className="ui-btn w-10 h-10 p-0 font-semibold"
                  title={`Drag ${getBlockTypeLabel(entry.id)}`}
                >
                  {getBlockTypeIcon(entry.id)}
                </button>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium truncate">{getBlockTypeLabel(entry.id)}</div>
                  <div className="text-xs text-gray-500">{entry.id}</div>
                </div>
                <button
                  type="button"
                  onClick={() => onInsertBlockType(entry.id)}
                  className="ui-btn"
                >
                  Insert
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeView === 'library' && (
        <div className="ui-pane-body">
          <div className="text-xs text-gray-500">
            Select Library editor view.
          </div>
          <div className="space-y-2">
            <button
              type="button"
              onClick={() => onLibraryViewChange('dies')}
              className={`ui-list-item ${libraryView === 'dies' ? 'ui-list-item-active' : ''}`}
            >
              Dies
            </button>
            <button
              type="button"
              onClick={() => onLibraryViewChange('dieAssemblies')}
              className={`ui-list-item ${libraryView === 'dieAssemblies' ? 'ui-list-item-active' : ''}`}
            >
              Die Assemblies
            </button>
            <button
              type="button"
              onClick={() => onLibraryViewChange('presses')}
              className={`ui-list-item ${libraryView === 'presses' ? 'ui-list-item-active' : ''}`}
            >
              Presses
            </button>
            <button
              type="button"
              onClick={() => onLibraryViewChange('materials')}
              className={`ui-list-item ${libraryView === 'materials' ? 'ui-list-item-active' : ''}`}
            >
              Materials
            </button>
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
