export interface DocumentResumeState {
  version: 1
  toolView: 'blocks'
  projectId: string | null
  documentId: string | null
  scrollTop: number
  selectedBlockIds: string[]
  updatedAt: number
}

const STORAGE_KEY = 'forgelab-document-resume'

const DEFAULT_STATE: DocumentResumeState = {
  version: 1,
  toolView: 'blocks',
  projectId: null,
  documentId: null,
  scrollTop: 0,
  selectedBlockIds: [],
  updatedAt: 0,
}

function normalizeString(value: unknown): string | null {
  return typeof value === 'string' && value.length > 0 ? value : null
}

function normalizeScrollTop(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) && value > 0 ? value : 0
}

function normalizeSelectedBlockIds(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((entry): entry is string => typeof entry === 'string' && entry.length > 0)
    : []
}

export function loadDocumentResumeState(): DocumentResumeState | null {
  if (typeof window === 'undefined') {
    return null
  }

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) {
      return null
    }

    const parsed = JSON.parse(raw) as Partial<DocumentResumeState>
    return {
      version: 1,
      toolView: 'blocks',
      projectId: normalizeString(parsed.projectId),
      documentId: normalizeString(parsed.documentId),
      scrollTop: normalizeScrollTop(parsed.scrollTop),
      selectedBlockIds: normalizeSelectedBlockIds(parsed.selectedBlockIds),
      updatedAt: normalizeScrollTop(parsed.updatedAt),
    }
  } catch {
    return null
  }
}

export function saveDocumentResumeState(patch: Partial<Omit<DocumentResumeState, 'version' | 'updatedAt'>>) {
  if (typeof window === 'undefined') {
    return
  }

  const previous = loadDocumentResumeState() || DEFAULT_STATE
  const next: DocumentResumeState = {
    ...previous,
    ...patch,
    version: 1,
    toolView: 'blocks',
    projectId: patch.projectId === undefined ? previous.projectId : normalizeString(patch.projectId),
    documentId: patch.documentId === undefined ? previous.documentId : normalizeString(patch.documentId),
    scrollTop: patch.scrollTop === undefined ? previous.scrollTop : normalizeScrollTop(patch.scrollTop),
    selectedBlockIds: patch.selectedBlockIds === undefined
      ? previous.selectedBlockIds
      : normalizeSelectedBlockIds(patch.selectedBlockIds),
    updatedAt: Date.now(),
  }

  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
}
