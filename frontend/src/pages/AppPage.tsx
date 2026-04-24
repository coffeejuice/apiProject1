import { useEffect, useMemo, useRef, useState } from 'react'

import BlockEditor, { BlockEditorHandle, BlockEditorMeta } from '../components/BlockEditor'
import MainEditorPane from '../components/MainEditorPane'
import MenuBar from '../components/MenuBar'
import TopEditorPane from '../components/TopEditorPane'
import ToolsPane from '../components/ToolsPane'
import ToolsSwitcher, { ToolView } from '../components/ToolsSwitcher'
import VisualEditor from '../components/VisualEditor'
import type { BlockData } from '../components/blocks'
import type { LibraryEditorView, MainEditorView } from '../components/editorPaneTypes'
import {
  LibraryMaterialsView,
  LibraryDieAssembliesView,
  LibraryDiesView,
  LibraryPressesView,
} from '../components/library/LibraryViews'
import SimulationView from '../components/simulation/SimulationView'
import { useDocumentsStore } from '../stores/useDocumentsStore'
import { useBlockClipboardStore } from '../stores/useBlockClipboardStore'
import { useLibraryStore } from '../stores/useLibraryStore'
import { useSessionStore } from '../stores/useSessionStore'

const EMPTY_EDITOR_META: BlockEditorMeta = {
  isLoading: false,
  draftDocumentName: '',
  sourceDocumentId: null,
  activeDocumentBlockId: null,
  saveStatus: 'idle',
  saveError: null,
  hasUnsavedChanges: false,
  changedBlocksCount: 0,
  canUndo: false,
  canRedo: false,
  isLineageLoading: false,
  isSessionsLoading: false,
}

interface LibraryActionConfig {
  createLabel: string
  cloneLabel: string
  deleteLabel: string
  selectedId: number | null
}

function getLibraryActions(view: MainEditorView, selection: {
  dieId: number | null
  dieAssemblyId: number | null
  pressId: number | null
  materialId: number | null
}): LibraryActionConfig {
  if (view === 'dies') {
    return {
      createLabel: 'New die',
      cloneLabel: 'Clone selected die',
      deleteLabel: 'Delete selected die',
      selectedId: selection.dieId,
    }
  }

  if (view === 'dieAssemblies') {
    return {
      createLabel: 'New die assembly',
      cloneLabel: 'Clone selected die assembly',
      deleteLabel: 'Delete selected die assembly',
      selectedId: selection.dieAssemblyId,
    }
  }

  if (view === 'presses') {
    return {
      createLabel: 'New press',
      cloneLabel: 'Clone selected press',
      deleteLabel: 'Delete selected press',
      selectedId: selection.pressId,
    }
  }

  return {
    createLabel: 'New material',
    cloneLabel: 'Clone selected material',
    deleteLabel: 'Delete selected material',
    selectedId: selection.materialId,
  }
}

function resolveMainEditorView(toolView: ToolView, libraryView: LibraryEditorView): MainEditorView {
  if (toolView === 'library') {
    return libraryView
  }
  if (toolView === 'simulation') {
    return 'simulation'
  }
  return 'blockEditor'
}

function getBlockClipboardLabel(block: BlockData): string {
  const title = block.props?.title
  if (typeof title === 'string' && title.trim()) {
    return title
  }

  const operationType = block.props?.operation_type
  if (operationType && typeof operationType === 'object') {
    const libraryName = (operationType as { library_name?: unknown }).library_name
    if (typeof libraryName === 'string' && libraryName.trim()) {
      return libraryName
    }
  }

  if (block.block_type_id === 'document_heading') {
    return 'Document'
  }
  if (block.block_type_id === '10') {
    return 'Furnace'
  }
  if (block.block_type_id === '24') {
    return 'Deformation'
  }
  return `Block ${block.block_type_id}`
}

function getClipboardClipLabel(
  clip: ReturnType<typeof useBlockClipboardStore.getState>['clips'][number] | null
): string | null {
  if (!clip) {
    return null
  }
  const firstBlockLabel = clip.blocks[0] ? getBlockClipboardLabel(clip.blocks[0]) : 'Empty clip'
  const suffix = clip.blocks.length > 1 ? ` +${clip.blocks.length - 1}` : ''
  return `${clip.mode === 'cut' ? 'Cut' : 'Copy'}: ${firstBlockLabel}${suffix}`
}

export default function AppPage() {
  const { fetchProjects, currentDoc } = useDocumentsStore()
  const {
    users,
    dieTypes,
    materials,
    materialClassificationCatalog,
    dies,
    dieAssemblies,
    presses,
    pressModes,
    isLoading: isLibraryLoading,
    error: libraryError,
    hasLoaded: hasLibraryLoaded,
    fetchAll: fetchLibrary,
  } = useLibraryStore()
  const { user } = useSessionStore()
  const activeClipboardClip = useBlockClipboardStore((state) =>
    state.clips.find((clip) => clip.id === state.activeClipId) ?? null
  )

  const editorRef = useRef<BlockEditorHandle | null>(null)

  const [activeToolView, setActiveToolView] = useState<ToolView | null>('projects')
  const [activeLibraryView, setActiveLibraryView] = useState<LibraryEditorView>('dies')
  const [mainEditorView, setMainEditorView] = useState<MainEditorView>('blockEditor')
  const [isTopEditorPaneCollapsed, setIsTopEditorPaneCollapsed] = useState(false)
  const [editorMeta, setEditorMeta] = useState<BlockEditorMeta>(EMPTY_EDITOR_META)
  const [editorBlocks, setEditorBlocks] = useState<BlockData[]>([])

  const [selectedDieId, setSelectedDieId] = useState<number | null>(null)
  const [selectedDieAssemblyId, setSelectedDieAssemblyId] = useState<number | null>(null)
  const [selectedPressId, setSelectedPressId] = useState<number | null>(null)
  const [selectedMaterialId, setSelectedMaterialId] = useState<number | null>(null)

  useEffect(() => {
    void fetchProjects()
  }, [fetchProjects])

  useEffect(() => {
    if (!hasLibraryLoaded) {
      void fetchLibrary()
    }
  }, [fetchLibrary, hasLibraryLoaded])

  useEffect(() => {
    if (activeToolView === 'library') {
      setMainEditorView(activeLibraryView)
    }
  }, [activeLibraryView, activeToolView])

  const callEditor = (callback: (editor: BlockEditorHandle) => Promise<boolean> | Promise<void> | void) => {
    const editor = editorRef.current
    if (!editor) {
      return
    }
    void callback(editor)
  }

  const toggleToolView = (view: ToolView) => {
    setActiveToolView((previous) => {
      if (previous === view) {
        return null
      }
      setMainEditorView(resolveMainEditorView(view, activeLibraryView))
      return view
    })
  }

  const handleInsertBlockFromToolsPane = (blockTypeId: string) => {
    callEditor(async (editor) => {
      await editor.insertBlock(blockTypeId)
    })
  }

  const handlePasteClipboardClip = (clipId?: string) => {
    const editor = editorRef.current
    if (!editor) {
      return
    }
    setMainEditorView('blockEditor')
    void editor.pasteClipboardClip(clipId)
  }

  const handleCopyBlocksToClipboard = async (blockIds: string[]): Promise<boolean> => {
    const editor = editorRef.current
    if (!editor) {
      return false
    }

    const copied = await editor.copyBlocksToClipboard(blockIds)
    if (copied) {
      setActiveToolView('blocks')
      setMainEditorView('blockEditor')
    }
    return copied
  }

  const handleCutBlocksToClipboard = async (blockIds: string[]): Promise<boolean> => {
    const editor = editorRef.current
    if (!editor) {
      return false
    }

    const cut = await editor.cutBlocksToClipboard(blockIds)
    if (cut) {
      setActiveToolView('blocks')
      setMainEditorView('blockEditor')
    }
    return cut
  }

  const handlePasteActiveClipboard = async (): Promise<boolean> => {
    const editor = editorRef.current
    if (!editor) {
      return false
    }
    return editor.pasteClipboardClip()
  }

  const hasDocument = mainEditorView === 'blockEditor' && Boolean(currentDoc?.id)
  const activeClipboardLabel = useMemo(
    () => getClipboardClipLabel(activeClipboardClip),
    [activeClipboardClip]
  )

  const libraryActions = useMemo(() => {
    return getLibraryActions(mainEditorView, {
      dieId: selectedDieId,
      dieAssemblyId: selectedDieAssemblyId,
      pressId: selectedPressId,
      materialId: selectedMaterialId,
    })
  }, [mainEditorView, selectedDieAssemblyId, selectedDieId, selectedMaterialId, selectedPressId])

  return (
    <div className="ui-shell flex h-screen">
      <div className="flex-1 min-w-0 flex flex-col">
        <MenuBar
          meta={editorMeta}
          hasDocument={hasDocument}
          isTopEditorVisible={!isTopEditorPaneCollapsed}
          showTopEditorToggle={mainEditorView === 'blockEditor'}
          onToggleTopEditor={() => setIsTopEditorPaneCollapsed((previous) => !previous)}
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
            libraryView={activeLibraryView}
            onLibraryViewChange={setActiveLibraryView}
            onInsertBlockType={handleInsertBlockFromToolsPane}
            onPasteClipboardClip={handlePasteClipboardClip}
          />

          <div className="flex-1 min-w-0 flex flex-col">
            <TopEditorPane
              view={mainEditorView}
              isVisible={!isTopEditorPaneCollapsed}
              visualEditorView={(
                <VisualEditor
                  blocks={editorBlocks}
                  isVisible
                  hasUnsavedChanges={editorMeta.hasUnsavedChanges}
                  activeDocumentBlockId={editorMeta.activeDocumentBlockId}
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
                  hasActiveClipboardClip={Boolean(activeClipboardClip)}
                  activeClipboardLabel={activeClipboardLabel}
                  onCopyBlocksToClipboard={handleCopyBlocksToClipboard}
                  onCutBlocksToClipboard={handleCutBlocksToClipboard}
                  onPasteActiveClipboard={handlePasteActiveClipboard}
                />
              )}
              libraryActionsView={
                mainEditorView === 'materials' || mainEditorView === 'simulation'
                  ? null
                  : (
                      <div className="ui-pane-header flex items-center justify-between gap-3">
                        <div className="ui-pane-title">TopEditorPane</div>
                        <div className="flex flex-wrap items-center gap-2">
                          <button type="button" className="ui-btn-primary" onClick={() => undefined}>
                            {libraryActions.createLabel}
                          </button>
                          <button
                            type="button"
                            className="ui-btn"
                            disabled={libraryActions.selectedId === null}
                            onClick={() => undefined}
                          >
                            {libraryActions.cloneLabel}
                          </button>
                          <button
                            type="button"
                            className="ui-btn-danger"
                            disabled={libraryActions.selectedId === null}
                            onClick={() => undefined}
                          >
                            {libraryActions.deleteLabel}
                          </button>
                          <div className="ui-badge">
                            Selected: {libraryActions.selectedId ?? 'none'}
                          </div>
                        </div>
                      </div>
                    )
              }
            />

            <MainEditorPane
              view={mainEditorView}
              blockEditorView={(
                <BlockEditor
                  ref={editorRef}
                  onMetaChange={setEditorMeta}
                  onBlocksChange={setEditorBlocks}
                />
              )}
              diesView={(
                <LibraryDiesView
                  dies={dies}
                  dieTypes={dieTypes}
                  users={users}
                  currentUserId={user?.user_id ?? null}
                  selectedDieId={selectedDieId}
                  onSelectDieId={setSelectedDieId}
                  isLoading={isLibraryLoading}
                  error={libraryError}
                />
              )}
              dieAssembliesView={(
                <LibraryDieAssembliesView
                  dieAssemblies={dieAssemblies}
                  users={users}
                  currentUserId={user?.user_id ?? null}
                  selectedDieAssemblyId={selectedDieAssemblyId}
                  onSelectDieAssemblyId={setSelectedDieAssemblyId}
                  isLoading={isLibraryLoading}
                  error={libraryError}
                />
              )}
              pressesView={(
                <LibraryPressesView
                  presses={presses}
                  pressModes={pressModes}
                  users={users}
                  currentUserId={user?.user_id ?? null}
                  selectedPressId={selectedPressId}
                  onSelectPressId={setSelectedPressId}
                  isLoading={isLibraryLoading}
                  error={libraryError}
                />
              )}
              materialsView={(
                <LibraryMaterialsView
                  materials={materials}
                  materialClassificationCatalog={materialClassificationCatalog}
                  users={users}
                  currentUserId={user?.user_id ?? null}
                  selectedMaterialId={selectedMaterialId}
                  onSelectMaterialId={setSelectedMaterialId}
                  onRefreshLibrary={fetchLibrary}
                  isMaterialListVisible={activeToolView === 'library'}
                  isLoading={isLibraryLoading}
                  error={libraryError}
                />
              )}
              simulationView={(
                <SimulationView
                  users={users}
                  currentUserId={user?.user_id ?? null}
                />
              )}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
