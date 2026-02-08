import { useEffect } from 'react'
import { useDocumentsStore } from '../stores/useDocumentsStore'
import Sidebar from '../components/Sidebar'
import BlockEditor from '../components/BlockEditor'

export default function AppPage() {
  const { fetchDocuments } = useDocumentsStore()

  useEffect(() => {
    fetchDocuments()
  }, [fetchDocuments])

  // Initialize block components
  useEffect(() => {
    import('../components/blocks')
  }, [])

  return (
    <div className="flex h-screen bg-gray-50">
      <Sidebar />
      <main className="flex-1 overflow-hidden">
        <BlockEditor />
      </main>
    </div>
  )
}
