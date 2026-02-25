/**
 * Block components registration
 * Import and register all block components here
 */

import { registerBlockType } from './BlockRegistry'
import BasicContentBlock from './BasicContentBlock'
import DocumentHeadingBlock from './DocumentHeadingBlock'
import InputWorkpieceBlock from './InputWorkpieceBlock'

// Register system blocks
registerBlockType('document_heading', DocumentHeadingBlock)
registerBlockType('input_workpiece', InputWorkpieceBlock)

// Register editable content blocks
registerBlockType('paragraph', BasicContentBlock)
registerBlockType('heading1', BasicContentBlock)
registerBlockType('heading2', BasicContentBlock)
registerBlockType('list', BasicContentBlock)
registerBlockType('todo', BasicContentBlock)
registerBlockType('code', BasicContentBlock)
registerBlockType('quote', BasicContentBlock)
registerBlockType('divider', BasicContentBlock)

// Export for convenience
export { BasicContentBlock, DocumentHeadingBlock, InputWorkpieceBlock }
export * from './BlockRegistry'
