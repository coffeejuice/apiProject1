import { create } from 'zustand'
import { apiClient } from '../lib/apiClient'
import type {
  Document,
  DocumentListResponse,
  CreateDocumentRequest,
} from '../types/api'
import { extractField } from '../lib/utils'

interface DocumentsState {
  documents: Document[]
  currentDocId: string | null
  currentDoc: Document | null
  isLoading: boolean
  error: string | null
  showDeleted: boolean
  selectedDocIds: Set<string>

  fetchDocuments: () => Promise<void>
  createDocument: (title: string) => Promise<Document | null>
  fetchDocument: (id: string) => Promise<Document | null>
  setCurrentDoc: (id: string | null) => void
  updateLocalDoc: (id: string, updates: Partial<Document>) => void
  updateDocument: (id: string | number, updates: Partial<Document>) => Promise<boolean>
  deleteDocument: (id: string | number) => Promise<boolean>
  deleteMultipleDocuments: (ids: string[]) => Promise<void>
  setShowDeleted: (show: boolean) => void
  toggleDocSelection: (id: string) => void
  clearSelection: () => void
  selectAll: (docIds: string[]) => void
}

export const useDocumentsStore = create<DocumentsState>((set, get) => ({
  documents: [],
  currentDocId: null,
  currentDoc: null,
  isLoading: false,
  error: null,
  showDeleted: false,
  selectedDocIds: new Set<string>(),

  fetchDocuments: async () => {
    set({ isLoading: true, error: null })

    const { showDeleted } = get()

    const response = await apiClient.get<DocumentListResponse>('/documents', {
      params: {
        limit: 100,
        include_deleted: showDeleted,
      },
    })

    if (!response.ok) {
      set({
        isLoading: false,
        error: response.errorMessage || 'Failed to fetch documents',
      })
      return
    }

    // Extract documents array (tolerant)
    const documents = extractField<Document[]>(
      response.data as Record<string, unknown>,
      'items',
      'documents',
      'data'
    )

    // Normalize documents: map document_id to id if needed
    const normalizedDocs = (documents || []).map((doc) => ({
      ...doc,
      id: doc.id || doc.document_id || '',
    }))

    set({
      documents: normalizedDocs,
      isLoading: false,
      error: null,
    })
  },

  createDocument: async (title: string) => {
    set({ isLoading: true, error: null })

    const response = await apiClient.post<Document>('/documents', {
      body: { title } as CreateDocumentRequest,
    })

    if (!response.ok) {
      set({
        isLoading: false,
        error: response.errorMessage || 'Failed to create document',
      })
      return null
    }

    const newDoc = {
      ...response.data!,
      id: response.data!.id || response.data!.document_id || '',
    }

    set((state) => ({
      documents: [newDoc, ...state.documents],
      isLoading: false,
      error: null,
    }))

    return newDoc
  },

  fetchDocument: async (id: string) => {
    set({ isLoading: true, error: null })

    const response = await apiClient.get<Document>(`/documents/${id}`)

    if (!response.ok) {
      set({
        isLoading: false,
        error: response.errorMessage || 'Failed to fetch document',
      })
      return null
    }

    const doc = {
      ...response.data!,
      id: response.data!.id || response.data!.document_id || '',
    }

    set({
      currentDoc: doc,
      currentDocId: String(doc.id),
      isLoading: false,
      error: null,
    })

    return doc
  },

  setCurrentDoc: (id: string | null) => {
    if (id === null) {
      set({ currentDocId: null, currentDoc: null })
      return
    }

    const doc = get().documents.find((d) => d.id === id)
    if (doc) {
      set({ currentDocId: id, currentDoc: doc })
    } else {
      get().fetchDocument(id)
    }
  },

  updateLocalDoc: (id: string, updates: Partial<Document>) => {
    set((state) => ({
      documents: state.documents.map((doc) =>
        doc.id === id ? { ...doc, ...updates } : doc
      ),
      currentDoc:
        state.currentDoc?.id === id
          ? { ...state.currentDoc, ...updates }
          : state.currentDoc,
    }))
  },

  updateDocument: async (id: string | number, updates: Partial<Document>) => {
    const response = await apiClient.patch<Document>(`/documents/${id}`, {
      body: updates,
    })

    if (!response.ok || !response.data) {
      console.error('Failed to update document:', response.errorMessage)
      return false
    }

    // Update local state
    const normalizedDoc = {
      ...response.data,
      id: response.data?.id || response.data?.document_id || id,
    }

    set((state) => ({
      documents: state.documents.map((doc) =>
        doc.id === id ? { ...doc, ...normalizedDoc } : doc
      ),
      currentDoc:
        state.currentDoc?.id === id
          ? { ...state.currentDoc, ...normalizedDoc }
          : state.currentDoc,
    }))

    return true
  },

  deleteDocument: async (id: string | number) => {
    const response = await apiClient.delete(`/documents/${id}`)

    if (!response.ok) {
      console.error('Failed to delete document:', response.errorMessage)
      return false
    }

    // Clear current doc if it was deleted
    const state = get()
    if (state.currentDocId === String(id)) {
      set({ currentDoc: null, currentDocId: null })
    }

    // Refetch documents from backend
    await get().fetchDocuments()

    return true
  },

  setShowDeleted: (show: boolean) => {
    set({ showDeleted: show })
    // Refetch documents with new filter
    get().fetchDocuments()
  },

  deleteMultipleDocuments: async (ids: string[]) => {
    // Send all delete requests
    const promises = ids.map((id) =>
      apiClient.delete(`/documents/${id}`)
    )
    const results = await Promise.all(promises)

    // Check if all succeeded
    const allSucceeded = results.every((r) => r.ok)
    if (!allSucceeded) {
      console.error('Some documents failed to delete')
    }

    // Clear selection
    set({ selectedDocIds: new Set<string>() })

    // Clear current doc if it was deleted
    const state = get()
    if (state.currentDocId && ids.includes(String(state.currentDocId))) {
      set({ currentDoc: null, currentDocId: null })
    }

    // Refetch documents from backend
    await get().fetchDocuments()
  },

  toggleDocSelection: (id: string) => {
    set((state) => {
      const newSelection = new Set(state.selectedDocIds)
      if (newSelection.has(id)) {
        newSelection.delete(id)
      } else {
        newSelection.add(id)
      }
      return { selectedDocIds: newSelection }
    })
  },

  clearSelection: () => {
    set({ selectedDocIds: new Set<string>() })
  },

  selectAll: (docIds: string[]) => {
    set({ selectedDocIds: new Set(docIds) })
  },
}))
