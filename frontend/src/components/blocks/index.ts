/**
 * Block components registration
 * Import and register all block components here
 */

import { registerBlockType } from './BlockRegistry'
import DocumentHeadingBlock from './DocumentHeadingBlock'
import InputWorkpieceBlock from './InputWorkpieceBlock'

// Register system blocks
registerBlockType('document_heading', DocumentHeadingBlock)
registerBlockType('input_workpiece', InputWorkpieceBlock)

// Export for convenience
export { DocumentHeadingBlock, InputWorkpieceBlock }
export * from './BlockRegistry'
