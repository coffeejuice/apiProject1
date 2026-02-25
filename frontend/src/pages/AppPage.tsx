import { useEffect, useRef, useState } from 'react'
import { useDocumentsStore } from '../stores/useDocumentsStore'
import BlockEditor, { BlockEditorHandle, BlockEditorMeta } from '../components/BlockEditor'
import MenuBar from '../components/MenuBar'
import ToolsSwitcher, { ToolView } from '../components/ToolsSwitcher'
import ToolsPane from '../components/ToolsPane'
import VisualEditor from '../components/VisualEditor'
import type { BlockData } from '../components/blocks'

const EMPTY_EDITOR_META: BlockEditorMeta = {
  isLoading: false,
  draftDocumentName: '',
  sourceDocumentId: null,
  saveStatus: 'idle',
  saveError: null,
  hasUnsavedChanges: false,
  changedBlocksCount: 0,
  canUndo: false,
  canRedo: false,
  isLineageLoading: false,
  isSessionsLoading: false,
}

export default function AppPage() {
  const { fetchProjects, currentDoc } = useDocumentsStore()
  const editorRef = useRef<BlockEditorHandle | null>(null)

  const [activeToolView, setActiveToolView] = useState<ToolView | null>('projects')
  const [isVisualEditorCollapsed, setIsVisualEditorCollapsed] = useState(false)
  const [editorMeta, setEditorMeta] = useState<BlockEditorMeta>(EMPTY_EDITOR_META)
  const [editorBlocks, setEditorBlocks] = useState<BlockData[]>([])

  useEffect(() => {
    void fetchProjects()
  }, [fetchProjects])

  const callEditor = (callback: (editor: BlockEditorHandle) => Promise<boolean> | Promise<void> | void) => {
    const editor = editorRef.current
    if (!editor) {
      return
    }
    void callback(editor)
  }

  const toggleToolView = (view: ToolView) => {
    setActiveToolView((prev) => (prev === view ? null : view))
  }

  const handleInsertBlockFromToolsPane = (blockTypeId: string) => {
    callEditor(async (editor) => {
      const previousBlockId = editorBlocks.length > 0 ? editorBlocks[editorBlocks.length - 1].block_id : null
      await editor.insertBlock(blockTypeId, previousBlockId)
    })
  }

  const hasDocument = Boolean(currentDoc?.id)

  return (
    <div className="ui-shell flex h-screen">
      <div className="flex-1 min-w-0 flex flex-col">
        <MenuBar
          meta={editorMeta}
          hasDocument={hasDocument}
          isVisualEditorVisible={!isVisualEditorCollapsed}
          onToggleVisualEditor={() => setIsVisualEditorCollapsed((prev) => !prev)}
          onSave={() => callEditor((editor) => editor.saveChanges())}
          onCancel={() => callEditor((editor) => editor.cancelChanges())}
          onUndo={() => callEditor((editor) => editor.undo())}
          onRedo={() => callEditor((editor) => editor.redo())}
          onShowLineage={() => callEditor((editor) => editor.showLineage())}
          onShowSessions={() => callEditor((editor) => editor.showSessions())}
        />

        <div className="flex flex-1 min-h-0">
          <ToolsSwitcher activeView={activeToolView} onToggleView={toggleToolView} />

          <ToolsPane
            activeView={activeToolView}
            onInsertBlockType={handleInsertBlockFromToolsPane}
          />

          <div className="flex-1 min-w-0 flex flex-col">
            <VisualEditor
              blocks={editorBlocks}
              isVisible={!isVisualEditorCollapsed}
              hasUnsavedChanges={editorMeta.hasUnsavedChanges}
              onNavigate={(blockId) => {
                const editor = editorRef.current
                if (!editor) {
                  return
                }
                editor.scrollToBlock(blockId)
              }}
              onInsertBlock={async (blockTypeId, previousBlockId) => {
                const editor = editorRef.current
                if (!editor) {
                  return
                }
                await editor.insertBlock(blockTypeId, previousBlockId)
              }}
              onMoveBlocks={async (blockIds, previousBlockId) => {
                const editor = editorRef.current
                if (!editor) {
                  return
                }
                await editor.moveBlocks(blockIds, previousBlockId)
              }}
              onCopyBlocks={async (blockIds, previousBlockId) => {
                const editor = editorRef.current
                if (!editor) {
                  return
                }
                await editor.copyBlocks(blockIds, previousBlockId)
              }}
              onDeleteBlocks={async (blockIds) => {
                const editor = editorRef.current
                if (!editor) {
                  return
                }
                await editor.deleteBlocks(blockIds)
              }}
            />

            <div className="flex-1 min-h-0">
              <BlockEditor
                ref={editorRef}
                onMetaChange={setEditorMeta}
                onBlocksChange={setEditorBlocks}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
