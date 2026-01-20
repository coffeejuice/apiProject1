import { useState } from 'react'
import { useDocumentsStore } from '../stores/useDocumentsStore'
import { useSessionStore } from '../stores/useSessionStore'

export default function Sidebar() {
  const [newDocTitle, setNewDocTitle] = useState('')
  const [isCreating, setIsCreating] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [showNewDocModal, setShowNewDocModal] = useState(false)
  const [filterText, setFilterText] = useState('')

  const {
    documents: allDocuments,
    currentDocId,
    setCurrentDoc,
    createDocument,
    deleteMultipleDocuments,
    isLoading,
    showDeleted,
    setShowDeleted,
    selectedDocIds,
    toggleDocSelection,
    clearSelection,
    selectAll,
  } = useDocumentsStore()
  const { user, logout } = useSessionStore()

  // Filter documents by title
  const documents = allDocuments.filter((doc) =>
    doc.title.toLowerCase().includes(filterText.toLowerCase())
  )

  const handleCreateDocument = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newDocTitle.trim()) return

    setIsCreating(true)
    const doc = await createDocument(newDocTitle.trim())
    setIsCreating(false)

    if (doc) {
      setNewDocTitle('')
      setShowNewDocModal(false)
      setCurrentDoc(doc.id)
    }
  }

  const handleOpenNewDocModal = () => {
    setNewDocTitle('')
    setShowNewDocModal(true)
  }

  const handleDeleteDocuments = async () => {
    const idsToDelete = selectedDocIds.size > 0
      ? Array.from(selectedDocIds)
      : currentDocId
        ? [currentDocId]
        : []

    if (idsToDelete.length === 0) return

    const message =
      idsToDelete.length === 1
        ? 'Are you sure you want to delete this document?'
        : `Are you sure you want to delete ${idsToDelete.length} documents?`

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

  return (
    <aside className="w-80 bg-white border-r border-gray-200 flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-gray-200">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-xl font-bold text-gray-900">Techno-Notion</h1>
          <button
            onClick={logout}
            className="text-sm text-gray-600 hover:text-gray-900"
            title="Logout"
          >
            Logout
          </button>
        </div>

        {user && (
          <div className="text-sm text-gray-600">
            {user.username || user.login || user.email}
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="p-4 border-b border-gray-200">
        <div className="space-y-2">
          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleOpenNewDocModal}
              className="flex-1 bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 text-sm"
            >
              New
            </button>
            <button
              type="button"
              onClick={handleDeleteDocuments}
              disabled={(selectedDocIds.size === 0 && !currentDocId) || isDeleting}
              className="flex-1 bg-red-600 text-white py-2 px-4 rounded-md hover:bg-red-700 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isDeleting
                ? 'Deleting...'
                : selectedDocIds.size > 0
                  ? `Delete (${selectedDocIds.size})`
                  : 'Delete'}
            </button>
          </div>
          <div className="space-y-2 pt-1">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="show-deleted"
                  checked={showDeleted}
                  onChange={(e) => setShowDeleted(e.target.checked)}
                  className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                />
                <label
                  htmlFor="show-deleted"
                  className="text-sm text-gray-700 cursor-pointer select-none"
                >
                  Show deleted
                </label>
              </div>
              <button
                type="button"
                onClick={handleToggleSelectAll}
                className="text-xs text-blue-600 hover:text-blue-800"
              >
                {selectedDocIds.size === documents.length && documents.length > 0
                  ? 'Deselect all'
                  : 'Select all'}
              </button>
            </div>
            <input
              type="text"
              value={filterText}
              onChange={(e) => setFilterText(e.target.value)}
              placeholder="Filter by title..."
              className="w-full px-3 py-1.5 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
      </div>

      {/* Documents List */}
      <div className="flex-1 overflow-y-auto">
        {isLoading && documents.length === 0 ? (
          <div className="p-4 text-center text-gray-500 text-sm">
            Loading documents...
          </div>
        ) : documents.length === 0 ? (
          <div className="p-4 text-center text-gray-500 text-sm">
            No documents yet. Create your first one!
          </div>
        ) : (
          <div className="py-2">
            {documents.map((doc) => {
              const docId = String(doc.id)
              const isSelected = selectedDocIds.has(docId)
              return (
                <div
                  key={doc.id}
                  className={`flex items-center gap-2 px-4 py-3 hover:bg-gray-50 border-l-4 transition-colors ${
                    currentDocId === doc.id
                      ? 'border-blue-600 bg-blue-50'
                      : 'border-transparent'
                  } ${doc.deleted_at ? 'opacity-50' : ''}`}
                >
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={(e) => {
                      e.stopPropagation()
                      toggleDocSelection(docId)
                    }}
                    className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500 flex-shrink-0"
                  />
                  <button
                    onClick={() => setCurrentDoc(doc.id)}
                    className="flex-1 text-left"
                  >
                    <div className="font-medium text-gray-900 truncate">
                      {doc.title || 'Untitled'}
                      {doc.deleted_at && (
                        <span className="ml-2 text-xs text-red-600">(Deleted)</span>
                      )}
                    </div>
                    {doc.updated_at && (
                      <div className="text-xs text-gray-500 mt-1">
                        {new Date(doc.updated_at).toLocaleDateString()}
                      </div>
                    )}
                  </button>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* New Document Modal */}
      {showNewDocModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 w-96">
            <h2 className="text-xl font-bold mb-4">Create New Document</h2>
            <form onSubmit={handleCreateDocument}>
              <input
                type="text"
                value={newDocTitle}
                onChange={(e) => setNewDocTitle(e.target.value)}
                placeholder="Document title..."
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 mb-4"
                disabled={isCreating}
                autoFocus
              />
              <div className="flex gap-2 justify-end">
                <button
                  type="button"
                  onClick={() => setShowNewDocModal(false)}
                  disabled={isCreating}
                  className="px-4 py-2 text-sm text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isCreating || !newDocTitle.trim()}
                  className="px-4 py-2 text-sm text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isCreating ? 'Creating...' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </aside>
  )
}
