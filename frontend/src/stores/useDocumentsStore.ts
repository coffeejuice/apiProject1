import { create } from 'zustand'
import { apiClient } from '../lib/apiClient'
import type {
  CreateDocumentRequest,
  CreateProjectRequest,
  Document,
  DocumentDiffResponse,
  DocumentListResponse,
  Project,
  ProjectListResponse,
} from '../types/api'
import { extractField } from '../lib/utils'

interface DocumentsState {
  projects: Project[]
  currentProjectId: string | null
  documents: Document[]
  currentDocId: string | null
  currentDoc: Document | null
  isLoading: boolean
  error: string | null
  showDeleted: boolean
  selectedDocIds: Set<string>
  documentSelectionInitialized: boolean

  fetchProjects: () => Promise<void>
  createProject: (name: string, notes?: string) => Promise<Project | null>
  deleteProject: (id: string) => Promise<boolean>
  setCurrentProject: (id: string | null) => void

  fetchDocuments: (projectId?: string | null) => Promise<void>
  restoreDocumentContext: (projectId: string | null, documentId: string) => Promise<boolean>
  createDocument: (name: string, notes?: string, sourceDocumentId?: string) => Promise<Document | null>
  copyDocument: (id: string, name?: string) => Promise<Document | null>
  fetchDocument: (id: string) => Promise<Document | null>
  setCurrentDoc: (id: string | null) => void
  updateLocalDoc: (id: string, updates: Partial<Document>) => void
  updateDocument: (id: string, updates: Partial<Document>) => Promise<boolean>
  deleteDocument: (id: string) => Promise<boolean>
  deleteMultipleDocuments: (ids: string[]) => Promise<boolean>
  getDiff: (leftId: string, rightId: string) => Promise<DocumentDiffResponse | null>

  setShowDeleted: (show: boolean) => void
  initializeDocumentSelection: () => void
  toggleDocSelection: (id: string) => void
  clearSelection: () => void
  selectAll: (docIds: string[]) => void
}

function normalizeProject(project: Partial<Project>): Project {
  const id = String(project.id || project.project_id || '')
  return {
    ...project,
    id,
    project_id: project.project_id ?? (id ? Number(id) : undefined),
    user_id: project.user_id ?? 0,
    name: project.name || '',
  } as Project
}

function normalizeDocument(document: Partial<Document>): Document {
  const id = String(document.id || document.document_id || '')
  return {
    ...document,
    id,
    document_id: document.document_id ?? (id ? Number(id) : undefined),
    project_id: document.project_id ?? 0,
    name: document.name || '',
  } as Document
}

function syncDocumentSelection(
  documents: Document[],
  requestedSelection: Iterable<string>,
): {
  selectedDocIds: Set<string>
  currentDocId: string | null
  currentDoc: Document | null
} {
  const documentIds = new Set(documents.map((document) => document.id))
  const selectedDocIds = new Set(
    Array.from(requestedSelection)
      .map((id) => String(id))
      .filter((id) => documentIds.has(id))
  )
  const selectedIds = Array.from(selectedDocIds)
  const currentDocId = selectedIds.length === 1 ? selectedIds[0] : null
  const currentDoc = currentDocId
    ? documents.find((document) => document.id === currentDocId) || null
    : null

  return { selectedDocIds, currentDocId, currentDoc }
}

export const useDocumentsStore = create<DocumentsState>((set, get) => ({
  projects: [],
  currentProjectId: null,
  documents: [],
  currentDocId: null,
  currentDoc: null,
  isLoading: false,
  error: null,
  showDeleted: false,
  selectedDocIds: new Set<string>(),
  documentSelectionInitialized: false,

  fetchProjects: async () => {
    set({ isLoading: true, error: null })
    const response = await apiClient.get<ProjectListResponse>('/projects')

    if (!response.ok) {
      set({
        isLoading: false,
        error: response.errorMessage || 'Failed to fetch projects',
      })
      return
    }

    const projects = extractField<Project[]>(
      response.data as Record<string, unknown>,
      'projects',
      'items',
      'data'
    ) || []

    const normalized = projects.map((project) => normalizeProject(project))
    const state = get()
    const nextProjectId =
      state.currentProjectId && normalized.some((project) => project.id === state.currentProjectId)
        ? state.currentProjectId
        : normalized[0]?.id || null

    set({
      projects: normalized,
      currentProjectId: nextProjectId,
      isLoading: false,
      error: null,
    })

    if (nextProjectId) {
      await get().fetchDocuments(nextProjectId)
    } else {
      set({
        documents: [],
        currentDoc: null,
        currentDocId: null,
        selectedDocIds: new Set<string>(),
        documentSelectionInitialized: false,
      })
    }
  },

  createProject: async (name: string, notes?: string) => {
    set({ isLoading: true, error: null })
    const payload: CreateProjectRequest = { name, notes }

    const response = await apiClient.post<Project>('/projects', { body: payload })
    if (!response.ok || !response.data) {
      set({
        isLoading: false,
        error: response.errorMessage || 'Failed to create project',
      })
      return null
    }

    const project = normalizeProject(response.data)
    set((state) => ({
      projects: [project, ...state.projects],
      currentProjectId: project.id,
      documents: [],
      currentDocId: null,
      currentDoc: null,
      selectedDocIds: new Set<string>(),
      documentSelectionInitialized: false,
      isLoading: false,
      error: null,
    }))
    await get().fetchDocuments(project.id)
    return project
  },

  deleteProject: async (id: string) => {
    const response = await apiClient.delete(`/projects/${id}`)
    if (!response.ok) {
      set({ error: response.errorMessage || 'Failed to delete project' })
      return false
    }

    const remainingProjects = get().projects.filter((project) => project.id !== id)
    const nextProjectId = remainingProjects[0]?.id || null
    set({
      projects: remainingProjects,
      currentProjectId: nextProjectId,
      documents: [],
      currentDocId: null,
      currentDoc: null,
      selectedDocIds: new Set<string>(),
      documentSelectionInitialized: false,
      error: null,
    })

    if (nextProjectId) {
      await get().fetchDocuments(nextProjectId)
    }
    return true
  },

  setCurrentProject: (id: string | null) => {
    set({
      currentProjectId: id,
      documents: [],
      currentDocId: null,
      currentDoc: null,
      selectedDocIds: new Set<string>(),
      documentSelectionInitialized: false,
    })
    if (id) {
      get().fetchDocuments(id)
    }
  },

  fetchDocuments: async (projectId?: string | null) => {
    const targetProjectId = projectId ?? get().currentProjectId
    if (!targetProjectId) {
      set({
        documents: [],
        currentDoc: null,
        currentDocId: null,
        selectedDocIds: new Set<string>(),
        documentSelectionInitialized: false,
      })
      return
    }

    set({ isLoading: true, error: null })
    const response = await apiClient.get<DocumentListResponse>(`/projects/${targetProjectId}/documents`, {
      params: { include_deleted: get().showDeleted },
    })

    if (!response.ok) {
      set({
        isLoading: false,
        error: response.errorMessage || 'Failed to fetch documents',
      })
      return
    }

    const documents = extractField<Document[]>(
      response.data as Record<string, unknown>,
      'documents',
      'items',
      'data'
    ) || []

    const normalized = documents.map((document) => normalizeDocument(document))
    const state = get()
    const requestedSelection = state.selectedDocIds.size > 0
      ? state.selectedDocIds
      : state.currentDocId
        ? [state.currentDocId]
        : []
    const selection = syncDocumentSelection(normalized, requestedSelection)

    set({
      documents: normalized,
      ...selection,
      isLoading: false,
      error: null,
    })
  },

  restoreDocumentContext: async (projectId: string | null, documentId: string) => {
    const normalizedDocumentId = String(documentId)
    const normalizedProjectId = projectId ? String(projectId) : null

    if (normalizedProjectId) {
      set({
        currentProjectId: normalizedProjectId,
        currentDocId: normalizedDocumentId,
        currentDoc: null,
        selectedDocIds: new Set<string>([normalizedDocumentId]),
        documentSelectionInitialized: true,
      })

      await get().fetchDocuments(normalizedProjectId)

      const state = get()
      if (state.currentDocId === normalizedDocumentId && state.currentDoc) {
        return true
      }
    }

    const fetched = await get().fetchDocument(normalizedDocumentId)
    if (!fetched) {
      return false
    }

    set({
      currentProjectId: String(fetched.project_id),
      currentDoc: fetched,
      currentDocId: fetched.id,
      selectedDocIds: new Set<string>([fetched.id]),
      documentSelectionInitialized: true,
    })
    return true
  },

  createDocument: async (name: string, notes?: string, sourceDocumentId?: string) => {
    const projectId = get().currentProjectId
    if (!projectId) {
      set({ error: 'Select a project first' })
      return null
    }

    set({ isLoading: true, error: null })
    const payload: CreateDocumentRequest = {
      project_id: Number(projectId),
      name,
      notes,
      source_document_id: sourceDocumentId ? Number(sourceDocumentId) : undefined,
    }

    const response = await apiClient.post<Document>('/documents', { body: payload })
    if (!response.ok || !response.data) {
      set({
        isLoading: false,
        error: response.errorMessage || 'Failed to create document',
      })
      return null
    }

    const document = normalizeDocument(response.data)
    set((state) => ({
      documents: [document, ...state.documents],
      currentDoc: document,
      currentDocId: document.id,
      selectedDocIds: new Set<string>([document.id]),
      documentSelectionInitialized: true,
      isLoading: false,
      error: null,
    }))
    return document
  },

  copyDocument: async (id: string, name?: string) => {
    const response = await apiClient.post<Document>(`/documents/${id}/copy`, {
      body: { name },
    })
    if (!response.ok || !response.data) {
      set({ error: response.errorMessage || 'Failed to copy document' })
      return null
    }

    const copied = normalizeDocument(response.data)
    set((state) => ({
      documents: [copied, ...state.documents],
      currentDoc: copied,
      currentDocId: copied.id,
      selectedDocIds: new Set<string>([copied.id]),
      documentSelectionInitialized: true,
      error: null,
    }))
    return copied
  },

  fetchDocument: async (id: string) => {
    set({ isLoading: true, error: null })
    const response = await apiClient.get<Document>(`/documents/${id}`)

    if (!response.ok || !response.data) {
      set({
        isLoading: false,
        error: response.errorMessage || 'Failed to fetch document',
      })
      return null
    }

    const document = normalizeDocument(response.data)
    set({
      currentDoc: document,
      currentDocId: document.id,
      selectedDocIds: new Set<string>([document.id]),
      documentSelectionInitialized: true,
      isLoading: false,
      error: null,
    })
    return document
  },

  setCurrentDoc: (id: string | null) => {
    if (id === null) {
      set({
        currentDocId: null,
        currentDoc: null,
        selectedDocIds: new Set<string>(),
        documentSelectionInitialized: true,
      })
      return
    }
    const document = get().documents.find((entry) => entry.id === id)
    if (document) {
      set({
        currentDocId: document.id,
        currentDoc: document,
        selectedDocIds: new Set<string>([document.id]),
        documentSelectionInitialized: true,
      })
      return
    }
    get().fetchDocument(id)
  },

  updateLocalDoc: (id: string, updates: Partial<Document>) => {
    set((state) => ({
      documents: state.documents.map((document) =>
        document.id === id ? { ...document, ...updates } : document
      ),
      currentDoc:
        state.currentDoc?.id === id ? { ...state.currentDoc, ...updates } : state.currentDoc,
    }))
  },

  updateDocument: async (id: string, updates: Partial<Document>) => {
    const response = await apiClient.patch<Document>(`/documents/${id}`, {
      body: updates,
    })

    if (!response.ok || !response.data) {
      set({ error: response.errorMessage || 'Failed to update document' })
      return false
    }

    const normalized = normalizeDocument(response.data)
    set((state) => ({
      documents: state.documents.map((document) =>
        document.id === id ? { ...document, ...normalized } : document
      ),
      currentDoc:
        state.currentDoc?.id === id ? { ...state.currentDoc, ...normalized } : state.currentDoc,
      error: null,
    }))
    return true
  },

  deleteDocument: async (id: string) => {
    const response = await apiClient.delete(`/documents/${id}`)
    if (!response.ok) {
      set({ error: response.errorMessage || 'Failed to delete document' })
      return false
    }
    await get().fetchDocuments()
    return true
  },

  deleteMultipleDocuments: async (ids: string[]) => {
    const requests = ids.map((id) => apiClient.delete(`/documents/${id}`))
    const responses = await Promise.all(requests)
    const failed = responses.filter((response) => !response.ok)
    if (failed.length > 0) {
      set({
        error: failed[0].errorMessage || `Failed to delete ${failed.length} document${failed.length === 1 ? '' : 's'}`,
      })
      return false
    }
    set({
      selectedDocIds: new Set<string>(),
      currentDocId: null,
      currentDoc: null,
      documentSelectionInitialized: true,
      error: null,
    })
    await get().fetchDocuments()
    return true
  },

  getDiff: async (leftId: string, rightId: string) => {
    const response = await apiClient.get<DocumentDiffResponse>(`/documents/${leftId}/diff/${rightId}`)
    if (!response.ok || !response.data) {
      set({ error: response.errorMessage || 'Failed to diff documents' })
      return null
    }
    return response.data
  },

  setShowDeleted: (show: boolean) => {
    set({ showDeleted: show })
    get().fetchDocuments()
  },

  initializeDocumentSelection: () => {
    const state = get()
    if (state.documentSelectionInitialized || state.documents.length === 0) {
      return
    }
    const firstDocument = state.documents[0]
    set({
      selectedDocIds: new Set<string>([firstDocument.id]),
      currentDocId: firstDocument.id,
      currentDoc: firstDocument,
      documentSelectionInitialized: true,
    })
  },

  toggleDocSelection: (id: string) => {
    set((state) => {
      const updated = new Set(state.selectedDocIds)
      if (updated.has(id)) {
        updated.delete(id)
      } else {
        updated.add(id)
      }
      return {
        ...syncDocumentSelection(state.documents, updated),
        documentSelectionInitialized: true,
      }
    })
  },

  clearSelection: () => {
    set({
      selectedDocIds: new Set<string>(),
      currentDocId: null,
      currentDoc: null,
      documentSelectionInitialized: true,
    })
  },

  selectAll: (docIds: string[]) => {
    set((state) => ({
      ...syncDocumentSelection(state.documents, docIds),
      documentSelectionInitialized: true,
    }))
  },
}))
