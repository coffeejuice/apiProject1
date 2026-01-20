import { useEffect, useState } from 'react'
import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import TaskList from '@tiptap/extension-task-list'
import TaskItem from '@tiptap/extension-task-item'
import { useDocumentsStore } from '../stores/useDocumentsStore'
import { useEditorStore } from '../stores/useEditorStore'
import EditorToolbar from './EditorToolbar'
import RevisionHistory from './RevisionHistory'
import ImportExport from './ImportExport'

export default function Editor() {
  const [title, setTitle] = useState('')
  const [showHistory, setShowHistory] = useState(false)
  const [showImportExport, setShowImportExport] = useState(false)
  const [titleSaveTimeout, setTitleSaveTimeout] = useState<NodeJS.Timeout | null>(null)

  const { currentDoc, updateLocalDoc, updateDocument } = useDocumentsStore()
  const {
    content,
    setContent,
    markDirty,
    save,
    saveStatus,
    lastSavedRevNumber,
    setLastSavedRevNumber,
    loadBlocksFromBackend,
    reset,
  } = useEditorStore()

  const editor = useEditor({
    extensions: [
      StarterKit,
      TaskList,
      TaskItem.configure({
        nested: true,
      }),
    ],
    content: '',
    onUpdate: ({ editor }) => {
      const json = editor.getJSON()
      setContent(json)
      markDirty()
    },
  })

  // Load document content when currentDoc changes
  useEffect(() => {
    if (!currentDoc) {
      reset()
      setTitle('')
      editor?.commands.setContent('')
      return
    }

    const loadDocument = async () => {
      setTitle(currentDoc.title || '')

      // Load blocks from backend to track IDs
      await loadBlocksFromBackend(currentDoc.id.toString())

      // Load content - try localStorage first, then backend data
      let docContent
      try {
        const savedContent = localStorage.getItem(`doc_${currentDoc.id}_content`)
        if (savedContent) {
          docContent = JSON.parse(savedContent)
        }
      } catch (e) {
        // Ignore parse errors
      }

      if (!docContent) {
        docContent = currentDoc.content || {
          type: 'doc',
          content: [{ type: 'paragraph' }],
        }
      }

      editor?.commands.setContent(docContent)
      setContent(docContent)

      // Set revision number
      const revNumber = currentDoc.rev_number || 0
      setLastSavedRevNumber(revNumber)
    }

    loadDocument()
  }, [currentDoc, editor, reset, setContent, setLastSavedRevNumber, loadBlocksFromBackend])

  // Autosave logic
  useEffect(() => {
    if (!currentDoc) return

    let saveTimeout: NodeJS.Timeout
    let intervalTimeout: NodeJS.Timeout

    const performSave = async () => {
      await save(currentDoc.id)
    }

    // Debounced save after 800ms idle
    saveTimeout = setTimeout(performSave, 800)

    // Force save every 10s if dirty
    intervalTimeout = setInterval(() => {
      if (saveStatus === 'idle') {
        performSave()
      }
    }, 10000)

    return () => {
      clearTimeout(saveTimeout)
      clearInterval(intervalTimeout)
    }
  }, [content, currentDoc, save, saveStatus])

  const handleTitleChange = (newTitle: string) => {
    setTitle(newTitle)
    if (currentDoc) {
      updateLocalDoc(currentDoc.id, { title: newTitle })

      // Clear any pending save
      if (titleSaveTimeout) {
        clearTimeout(titleSaveTimeout)
      }

      // Debounce backend update
      const timeoutId = setTimeout(async () => {
        await updateDocument(currentDoc.id, { title: newTitle })
        setTitleSaveTimeout(null)
      }, 1000)

      setTitleSaveTimeout(timeoutId)
    }
  }

  if (!currentDoc || !editor) {
    return null
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="border-b border-gray-200 bg-white p-4">
        <div className="flex items-center justify-between mb-4">
          <input
            type="text"
            value={title}
            onChange={(e) => handleTitleChange(e.target.value)}
            className="text-2xl font-bold border-none outline-none flex-1"
            placeholder="Untitled Document"
          />

          <div className="flex items-center gap-4">
            {/* Save Status */}
            <div className="text-sm">
              {saveStatus === 'saving' && (
                <span className="text-blue-600">Saving...</span>
              )}
              {saveStatus === 'saved' && (
                <span className="text-green-600" title="Saved to database">
                  Saved
                </span>
              )}
              {saveStatus === 'error' && (
                <span className="text-red-600">Error saving</span>
              )}
              {saveStatus === 'idle' && <span className="text-gray-400">-</span>}
            </div>

            {/* Action Buttons */}
            <button
              onClick={() => setShowHistory(true)}
              className="px-3 py-1.5 text-sm border border-gray-300 rounded hover:bg-gray-50"
            >
              History
            </button>
            <button
              onClick={() => setShowImportExport(true)}
              className="px-3 py-1.5 text-sm border border-gray-300 rounded hover:bg-gray-50"
            >
              Import/Export
            </button>
          </div>
        </div>

        {/* Revision info */}
        <div className="text-xs text-gray-500">
          Revision: {lastSavedRevNumber}
        </div>
      </div>

      {/* Toolbar */}
      <EditorToolbar editor={editor} />

      {/* Editor Content */}
      <div className="flex-1 overflow-y-auto bg-gray-100">
        <div className="max-w-4xl mx-auto py-8">
          <EditorContent editor={editor} className="tiptap prose max-w-none" />
        </div>
      </div>

      {/* Modals */}
      {showHistory && (
        <RevisionHistory
          documentId={currentDoc.id}
          onClose={() => setShowHistory(false)}
        />
      )}

      {showImportExport && (
        <ImportExport
          documentId={currentDoc.id}
          onClose={() => setShowImportExport(false)}
        />
      )}
    </div>
  )
}
