import { useState } from 'react'
import { useDocumentsStore } from '../stores/useDocumentsStore'
import { useSessionStore } from '../stores/useSessionStore'
import type { DocumentDiffResponse } from '../types/api'

export default function Sidebar() {
  const [newDocName, setNewDocName] = useState('')
  const [newProjectName, setNewProjectName] = useState('')
  const [showNewDocModal, setShowNewDocModal] = useState(false)
  const [showNewProjectModal, setShowNewProjectModal] = useState(false)
  const [isCreating, setIsCreating] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [isDiffing, setIsDiffing] = useState(false)
  const [filterText, setFilterText] = useState('')
  const [diffResult, setDiffResult] = useState<DocumentDiffResponse | null>(null)

  const {
    projects,
    currentProjectId,
    setCurrentProject,
    createProject,
    documents: allDocuments,
    currentDocId,
    setCurrentDoc,
    createDocument,
    copyDocument,
    deleteMultipleDocuments,
    isLoading,
    selectedDocIds,
    toggleDocSelection,
    clearSelection,
    selectAll,
    getDiff,
  } = useDocumentsStore()

  const { user, logout } = useSessionStore()

  const documents = allDocuments.filter((doc) =>
    doc.name.toLowerCase().includes(filterText.toLowerCase())
  )

  const handleCreateDocument = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!newDocName.trim()) return
    setIsCreating(true)
    const created = await createDocument(newDocName.trim())
    setIsCreating(false)
    if (created) {
      setCurrentDoc(created.id)
      setNewDocName('')
      setShowNewDocModal(false)
    }
  }

  const handleCreateProject = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!newProjectName.trim()) return
    setIsCreating(true)
    const created = await createProject(newProjectName.trim())
    setIsCreating(false)
    if (created) {
      setCurrentProject(created.id)
      setNewProjectName('')
      setShowNewProjectModal(false)
    }
  }

  const handleCopyDocument = async () => {
    const sourceId = currentDocId || Array.from(selectedDocIds)[0]
    if (!sourceId) return
    const copied = await copyDocument(sourceId)
    if (copied) {
      setCurrentDoc(copied.id)
    }
  }

  const handleDeleteDocuments = async () => {
    const idsToDelete = selectedDocIds.size > 0
      ? Array.from(selectedDocIds)
      : currentDocId
        ? [currentDocId]
        : []

    if (idsToDelete.length === 0) return
    const message = idsToDelete.length === 1
      ? 'Delete selected document?'
      : `Delete ${idsToDelete.length} documents?`
    if (!confirm(message)) {
      return
    }

    setIsDeleting(true)
    await deleteMultipleDocuments(idsToDelete)
    setIsDeleting(false)
  }

  const handleToggleSelectAll = () => {
    if (selectedDocIds.size === documents.length && documents.length > 0) {
      clearSelection()
    } else {
      selectAll(documents.map((doc) => String(doc.id)))
    }
  }

  const handleDiff = async () => {
    if (selectedDocIds.size !== 2) return
    const [left, right] = Array.from(selectedDocIds)
    setIsDiffing(true)
    const diff = await getDiff(left, right)
    if (diff) {
      setDiffResult(diff)
    }
    setIsDiffing(false)
  }

  return (
    <aside className="ui-pane w-96">
      <div className="ui-pane-header">
        <div className="flex items-center justify-between mb-2">
          <h1 className="ui-pane-title">Techno-Notion</h1>
          <button
            type="button"
            onClick={logout}
            className="ui-btn"
          >
            Logout
          </button>
        </div>

        {user && (
          <div className="text-sm text-gray-600">
            {user.login} ({user.email})
          </div>
        )}
      </div>

      <div className="p-3 border-b border-gray-200 space-y-3">
        <div className="flex gap-2">
          <select
            value={currentProjectId || ''}
            onChange={(event) => setCurrentProject(event.target.value || null)}
            className="ui-select flex-1"
          >
            {projects.length === 0 && <option value="">No projects</option>}
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => setShowNewProjectModal(true)}
            className="ui-btn"
          >
            New Project
          </button>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={() => setShowNewDocModal(true)}
            disabled={!currentProjectId}
            className="ui-btn-primary"
          >
            New Document
          </button>
          <button
            type="button"
            onClick={handleCopyDocument}
            disabled={!currentDocId && selectedDocIds.size === 0}
            className="ui-btn-secondary"
          >
            Copy
          </button>
          <button
            type="button"
            onClick={handleDeleteDocuments}
            disabled={(selectedDocIds.size === 0 && !currentDocId) || isDeleting}
            className="ui-btn-danger"
          >
            {isDeleting ? 'Deleting...' : 'Delete'}
          </button>
          <button
            type="button"
            onClick={handleDiff}
            disabled={selectedDocIds.size !== 2 || isDiffing}
            className="ui-btn"
          >
            {isDiffing ? 'Comparing...' : 'Diff'}
          </button>
        </div>

        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={handleToggleSelectAll}
            className="ui-btn"
          >
            {selectedDocIds.size === documents.length && documents.length > 0
              ? 'Deselect all'
              : 'Select all'}
          </button>
          <div className="text-xs text-gray-500">
            Select exactly 2 docs for diff
          </div>
        </div>

        <input
          type="text"
          value={filterText}
          onChange={(event) => setFilterText(event.target.value)}
          placeholder="Filter documents..."
          className="ui-input"
        />
      </div>

      <div className="flex-1 overflow-y-auto">
        {isLoading && documents.length === 0 ? (
          <div className="p-4 text-center text-gray-500 text-sm">Loading documents...</div>
        ) : documents.length === 0 ? (
          <div className="p-4 text-center text-gray-500 text-sm">No documents in this project.</div>
        ) : (
          <div className="py-2">
            {documents.map((doc) => {
              const docId = String(doc.id)
              const isSelected = selectedDocIds.has(docId)
              const isActive = currentDocId === docId

              return (
                <div
                  key={docId}
                  className={`flex items-center gap-2 px-3 py-2 hover:bg-gray-50 border-l-4 transition-colors ${
                    isActive ? 'border-blue-600 bg-blue-50' : 'border-transparent'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={() => toggleDocSelection(docId)}
                    className="w-4 h-4 text-blue-600 border-gray-300 rounded"
                  />
                  <button
                    type="button"
                    onClick={() => setCurrentDoc(docId)}
                    className="flex-1 text-left"
                  >
                    <div className="font-medium text-gray-900 truncate">{doc.name}</div>
                    <div className="text-xs text-gray-500 mt-1">
                      ID: {doc.document_id || doc.id}
                      {doc.source_document_id ? ` | copy of ${doc.source_document_id}` : ''}
                    </div>
                  </button>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {showNewProjectModal && (
        <div className="ui-modal-overlay">
          <div className="ui-modal w-96">
            <h2 className="ui-pane-title mb-3">Create Project</h2>
            <form onSubmit={handleCreateProject}>
              <input
                type="text"
                value={newProjectName}
                onChange={(event) => setNewProjectName(event.target.value)}
                placeholder="Project name..."
                className="ui-input mb-3"
                disabled={isCreating}
                autoFocus
              />
              <div className="flex gap-2 justify-end">
                <button
                  type="button"
                  onClick={() => setShowNewProjectModal(false)}
                  className="ui-btn"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isCreating || !newProjectName.trim()}
                  className="ui-btn-primary"
                >
                  {isCreating ? 'Creating...' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showNewDocModal && (
        <div className="ui-modal-overlay">
          <div className="ui-modal w-96">
            <h2 className="ui-pane-title mb-3">Create Document</h2>
            <form onSubmit={handleCreateDocument}>
              <input
                type="text"
                value={newDocName}
                onChange={(event) => setNewDocName(event.target.value)}
                placeholder="Document name..."
                className="ui-input mb-3"
                disabled={isCreating}
                autoFocus
              />
              <div className="flex gap-2 justify-end">
                <button
                  type="button"
                  onClick={() => setShowNewDocModal(false)}
                  className="ui-btn"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isCreating || !newDocName.trim() || !currentProjectId}
                  className="ui-btn-primary"
                >
                  {isCreating ? 'Creating...' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {diffResult && (
        <div className="ui-modal-overlay">
          <div className="ui-modal w-full max-w-4xl max-h-[80vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold">
                Diff: {diffResult.left_name} vs {diffResult.right_name}
              </h2>
              <button
                type="button"
                onClick={() => setDiffResult(null)}
                className="ui-btn"
              >
                Close
              </button>
            </div>
            <div className="text-sm text-gray-600 mb-4">
              Total changes: {diffResult.total_changes}
            </div>
            {diffResult.changes.length === 0 ? (
              <div className="text-sm text-gray-500">No differences.</div>
            ) : (
              <div className="space-y-3">
                {diffResult.changes.map((change) => (
                  <div key={`${change.index}-${change.change_type}`} className="border rounded p-3">
                    <div className="font-medium text-sm mb-1">
                      #{change.index} - {change.change_type}
                    </div>
                    <div className="text-xs text-gray-600">
                      Left: {change.left_block_type_id || '-'} | Right: {change.right_block_type_id || '-'}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </aside>
  )
}
