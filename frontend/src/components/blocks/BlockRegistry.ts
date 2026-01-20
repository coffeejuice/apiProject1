/**
 * Block Component Registry
 * Maps block types to their React components
 */

import { ComponentType } from 'react'

export interface BlockData {
  block_id: string
  block_type: string
  text: string
  props: Record<string, any>
  order_key: string
  is_system: boolean
  is_removable: boolean
  fixed_position: number | null
  editable_fields?: string[]
}

export interface BlockComponentProps {
  block: BlockData
  onUpdate: (blockId: string, props: Record<string, any>) => void
  isReadOnly?: boolean
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
