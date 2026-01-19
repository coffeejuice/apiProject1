import { useEffect } from 'react'
import { useDocumentsStore } from '../stores/useDocumentsStore'
import Sidebar from '../components/Sidebar'
import Editor from '../components/Editor'

export default function AppPage() {
  const { currentDocId, fetchDocuments } = useDocumentsStore()

  useEffect(() => {
    fetchDocuments()
  }, [fetchDocuments])

  return (
    <div className="flex h-screen bg-gray-50">
      <Sidebar />
      <main className="flex-1 overflow-hidden">
        {currentDocId ? (
          <Editor />
        ) : (
          <div className="flex items-center justify-center h-full">
            <div className="text-center text-gray-500">
              <p className="text-xl mb-2">Select a document to start editing</p>
              <p className="text-sm">or create a new one from the sidebar</p>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
