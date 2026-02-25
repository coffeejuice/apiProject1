export type ToolView = 'projects' | 'documents' | 'blocksLibrary' | 'users'

interface ToolsSwitcherProps {
  activeView: ToolView | null
  onToggleView: (view: ToolView) => void
}

const TOOL_ITEMS: Array<{ id: ToolView; label: string; short: string }> = [
  { id: 'projects', label: 'Projects', short: 'P' },
  { id: 'documents', label: 'Documents', short: 'D' },
  { id: 'blocksLibrary', label: 'BlocksLibrary', short: 'B' },
  { id: 'users', label: 'Users', short: 'U' },
]

export default function ToolsSwitcher({ activeView, onToggleView }: ToolsSwitcherProps) {
  return (
    <aside className="ui-pane w-16 items-center py-2 gap-2">
      {TOOL_ITEMS.map((item) => {
        const isActive = activeView === item.id

        return (
          <button
            key={item.id}
            type="button"
            onClick={() => onToggleView(item.id)}
            title={item.label}
            className={`ui-btn w-10 h-10 p-0 font-semibold ${
              isActive
                ? 'border-blue-600 bg-blue-50 text-blue-700'
                : 'text-gray-700'
            }`}
          >
            {item.short}
          </button>
        )
      })}
    </aside>
  )
}
