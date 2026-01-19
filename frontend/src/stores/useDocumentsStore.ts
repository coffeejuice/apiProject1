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

  fetchDocuments: () => Promise<void>
  createDocument: (title: string) => Promise<Document | null>
  fetchDocument: (id: string) => Promise<Document | null>
  setCurrentDoc: (id: string | null) => void
  updateLocalDoc: (id: string, updates: Partial<Document>) => void
  updateDocument: (id: string | number, updates: Partial<Document>) => Promise<boolean>
}

export const useDocumentsStore = create<DocumentsState>((set, get) => ({
  documents: [],
  currentDocId: null,
  currentDoc: null,
  isLoading: false,
  error: null,

  fetchDocuments: async () => {
    set({ isLoading: true, error: null })

    const response = await apiClient.get<DocumentListResponse>('/documents', {
      params: { limit: 100 },
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

    // Normalize documents: map process_id to id if needed
    const normalizedDocs = (documents || []).map((doc) => ({
      ...doc,
      id: doc.id || doc.process_id || '',
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
      id: response.data!.id || response.data!.process_id || '',
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
      id: response.data!.id || response.data!.process_id || '',
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
    const response = await apiClient.patch(`/documents/${id}`, {
      body: updates,
    })

    if (!response.ok) {
      console.error('Failed to update document:', response.errorMessage)
      return false
    }

    // Update local state
    const normalizedDoc = {
      ...response.data,
      id: response.data?.id || response.data?.process_id || id,
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
}))
