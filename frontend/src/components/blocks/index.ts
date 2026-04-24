/**
 * Block components registration
 * Import and register all block components here
 */

import { registerBlockType, registerOperationBlockType } from './BlockRegistry'
import DocumentHeadingBlock from './DocumentHeadingBlock'
import InputWorkpieceBlock from './InputWorkpieceBlock'
import OperationBlock from './OperationBlock'

// Register system blocks
registerBlockType('document_heading', DocumentHeadingBlock)
registerBlockType('input_workpiece', InputWorkpieceBlock)

// Register numeric operation block fallback backed by document_blocks_library.
registerOperationBlockType(OperationBlock)

// Export for convenience
export { DocumentHeadingBlock, InputWorkpieceBlock, OperationBlock }
export * from './BlockRegistry'
