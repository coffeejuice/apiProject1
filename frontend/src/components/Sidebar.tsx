import { useState } from 'react'
import { useDocumentsStore } from '../stores/useDocumentsStore'
import { useSessionStore } from '../stores/useSessionStore'
import SearchBar from './SearchBar'

export default function Sidebar() {
  const [newDocTitle, setNewDocTitle] = useState('')
  const [isCreating, setIsCreating] = useState(false)

  const { documents, currentDocId, setCurrentDoc, createDocument, isLoading } =
    useDocumentsStore()
  const { user, logout } = useSessionStore()

  const handleCreateDocument = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newDocTitle.trim()) return

    setIsCreating(true)
    const doc = await createDocument(newDocTitle.trim())
    setIsCreating(false)

    if (doc) {
      setNewDocTitle('')
      setCurrentDoc(doc.id)
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

      {/* Search */}
      <div className="p-4 border-b border-gray-200">
        <SearchBar />
      </div>

      {/* Create Document */}
      <div className="p-4 border-b border-gray-200">
        <form onSubmit={handleCreateDocument} className="space-y-2">
          <input
            type="text"
            value={newDocTitle}
            onChange={(e) => setNewDocTitle(e.target.value)}
            placeholder="New document title..."
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            disabled={isCreating}
          />
          <button
            type="submit"
            disabled={isCreating || !newDocTitle.trim()}
            className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isCreating ? 'Creating...' : '+ Create Document'}
          </button>
        </form>
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
            {documents.map((doc) => (
              <button
                key={doc.id}
                onClick={() => setCurrentDoc(doc.id)}
                className={`w-full text-left px-4 py-3 hover:bg-gray-50 border-l-4 transition-colors ${
                  currentDocId === doc.id
                    ? 'border-blue-600 bg-blue-50'
                    : 'border-transparent'
                }`}
              >
                <div className="font-medium text-gray-900 truncate">
                  {doc.title || 'Untitled'}
                </div>
                {doc.updated_at && (
                  <div className="text-xs text-gray-500 mt-1">
                    {new Date(doc.updated_at).toLocaleDateString()}
                  </div>
                )}
              </button>
            ))}
          </div>
        )}
      </div>
    </aside>
  )
}
