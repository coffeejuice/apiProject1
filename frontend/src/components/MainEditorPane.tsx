import type { ReactNode } from 'react'

import type { MainEditorView } from './editorPaneTypes'

interface MainEditorPaneProps {
  view: MainEditorView
  blockEditorView: ReactNode
  diesView: ReactNode
  dieAssembliesView: ReactNode
  pressesView: ReactNode
  materialsView: ReactNode
}

export default function MainEditorPane({
  view,
  blockEditorView,
  diesView,
  dieAssembliesView,
  pressesView,
  materialsView,
}: MainEditorPaneProps) {
  if (view === 'blockEditor') {
    return <div className="flex-1 min-h-0">{blockEditorView}</div>
  }

  if (view === 'dies') {
    return <div className="flex-1 min-h-0">{diesView}</div>
  }

  if (view === 'dieAssemblies') {
    return <div className="flex-1 min-h-0">{dieAssembliesView}</div>
  }

  if (view === 'presses') {
    return <div className="flex-1 min-h-0">{pressesView}</div>
  }

  return <div className="flex-1 min-h-0">{materialsView}</div>
}
