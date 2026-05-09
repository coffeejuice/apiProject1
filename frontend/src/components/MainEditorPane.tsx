import type { ReactNode } from 'react'

import type { MainEditorView } from './editorPaneTypes'

interface MainEditorPaneProps {
  view: MainEditorView
  blockEditorView: ReactNode
  diesView: ReactNode
  dieAssembliesView: ReactNode
  pressesView: ReactNode
  materialsView: ReactNode
  simulationView: ReactNode
  operationsView: ReactNode
  simulationStepsView: ReactNode
  logsView: ReactNode
}

export default function MainEditorPane({
  view,
  blockEditorView,
  diesView,
  dieAssembliesView,
  pressesView,
  materialsView,
  simulationView,
  operationsView,
  simulationStepsView,
  logsView,
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

  if (view === 'materials') {
    return <div className="flex-1 min-h-0">{materialsView}</div>
  }

  if (view === 'simulation') {
    return <div className="flex-1 min-h-0">{simulationView}</div>
  }

  if (view === 'operations') {
    return <div className="flex-1 min-h-0">{operationsView}</div>
  }

  if (view === 'simulationSteps') {
    return <div className="flex-1 min-h-0">{simulationStepsView}</div>
  }

  if (view === 'logs') {
    return <div className="flex-1 min-h-0">{logsView}</div>
  }

  return <div className="flex-1 min-h-0">{blockEditorView}</div>
}
