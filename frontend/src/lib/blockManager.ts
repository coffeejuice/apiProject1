import type { Operation } from '../types/api'
import { generateUUID } from './utils'

export interface TrackedBlock {
  blockId: string
  blockType: string
  text: string
  props: Record<string, unknown>
  orderKey: string
  parentBlockId?: string | null
}

const SYSTEM_BLOCK_TYPES = new Set(['document_heading', 'input_workpiece'])

function isSystemBlock(blockType: string): boolean {
  return SYSTEM_BLOCK_TYPES.has(blockType)
}

function extractText(node: any): string {
  if (!node) {
    return ''
  }
  if (typeof node === 'string') {
    return node
  }
  if (node.type === 'text' && typeof node.text === 'string') {
    return node.text
  }
  if (Array.isArray(node.content)) {
    return node.content.map(extractText).join('')
  }
  return ''
}

function getNodeId(node: any): string | undefined {
  if (!node || typeof node !== 'object') {
    return undefined
  }
  const attrs = node.attrs || {}
  const candidates = [attrs.block_id, attrs.blockId, attrs.id]
  for (const candidate of candidates) {
    if (typeof candidate === 'string' && candidate.trim()) {
      return candidate
    }
  }
  return undefined
}

function mapNodeType(node: any): string {
  if (!node || typeof node !== 'object') {
    return 'paragraph'
  }

  switch (node.type) {
    case 'paragraph':
      return 'paragraph'
    case 'heading': {
      const level = Number(node.attrs?.level || 1)
      return level <= 1 ? 'heading1' : 'heading2'
    }
    case 'bulletList':
    case 'orderedList':
    case 'listItem':
      return 'list'
    case 'taskList':
    case 'taskItem':
      return 'todo'
    case 'codeBlock':
      return 'code'
    case 'blockquote':
      return 'quote'
    case 'horizontalRule':
      return 'divider'
    default:
      return 'paragraph'
  }
}

function buildOrderKey(base: number, index: number): string {
  const orderBase = String(base + index).padStart(20, '0')
  const suffix = String(Math.floor(Math.random() * 9000) + 1000)
  return `${orderBase}-${suffix}`
}

function createTrackedBlock(
  node: any,
  blockType: string,
  orderKey: string,
  props: Record<string, unknown> = {}
): TrackedBlock {
  return {
    blockId: getNodeId(node) || '',
    blockType,
    text: extractText(node),
    props,
    orderKey,
    parentBlockId: null,
  }
}

function appendBlocksFromNode(
  node: any,
  blocks: TrackedBlock[],
  nextIndex: { value: number },
  orderBase: number
): void {
  if (!node || typeof node !== 'object') {
    return
  }

  if (node.type === 'bulletList' || node.type === 'orderedList') {
    const items = Array.isArray(node.content) ? node.content : []
    items.forEach((item: any) => {
      const orderKey = buildOrderKey(orderBase, nextIndex.value)
      nextIndex.value += 1
      blocks.push(createTrackedBlock(item, 'list', orderKey))
    })
    return
  }

  if (node.type === 'taskList') {
    const items = Array.isArray(node.content) ? node.content : []
    items.forEach((item: any) => {
      const orderKey = buildOrderKey(orderBase, nextIndex.value)
      nextIndex.value += 1
      blocks.push(
        createTrackedBlock(item, 'todo', orderKey, {
          checked: Boolean(item.attrs?.checked),
        })
      )
    })
    return
  }

  if (node.type === 'listItem' || node.type === 'taskItem') {
    const orderKey = buildOrderKey(orderBase, nextIndex.value)
    nextIndex.value += 1
    blocks.push(createTrackedBlock(node, mapNodeType(node), orderKey, {
      checked: Boolean(node.attrs?.checked),
    }))
    return
  }

  const orderKey = buildOrderKey(orderBase, nextIndex.value)
  nextIndex.value += 1
  blocks.push(createTrackedBlock(node, mapNodeType(node), orderKey))
}

export function contentToBlocks(content: unknown): TrackedBlock[] {
  if (!content || typeof content !== 'object') {
    return []
  }

  const doc = content as { type?: string; content?: any[] }
  if (!Array.isArray(doc.content)) {
    return []
  }

  const blocks: TrackedBlock[] = []
  const orderBase = Date.now() * 1000
  const nextIndex = { value: 0 }

  doc.content.forEach((node) => {
    appendBlocksFromNode(node, blocks, nextIndex, orderBase)
  })

  return blocks
}

function propsEqual(a: Record<string, unknown>, b: Record<string, unknown>): boolean {
  try {
    return JSON.stringify(a) === JSON.stringify(b)
  } catch {
    return false
  }
}

export function generateOperations(
  oldBlocks: TrackedBlock[],
  newBlocks: TrackedBlock[]
): Operation[] {
  const ops: Operation[] = []
  const oldById = new Map<string, TrackedBlock>()
  const oldIndexById = new Map<string, number>()

  oldBlocks.forEach((block, index) => {
    oldById.set(block.blockId, block)
    oldIndexById.set(block.blockId, index)
  })

  const oldUserBlocks = oldBlocks.filter((block) => !isSystemBlock(block.blockType))
  const matchedOldIds = new Set<string>()
  const orderBase = Date.now() * 1000

  newBlocks.forEach((newBlock, index) => {
    let oldBlock: TrackedBlock | undefined
    if (newBlock.blockId) {
      oldBlock = oldById.get(newBlock.blockId)
    }

    if (!oldBlock) {
      const fallback = oldUserBlocks[index]
      if (fallback && !matchedOldIds.has(fallback.blockId)) {
        oldBlock = fallback
        newBlock.blockId = fallback.blockId
      }
    }

    if (oldBlock) {
      matchedOldIds.add(oldBlock.blockId)

      if (newBlock.text !== oldBlock.text) {
        ops.push({
          op_type: 'update_text',
          data: {
            block_id: oldBlock.blockId,
            text: newBlock.text,
          },
        })
      }

      if (!propsEqual(newBlock.props, oldBlock.props)) {
        ops.push({
          op_type: 'update_props',
          data: {
            block_id: oldBlock.blockId,
            props: newBlock.props,
          },
        })
      }

      const oldIndex = oldIndexById.get(oldBlock.blockId)
      if (oldIndex !== undefined && oldIndex !== index) {
        const orderKey = buildOrderKey(orderBase, index)
        newBlock.orderKey = orderKey
        ops.push({
          op_type: 'move_block',
          data: {
            block_id: oldBlock.blockId,
            parent_block_id: null,
            order_key: orderKey,
          },
        })
      } else {
        newBlock.orderKey = oldBlock.orderKey
      }
    } else {
      const blockId = newBlock.blockId || generateUUID()
      const orderKey = newBlock.orderKey || buildOrderKey(orderBase, index)
      newBlock.blockId = blockId
      newBlock.orderKey = orderKey

      ops.push({
        op_type: 'insert_block',
        data: {
          block_id: blockId,
          parent_block_id: null,
          order_key: orderKey,
          block_type: newBlock.blockType,
          text: newBlock.text || '',
          props: newBlock.props || {},
        },
      })
    }
  })

  oldBlocks.forEach((oldBlock) => {
    if (matchedOldIds.has(oldBlock.blockId)) {
      return
    }
    if (isSystemBlock(oldBlock.blockType)) {
      return
    }
    ops.push({
      op_type: 'delete_block',
      data: {
        block_id: oldBlock.blockId,
      },
    })
  })

  return ops
}
