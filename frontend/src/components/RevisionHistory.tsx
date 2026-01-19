import { useEffect, useState } from 'react'
import { apiClient } from '../lib/apiClient'
import { useDocumentsStore } from '../stores/useDocumentsStore'
import type { RevisionListResponse, Revision } from '../types/api'
import { extractField } from '../lib/utils'

interface RevisionHistoryProps {
  documentId: string
  onClose: () => void
}

export default function RevisionHistory({
  documentId,
  onClose,
}: RevisionHistoryProps) {
  const [revisions, setRevisions] = useState<Revision[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isRestoring, setIsRestoring] = useState(false)

  const { fetchDocument } = useDocumentsStore()

  useEffect(() => {
    fetchRevisions()
  }, [documentId])

  const fetchRevisions = async () => {
    setIsLoading(true)
    setError(null)

    const response = await apiClient.get<RevisionListResponse>(
      `/documents/${documentId}/revisions`
    )

    if (!response.ok) {
      setError(response.errorMessage || 'Failed to fetch revisions')
      setIsLoading(false)
      return
    }

    const revisionList = extractField<Revision[]>(
      response.data as Record<string, unknown>,
      'items',
      'revisions',
      'data'
    )

    setRevisions(revisionList || [])
    setIsLoading(false)
  }

  const handleRestore = async (revisionId: string) => {
    if (
      !confirm(
        'Are you sure you want to restore this revision? This will create a new revision with the old content.'
      )
    ) {
      return
    }

    setIsRestoring(true)
    setError(null)

    const response = await apiClient.post(
      `/documents/${documentId}/revisions/${revisionId}/restore`
    )

    if (!response.ok) {
      setError(response.errorMessage || 'Failed to restore revision')
      setIsRestoring(false)
      return
    }

    // Refetch document to get updated content
    await fetchDocument(documentId)
    setIsRestoring(false)
    onClose()
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="p-6 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-bold text-gray-900">
              Revision History
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
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {isLoading && (
            <div className="text-center text-gray-500">
              Loading revisions...
            </div>
          )}

          {error && (
            <div className="p-4 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
              {error}
            </div>
          )}

          {!isLoading && !error && revisions.length === 0 && (
            <div className="text-center text-gray-500">No revisions yet</div>
          )}

          {!isLoading && revisions.length > 0 && (
            <div className="space-y-3">
              {revisions.map((revision) => (
                <div
                  key={revision.id}
                  className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-medium text-gray-900">
                        Revision #{revision.rev_number}
                      </div>
                      <div className="text-sm text-gray-500 mt-1">
                        {new Date(revision.created_at).toLocaleString()}
                      </div>
                      {revision.device_id && (
                        <div className="text-xs text-gray-400 mt-1">
                          Device: {revision.device_id.substring(0, 8)}...
                        </div>
                      )}
                    </div>

                    <button
                      onClick={() => handleRestore(revision.id)}
                      disabled={isRestoring}
                      className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Restore
                    </button>
                  </div>
                </div>
              ))}
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
