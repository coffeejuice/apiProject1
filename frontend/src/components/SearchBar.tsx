import { useState } from 'react'
import { apiClient } from '../lib/apiClient'
import { useDocumentsStore } from '../stores/useDocumentsStore'
import type { SearchResponse, SearchResult } from '../types/api'

export default function SearchBar() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [isSearching, setIsSearching] = useState(false)
  const [showResults, setShowResults] = useState(false)

  const { setCurrentDoc, documents } = useDocumentsStore()

  const handleSearch = async (searchQuery: string) => {
    if (!searchQuery.trim()) {
      setResults([])
      setShowResults(false)
      return
    }

    setIsSearching(true)

    const response = await apiClient.get<SearchResponse>('/search', {
      params: { q: searchQuery },
    })

    if (response.ok && response.data) {
      setResults(response.data.results || [])
      setShowResults(true)
    } else {
      setResults([])
    }

    setIsSearching(false)
  }

  const handleInputChange = (value: string) => {
    setQuery(value)

    // Debounce search
    const timeoutId = setTimeout(() => {
      handleSearch(value)
    }, 300)

    return () => clearTimeout(timeoutId)
  }

  const handleSelectResult = (documentId: number) => {
    setCurrentDoc(String(documentId))
    setShowResults(false)
    setQuery('')
    setResults([])
  }

  const getDocumentTitle = (documentId: number): string => {
    const doc = documents.find((d) => d.id === String(documentId))
    return doc?.name || `Document #${documentId}`
  }

  return (
    <div className="relative">
      <div className="relative">
        <input
          type="text"
          value={query}
          onChange={(e) => handleInputChange(e.target.value)}
          placeholder="Search documents..."
          className="w-full px-3 py-2 pl-9 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <svg
          className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
          />
        </svg>
        {isSearching && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2">
            <div className="animate-spin h-4 w-4 border-2 border-blue-600 border-t-transparent rounded-full"></div>
          </div>
        )}
      </div>

      {/* Search Results Dropdown */}
      {showResults && results.length > 0 && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-md shadow-lg max-h-64 overflow-y-auto z-10">
          {results.map((result) => (
            <button
              key={result.block_id}
              onClick={() => handleSelectResult(result.document_id)}
              className="w-full text-left px-3 py-2 hover:bg-gray-50 border-b border-gray-100 last:border-b-0"
            >
              <div className="font-medium text-sm text-gray-900">
                {getDocumentTitle(result.document_id)}
              </div>
              <div className="text-xs text-gray-500 mt-1 line-clamp-2">
                {result.snippet}
              </div>
              <div className="text-xs text-gray-400 mt-1">
                {result.block_type_id}
              </div>
            </button>
          ))}
        </div>
      )}

      {showResults && results.length === 0 && query && !isSearching && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-md shadow-lg p-3 text-sm text-gray-500 text-center z-10">
          No results found
        </div>
      )}
    </div>
  )
}
