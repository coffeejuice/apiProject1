export interface BlockTypeMeta {
  id: string
  label: string
  icon: string
  insertable: boolean
}

const BLOCK_TYPE_META: Record<string, BlockTypeMeta> = {
  document_heading: {
    id: 'document_heading',
    label: 'Document Heading',
    icon: 'DH',
    insertable: false,
  },
  input_workpiece: {
    id: 'input_workpiece',
    label: 'Input Workpiece',
    icon: 'IW',
    insertable: false,
  },
  paragraph: {
    id: 'paragraph',
    label: 'Paragraph',
    icon: 'P',
    insertable: true,
  },
  heading1: {
    id: 'heading1',
    label: 'Heading 1',
    icon: 'H1',
    insertable: true,
  },
  heading2: {
    id: 'heading2',
    label: 'Heading 2',
    icon: 'H2',
    insertable: true,
  },
  list: {
    id: 'list',
    label: 'List',
    icon: 'L',
    insertable: true,
  },
  todo: {
    id: 'todo',
    label: 'Todo',
    icon: 'T',
    insertable: true,
  },
  code: {
    id: 'code',
    label: 'Code',
    icon: '</>',
    insertable: true,
  },
  quote: {
    id: 'quote',
    label: 'Quote',
    icon: '"',
    insertable: true,
  },
  divider: {
    id: 'divider',
    label: 'Divider',
    icon: '---',
    insertable: true,
  },
}

const FALLBACK_META: BlockTypeMeta = {
  id: 'unknown',
  label: 'Unknown',
  icon: '?',
  insertable: false,
}

export const BLOCK_LIBRARY_TYPES = Object.values(BLOCK_TYPE_META).filter(
  (entry) => entry.insertable
)

export function getBlockTypeMeta(blockTypeId: string): BlockTypeMeta {
  return BLOCK_TYPE_META[blockTypeId] || { ...FALLBACK_META, id: blockTypeId, label: blockTypeId }
}

export function getBlockTypeLabel(blockTypeId: string): string {
  return getBlockTypeMeta(blockTypeId).label
}

export function getBlockTypeIcon(blockTypeId: string): string {
  return getBlockTypeMeta(blockTypeId).icon
}
