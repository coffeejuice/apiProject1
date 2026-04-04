import type { ReactNode } from 'react'

import type { MainEditorView } from './editorPaneTypes'

interface TopEditorPaneProps {
  view: MainEditorView
  isVisible: boolean
  visualEditorView: ReactNode
  libraryActionsView: ReactNode
}

export default function TopEditorPane({
  view,
  isVisible,
  visualEditorView,
  libraryActionsView,
}: TopEditorPaneProps) {
  if (view === 'blockEditor') {
    if (!isVisible) {
      return null
    }
    return <>{visualEditorView}</>
  }

  return (
    <section className="border-b border-gray-200 bg-white flex-shrink-0">
      {libraryActionsView}
    </section>
  )
}
