/**
 * Block components registration
 * Import and register all block components here
 */

import { registerBlockType } from './BlockRegistry'
import DocumentBlock from './DocumentBlock'
import OperationBlock from './OperationBlock'

registerBlockType('document', DocumentBlock)
registerBlockType('heating', OperationBlock)
registerBlockType('furnace', OperationBlock)
registerBlockType('deformation', OperationBlock)
registerBlockType('operation', OperationBlock)

// Export for convenience
export { DocumentBlock, OperationBlock }
export * from './BlockRegistry'
