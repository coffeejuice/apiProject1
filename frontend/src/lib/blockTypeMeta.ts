export interface BlockTypeMeta {
  id: string
  label: string
  icon: string
  insertable: boolean
}

const BLOCK_TYPE_META: Record<string, BlockTypeMeta> = {
  document: {
    id: 'document',
    label: 'Document',
    icon: 'DOC',
    insertable: false,
  },
  heating: {
    id: 'heating',
    label: 'Heating',
    icon: 'HEAT',
    insertable: true,
  },
  deformation: {
    id: 'deformation',
    label: 'Deformation',
    icon: 'DEF',
    insertable: true,
  },
  operation: {
    id: 'operation',
    label: 'Operation',
    icon: 'OP',
    insertable: true,
  },
  furnace: {
    id: 'furnace',
    label: 'Furnace',
    icon: 'FUR',
    insertable: true,
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
  return { ...FALLBACK_META, id: blockTypeId, label: blockTypeId }
}

export function getBlockTypeLabel(blockTypeId: string): string {
  return getBlockTypeMeta(blockTypeId).label
}

export function getBlockTypeIcon(blockTypeId: string): string {
  return getBlockTypeMeta(blockTypeId).icon
}
