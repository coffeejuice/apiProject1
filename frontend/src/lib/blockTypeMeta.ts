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
}

const FALLBACK_META: BlockTypeMeta = {
  id: 'unknown',
  label: 'Unknown',
  icon: '?',
  insertable: false,
}

export function getBlockTypeMeta(blockTypeId: string): BlockTypeMeta {
  if (BLOCK_TYPE_META[blockTypeId]) {
    return BLOCK_TYPE_META[blockTypeId]
  }
  if (/^\d+$/.test(blockTypeId)) {
    return {
      id: blockTypeId,
      label: `Operation ${blockTypeId}`,
      icon: 'OP',
      insertable: true,
    }
  }
  return { ...FALLBACK_META, id: blockTypeId, label: blockTypeId }
}

export function getBlockTypeLabel(blockTypeId: string): string {
  return getBlockTypeMeta(blockTypeId).label
}

export function getBlockTypeIcon(blockTypeId: string): string {
  return getBlockTypeMeta(blockTypeId).icon
}
