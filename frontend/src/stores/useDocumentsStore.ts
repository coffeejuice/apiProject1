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

  fetchProjects: () => Promise<void>
  createProject: (name: string, notes?: string) => Promise<Project | null>
  setCurrentProject: (id: string | null) => void

  fetchDocuments: (projectId?: string | null) => Promise<void>
  createDocument: (name: string, notes?: string, sourceDocumentId?: string) => Promise<Document | null>
  copyDocument: (id: string, name?: string) => Promise<Document | null>
  fetchDocument: (id: string) => Promise<Document | null>
  setCurrentDoc: (id: string | null) => void
  updateLocalDoc: (id: string, updates: Partial<Document>) => void
  updateDocument: (id: string, updates: Partial<Document>) => Promise<boolean>
  deleteDocument: (id: string) => Promise<boolean>
  deleteMultipleDocuments: (ids: string[]) => Promise<void>
  getDiff: (leftId: string, rightId: string) => Promise<DocumentDiffResponse | null>

  setShowDeleted: (show: boolean) => void
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
      set({ documents: [], currentDoc: null, currentDocId: null })
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
      isLoading: false,
      error: null,
    }))
    await get().fetchDocuments(project.id)
    return project
  },

  setCurrentProject: (id: string | null) => {
    set({
      currentProjectId: id,
      documents: [],
      currentDocId: null,
      currentDoc: null,
      selectedDocIds: new Set<string>(),
    })
    if (id) {
      get().fetchDocuments(id)
    }
  },

  fetchDocuments: async (projectId?: string | null) => {
    const targetProjectId = projectId ?? get().currentProjectId
    if (!targetProjectId) {
      set({ documents: [], currentDoc: null, currentDocId: null })
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
    const currentDoc = normalized.find((document) => document.id === get().currentDocId) || null

    set({
      documents: normalized,
      currentDoc,
      currentDocId: currentDoc?.id || null,
      isLoading: false,
      error: null,
    })
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
      isLoading: false,
      error: null,
    })
    return document
  },

  setCurrentDoc: (id: string | null) => {
    if (id === null) {
      set({ currentDocId: null, currentDoc: null })
      return
    }
    const document = get().documents.find((entry) => entry.id === id)
    if (document) {
      set({ currentDocId: document.id, currentDoc: document })
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
    await Promise.all(requests)
    set({ selectedDocIds: new Set<string>() })
    await get().fetchDocuments()
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

  toggleDocSelection: (id: string) => {
    set((state) => {
      const updated = new Set(state.selectedDocIds)
      if (updated.has(id)) {
        updated.delete(id)
      } else {
        updated.add(id)
      }
      return { selectedDocIds: updated }
    })
  },

  clearSelection: () => {
    set({ selectedDocIds: new Set<string>() })
  },

  selectAll: (docIds: string[]) => {
    set({ selectedDocIds: new Set<string>(docIds) })
  },
}))
