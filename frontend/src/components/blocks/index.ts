/**
 * Block components registration
 * Import and register all block components here
 */

import { registerBlockType } from './BlockRegistry'
import ProcessHeadingBlock from './ProcessHeadingBlock'
import InputWorkpieceBlock from './InputWorkpieceBlock'

// Register system blocks
registerBlockType('process_heading', ProcessHeadingBlock)
registerBlockType('input_workpiece', InputWorkpieceBlock)

// Export for convenience
export { ProcessHeadingBlock, InputWorkpieceBlock }
export * from './BlockRegistry'
