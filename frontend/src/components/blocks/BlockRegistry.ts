/**
 * Block Component Registry
 * Maps block types to their React components
 */

/* eslint-disable @typescript-eslint/no-explicit-any */

import { ComponentType } from 'react'

export interface BlockData {
  block_id: string
  document_id: number
  previous_block_id: string | null
  next_block_id: string | null
  block_type_id: string
  props: Record<string, any>
  is_system: boolean
  is_removable: boolean
  fixed_position: number | null
  editable_fields?: string[]
  field_limits?: Record<string, number>
}

export interface BlockComponentProps {
  block: BlockData
  baselineProps: Record<string, any>
  isActive: boolean
  saveStatus?: 'idle' | 'saving' | 'saved' | 'error'
  sectionNumber?: string | null
  onUpdate: (blockId: string, props: Record<string, any>) => void
}

type BlockComponent = ComponentType<BlockComponentProps>

class BlockTypeRegistry {
  private components: Map<string, BlockComponent> = new Map()

  register(blockType: string, component: BlockComponent): void {
    this.components.set(blockType, component)
  }

  get(blockType: string): BlockComponent | undefined {
    return this.components.get(blockType)
  }

  has(blockType: string): boolean {
    return this.components.has(blockType)
  }

  getAll(): Map<string, BlockComponent> {
    return new Map(this.components)
  }
}

// Global registry instance
const registry = new BlockTypeRegistry()

export function registerBlockType(
  blockType: string,
  component: BlockComponent
): void {
  registry.register(blockType, component)
}

export function getBlockComponent(blockType: string): BlockComponent | undefined {
  return registry.get(blockType)
}

export function hasBlockComponent(blockType: string): boolean {
  return registry.has(blockType)
}

export default registry
