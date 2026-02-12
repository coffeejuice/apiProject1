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
    <aside className="w-96 bg-white border-r border-gray-200 flex flex-col">
      <div className="p-4 border-b border-gray-200">
        <div className="flex items-center justify-between mb-2">
          <h1 className="text-xl font-bold text-gray-900">Techno-Notion</h1>
          <button
            type="button"
            onClick={logout}
            className="text-sm text-gray-600 hover:text-gray-900"
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

      <div className="p-4 border-b border-gray-200 space-y-3">
        <div className="flex gap-2">
          <select
            value={currentProjectId || ''}
            onChange={(event) => setCurrentProject(event.target.value || null)}
            className="flex-1 px-3 py-2 border border-gray-300 rounded-md text-sm"
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
            className="px-3 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50"
          >
            New Project
          </button>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={() => setShowNewDocModal(true)}
            disabled={!currentProjectId}
            className="bg-blue-600 text-white py-2 px-3 rounded-md hover:bg-blue-700 text-sm disabled:opacity-50"
          >
            New Document
          </button>
          <button
            type="button"
            onClick={handleCopyDocument}
            disabled={!currentDocId && selectedDocIds.size === 0}
            className="bg-indigo-600 text-white py-2 px-3 rounded-md hover:bg-indigo-700 text-sm disabled:opacity-50"
          >
            Copy
          </button>
          <button
            type="button"
            onClick={handleDeleteDocuments}
            disabled={(selectedDocIds.size === 0 && !currentDocId) || isDeleting}
            className="bg-red-600 text-white py-2 px-3 rounded-md hover:bg-red-700 text-sm disabled:opacity-50"
          >
            {isDeleting ? 'Deleting...' : 'Delete'}
          </button>
          <button
            type="button"
            onClick={handleDiff}
            disabled={selectedDocIds.size !== 2 || isDiffing}
            className="bg-gray-800 text-white py-2 px-3 rounded-md hover:bg-gray-900 text-sm disabled:opacity-50"
          >
            {isDiffing ? 'Comparing...' : 'Diff'}
          </button>
        </div>

        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={handleToggleSelectAll}
            className="text-xs text-blue-600 hover:text-blue-800"
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
          className="w-full px-3 py-1.5 border border-gray-300 rounded-md text-sm"
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
                  className={`flex items-center gap-2 px-4 py-3 hover:bg-gray-50 border-l-4 transition-colors ${
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
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 w-96">
            <h2 className="text-xl font-bold mb-4">Create Project</h2>
            <form onSubmit={handleCreateProject}>
              <input
                type="text"
                value={newProjectName}
                onChange={(event) => setNewProjectName(event.target.value)}
                placeholder="Project name..."
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm mb-4"
                disabled={isCreating}
                autoFocus
              />
              <div className="flex gap-2 justify-end">
                <button
                  type="button"
                  onClick={() => setShowNewProjectModal(false)}
                  className="px-4 py-2 text-sm text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isCreating || !newProjectName.trim()}
                  className="px-4 py-2 text-sm text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50"
                >
                  {isCreating ? 'Creating...' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showNewDocModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 w-96">
            <h2 className="text-xl font-bold mb-4">Create Document</h2>
            <form onSubmit={handleCreateDocument}>
              <input
                type="text"
                value={newDocName}
                onChange={(event) => setNewDocName(event.target.value)}
                placeholder="Document name..."
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm mb-4"
                disabled={isCreating}
                autoFocus
              />
              <div className="flex gap-2 justify-end">
                <button
                  type="button"
                  onClick={() => setShowNewDocModal(false)}
                  className="px-4 py-2 text-sm text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isCreating || !newDocName.trim() || !currentProjectId}
                  className="px-4 py-2 text-sm text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50"
                >
                  {isCreating ? 'Creating...' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {diffResult && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-4xl max-h-[80vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold">
                Diff: {diffResult.left_name} vs {diffResult.right_name}
              </h2>
              <button
                type="button"
                onClick={() => setDiffResult(null)}
                className="text-gray-500 hover:text-gray-800"
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
