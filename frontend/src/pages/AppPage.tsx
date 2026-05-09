import { useEffect, useMemo, useRef, useState } from 'react'

import BlockEditor, { BlockEditorHandle, BlockEditorMeta } from '../components/BlockEditor'
import MainEditorPane from '../components/MainEditorPane'
import MenuBar from '../components/MenuBar'
import ToolsPane from '../components/ToolsPane'
import ToolsSwitcher, { ToolView } from '../components/ToolsSwitcher'
import type { LibraryEditorView, MainEditorView } from '../components/editorPaneTypes'
import {
  LibraryMaterialsView,
  LibraryDieAssembliesView,
  LibraryDiesView,
  LibraryPressesView,
} from '../components/library/LibraryViews'
import LogsView from '../components/runtimeLogs/LogsView'
import DocumentOperationsView from '../components/operations/DocumentOperationsView'
import SimulationStepsView from '../components/simulationSteps/SimulationStepsView'
import SimulationView from '../components/simulation/SimulationView'
import { loadDocumentResumeState, saveDocumentResumeState } from '../lib/documentResumeState'
import { useDocumentsStore } from '../stores/useDocumentsStore'
import { useLibraryStore } from '../stores/useLibraryStore'
import { useSessionStore } from '../stores/useSessionStore'

const EMPTY_EDITOR_META: BlockEditorMeta = {
  isLoading: false,
  draftDocumentName: '',
  sourceDocumentId: null,
  activeDocumentBlockId: null,
  hoveredDocumentBlockId: null,
  documentBlocks: [],
  activeDocumentBlockLabel: null,
  selectedDocumentBlockIds: [],
  selectedDocumentBlockLabel: null,
  structureEditDisabled: false,
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
  if (toolView === 'operations') {
    return 'operations'
  }
  if (toolView === 'simulationSteps') {
    return 'simulationSteps'
  }
  if (toolView === 'logs') {
    return 'logs'
  }
  return 'blockEditor'
}

export default function AppPage() {
  const resumeStateRef = useRef(loadDocumentResumeState())
  const { fetchProjects, restoreDocumentContext, currentDoc } = useDocumentsStore()
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
  const editorRef = useRef<BlockEditorHandle | null>(null)

  const [activeToolView, setActiveToolView] = useState<ToolView | null>(
    () => (resumeStateRef.current?.documentId ? 'blocks' : 'projects')
  )
  const [activeLibraryView, setActiveLibraryView] = useState<LibraryEditorView>('dies')
  const [mainEditorView, setMainEditorView] = useState<MainEditorView>('blockEditor')
  const [editorMeta, setEditorMeta] = useState<BlockEditorMeta>(EMPTY_EDITOR_META)

  const [selectedDieId, setSelectedDieId] = useState<number | null>(null)
  const [selectedDieAssemblyId, setSelectedDieAssemblyId] = useState<number | null>(null)
  const [selectedPressId, setSelectedPressId] = useState<number | null>(null)
  const [selectedMaterialId, setSelectedMaterialId] = useState<number | null>(null)

  useEffect(() => {
    let isCancelled = false

    const initialize = async () => {
      await fetchProjects()
      const resumeState = resumeStateRef.current
      if (isCancelled || !resumeState?.documentId) {
        return
      }

      setActiveToolView('blocks')
      setMainEditorView('blockEditor')
      await restoreDocumentContext(resumeState.projectId, resumeState.documentId)
    }

    void initialize()

    return () => {
      isCancelled = true
    }
  }, [fetchProjects, restoreDocumentContext])

  useEffect(() => {
    if (!currentDoc?.id) {
      return
    }

    saveDocumentResumeState({
      projectId: String(currentDoc.project_id),
      documentId: currentDoc.id,
    })
  }, [currentDoc?.id, currentDoc?.project_id])

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

  const handlePasteClipboardClip = (clipId?: string) => {
    const editor = editorRef.current
    if (!editor) {
      return
    }
    setMainEditorView('blockEditor')
    void editor.pasteClipboardClip(clipId)
  }

  const getSelectedBlockIds = () => editorMeta.selectedDocumentBlockIds
  const getSingleSelectedOrActiveBlockIds = () => {
    const selectedBlockIds = getSelectedBlockIds()
    if (selectedBlockIds.length === 1) {
      return selectedBlockIds
    }
    if (selectedBlockIds.length === 0 && editorMeta.activeDocumentBlockId) {
      return [editorMeta.activeDocumentBlockId]
    }
    return []
  }

  const handleCopySelectedBlockToClipboard = () => {
    const selectedBlockIds = getSelectedBlockIds()
    if (selectedBlockIds.length !== 1) {
      return
    }
    callEditor((editor) => editor.copyBlocksToClipboard(selectedBlockIds))
  }

  const handleCutSelectedBlockToClipboard = () => {
    const targetBlockIds = getSingleSelectedOrActiveBlockIds()
    if (targetBlockIds.length !== 1) {
      return
    }
    callEditor((editor) => editor.cutBlocksToClipboard(targetBlockIds))
  }

  const handleRemoveSelectedBlock = () => {
    const targetBlockIds = getSingleSelectedOrActiveBlockIds()
    if (targetBlockIds.length !== 1) {
      return
    }
    callEditor(async (editor) => {
      const removed = await editor.deleteBlocks(targetBlockIds)
      if (removed) {
        editor.clearSelectedBlocks()
      }
    })
  }

  const handlePasteAfterSelectedBlock = () => {
    const selectedBlockIds = getSelectedBlockIds()
    if (selectedBlockIds.length !== 1) {
      return
    }
    callEditor((editor) => editor.pasteClipboardClip(undefined, selectedBlockIds[0]))
  }

  const handleClearSelectedBlocks = () => {
    callEditor((editor) => editor.clearSelectedBlocks())
  }

  const hasDocument = (mainEditorView === 'blockEditor' || mainEditorView === 'operations') && Boolean(currentDoc?.id)

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
          documentTitle={currentDoc?.name ?? null}
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
            editorMeta={editorMeta}
            onCopySelectedBlockToClipboard={handleCopySelectedBlockToClipboard}
            onCutSelectedBlockToClipboard={handleCutSelectedBlockToClipboard}
            onRemoveSelectedBlock={handleRemoveSelectedBlock}
            onPasteAfterSelectedBlock={handlePasteAfterSelectedBlock}
            onClearSelectedBlocks={handleClearSelectedBlocks}
            onPasteClipboardClip={handlePasteClipboardClip}
          />

          <div className="flex-1 min-w-0 flex flex-col">
            {mainEditorView !== 'blockEditor' &&
            mainEditorView !== 'operations' &&
            mainEditorView !== 'simulationSteps' &&
            mainEditorView !== 'materials' &&
            mainEditorView !== 'simulation' &&
            mainEditorView !== 'logs' ? (
              <section className="border-b border-[rgba(55,53,47,0.09)] bg-[#fbfbfa] flex-shrink-0">
                <div className="ui-pane-header flex items-center justify-between gap-3">
                  <div className="ui-pane-title">Library actions</div>
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
              </section>
            ) : null}

            <MainEditorPane
              view={mainEditorView}
              blockEditorView={(
                <BlockEditor
                  ref={editorRef}
                  onMetaChange={setEditorMeta}
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
              logsView={<LogsView />}
              simulationStepsView={(
                <SimulationStepsView
                  documentId={currentDoc?.id ?? null}
                  isStepListVisible={activeToolView === 'simulationSteps'}
                  activeBlockId={editorMeta.activeDocumentBlockId}
                  hoveredBlockId={editorMeta.hoveredDocumentBlockId}
                />
              )}
              operationsView={(
                <div className="operations-workspace">
                  <div className="operations-document-pane">
                    <BlockEditor
                      ref={editorRef}
                      onMetaChange={setEditorMeta}
                    />
                  </div>
                  <DocumentOperationsView
                    documentId={currentDoc?.id ?? null}
                    blocks={editorMeta.documentBlocks}
                    activeBlockId={editorMeta.activeDocumentBlockId}
                    hoveredBlockId={editorMeta.hoveredDocumentBlockId}
                    hasUnsavedChanges={editorMeta.hasUnsavedChanges}
                    saveStatus={editorMeta.saveStatus}
                  />
                </div>
              )}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
