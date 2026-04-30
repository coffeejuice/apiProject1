import Tooltip from './ui/Tooltip'

import type { ReactElement } from 'react'

export type ToolView = 'projects' | 'documents' | 'blocks' | 'library' | 'simulation' | 'users'

interface ToolsSwitcherProps {
  activeView: ToolView | null
  onToggleView: (view: ToolView) => void
}

function ProjectsIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <path
        d="M3.5 5.5A1.5 1.5 0 0 1 5 4h3l1.25 1.5H15A1.5 1.5 0 0 1 16.5 7v8A1.5 1.5 0 0 1 15 16.5H5A1.5 1.5 0 0 1 3.5 15V5.5Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function DocumentsIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <path
        d="M6 3.5h5l3 3V15A1.5 1.5 0 0 1 12.5 16.5h-6A1.5 1.5 0 0 1 5 15V5A1.5 1.5 0 0 1 6.5 3.5Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M11 3.75V7h3.25" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M7.5 10h5M7.5 12.75h5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
}

function BlocksIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <rect x="3.5" y="3.5" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.5" />
      <rect x="11.5" y="3.5" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.5" />
      <rect x="3.5" y="11.5" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.5" />
      <rect x="11.5" y="11.5" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  )
}

function LibraryIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <path
        d="M4 5.5c0-.83.67-1.5 1.5-1.5H9v11H5.5A1.5 1.5 0 0 1 4 13.5v-8Zm12 0c0-.83-.67-1.5-1.5-1.5H11v11h3.5a1.5 1.5 0 0 0 1.5-1.5v-8Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M10 4v11M6 7h1.5M12.5 7H14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
}

function UsersIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <path
        d="M7 8.25a2.25 2.25 0 1 0 0-4.5 2.25 2.25 0 0 0 0 4.5Zm6 0a1.9 1.9 0 1 0 0-3.8 1.9 1.9 0 0 0 0 3.8ZM3.75 15.5v-.75A3.75 3.75 0 0 1 7.5 11h.5a3.75 3.75 0 0 1 3.75 3.75v.75M11.75 15.5v-.5a3 3 0 0 1 3-3h.25a3 3 0 0 1 3 3v.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function SimulationIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
      <path
        d="M6 4.75v10.5c0 .45.5.72.88.47l8-5.25a.56.56 0 0 0 0-.94l-8-5.25A.56.56 0 0 0 6 4.75Z"
        fill="currentColor"
      />
    </svg>
  )
}

const TOOL_ITEMS: Array<{ id: ToolView; label: string; icon: ({ className }: { className?: string }) => ReactElement }> = [
  { id: 'projects', label: 'Projects', icon: ProjectsIcon },
  { id: 'documents', label: 'Documents', icon: DocumentsIcon },
  { id: 'blocks', label: 'Blocks', icon: BlocksIcon },
  { id: 'library', label: 'Library', icon: LibraryIcon },
  { id: 'simulation', label: 'Simulation', icon: SimulationIcon },
  { id: 'users', label: 'Users', icon: UsersIcon },
]

export default function ToolsSwitcher({ activeView, onToggleView }: ToolsSwitcherProps) {
  return (
    <aside className="ui-pane w-16 items-center py-2 gap-2">
      {TOOL_ITEMS.map((item) => {
        const isActive = activeView === item.id
        const Icon = item.icon

        return (
          <Tooltip key={item.id} content={item.label}>
            <button
              type="button"
              onClick={() => onToggleView(item.id)}
              aria-label={item.label}
              className={`ui-btn h-9 w-9 p-0 font-semibold ${
                isActive
                  ? 'bg-[rgba(55,53,47,0.09)] text-[rgba(55,53,47,0.92)]'
                  : 'text-[rgba(55,53,47,0.58)]'
              }`}
            >
              <Icon className="h-[18px] w-[18px]" />
            </button>
          </Tooltip>
        )
      })}
    </aside>
  )
}
