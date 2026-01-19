import { useState } from 'react'
import { apiClient } from '../lib/apiClient'
import { useDocumentsStore } from '../stores/useDocumentsStore'
import type { ImportRequest } from '../types/api'

interface ImportExportProps {
  documentId: string
  onClose: () => void
}

export default function ImportExport({
  documentId,
  onClose,
}: ImportExportProps) {
  const [activeTab, setActiveTab] = useState<'export' | 'import'>('export')
  const [importTitle, setImportTitle] = useState('')
  const [importContent, setImportContent] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const { fetchDocuments } = useDocumentsStore()

  const handleExport = async () => {
    setIsLoading(true)
    setError(null)

    try {
      const response = await fetch(
        `${apiClient.getBaseUrl()}/documents/${documentId}/export?format=markdown`,
        {
          headers: {
            Authorization: `Bearer ${apiClient.getToken()}`,
          },
        }
      )

      if (!response.ok) {
        throw new Error('Failed to export document')
      }

      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `document-${documentId}.md`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)

      setSuccess('Document exported successfully!')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed')
    } finally {
      setIsLoading(false)
    }
  }

  const handleImport = async () => {
    if (!importTitle.trim() || !importContent.trim()) {
      setError('Please provide both title and content')
      return
    }

    setIsLoading(true)
    setError(null)

    const response = await apiClient.post('/documents/import', {
      params: { format: 'markdown' },
      body: {
        title: importTitle.trim(),
        content_markdown: importContent.trim(),
      } as ImportRequest,
    })

    if (!response.ok) {
      setError(response.errorMessage || 'Failed to import document')
      setIsLoading(false)
      return
    }

    setSuccess('Document imported successfully!')
    setImportTitle('')
    setImportContent('')
    await fetchDocuments()
    setIsLoading(false)

    // Close after short delay
    setTimeout(() => {
      onClose()
    }, 1500)
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="p-6 border-b border-gray-200">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-2xl font-bold text-gray-900">
              Import / Export
            </h2>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600"
            >
              <svg
                className="w-6 h-6"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </div>

          {/* Tabs */}
          <div className="flex gap-4 border-b border-gray-200">
            <button
              onClick={() => setActiveTab('export')}
              className={`pb-2 px-1 ${
                activeTab === 'export'
                  ? 'border-b-2 border-blue-600 text-blue-600 font-medium'
                  : 'text-gray-600'
              }`}
            >
              Export
            </button>
            <button
              onClick={() => setActiveTab('import')}
              className={`pb-2 px-1 ${
                activeTab === 'import'
                  ? 'border-b-2 border-blue-600 text-blue-600 font-medium'
                  : 'text-gray-600'
              }`}
            >
              Import
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {error && (
            <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
              {error}
            </div>
          )}

          {success && (
            <div className="mb-4 p-4 bg-green-50 border border-green-200 rounded text-green-700 text-sm">
              {success}
            </div>
          )}

          {activeTab === 'export' && (
            <div className="space-y-4">
              <p className="text-gray-600">
                Export this document as a Markdown file.
              </p>
              <button
                onClick={handleExport}
                disabled={isLoading}
                className="w-full px-4 py-3 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isLoading ? 'Exporting...' : 'Export as Markdown'}
              </button>
            </div>
          )}

          {activeTab === 'import' && (
            <div className="space-y-4">
              <p className="text-gray-600">
                Import a new document from Markdown content.
              </p>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Document Title
                </label>
                <input
                  type="text"
                  value={importTitle}
                  onChange={(e) => setImportTitle(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="My New Document"
                  disabled={isLoading}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Markdown Content
                </label>
                <textarea
                  value={importContent}
                  onChange={(e) => setImportContent(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
                  rows={10}
                  placeholder="# My Document&#10;&#10;This is **bold** text..."
                  disabled={isLoading}
                />
              </div>

              <button
                onClick={handleImport}
                disabled={isLoading || !importTitle.trim() || !importContent.trim()}
                className="w-full px-4 py-3 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isLoading ? 'Importing...' : 'Import Document'}
              </button>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-gray-200">
          <button
            onClick={onClose}
            className="w-full px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
