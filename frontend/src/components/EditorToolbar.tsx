import type { Editor } from '@tiptap/react'

interface EditorToolbarProps {
  editor: Editor
}

export default function EditorToolbar({ editor }: EditorToolbarProps) {
  if (!editor) return null

  const buttons = [
    {
      name: 'Bold',
      isActive: editor.isActive('bold'),
      onClick: () => editor.chain().focus().toggleBold().run(),
    },
    {
      name: 'Italic',
      isActive: editor.isActive('italic'),
      onClick: () => editor.chain().focus().toggleItalic().run(),
    },
    {
      name: 'Strike',
      isActive: editor.isActive('strike'),
      onClick: () => editor.chain().focus().toggleStrike().run(),
    },
    {
      name: 'Code',
      isActive: editor.isActive('code'),
      onClick: () => editor.chain().focus().toggleCode().run(),
    },
    { name: '|', isActive: false, onClick: () => {} }, // Separator
    {
      name: 'H1',
      isActive: editor.isActive('heading', { level: 1 }),
      onClick: () => editor.chain().focus().toggleHeading({ level: 1 }).run(),
    },
    {
      name: 'H2',
      isActive: editor.isActive('heading', { level: 2 }),
      onClick: () => editor.chain().focus().toggleHeading({ level: 2 }).run(),
    },
    {
      name: 'H3',
      isActive: editor.isActive('heading', { level: 3 }),
      onClick: () => editor.chain().focus().toggleHeading({ level: 3 }).run(),
    },
    { name: '|', isActive: false, onClick: () => {} },
    {
      name: 'Bullet List',
      isActive: editor.isActive('bulletList'),
      onClick: () => editor.chain().focus().toggleBulletList().run(),
    },
    {
      name: 'Ordered List',
      isActive: editor.isActive('orderedList'),
      onClick: () => editor.chain().focus().toggleOrderedList().run(),
    },
    {
      name: 'Task List',
      isActive: editor.isActive('taskList'),
      onClick: () => editor.chain().focus().toggleTaskList().run(),
    },
    { name: '|', isActive: false, onClick: () => {} },
    {
      name: 'Code Block',
      isActive: editor.isActive('codeBlock'),
      onClick: () => editor.chain().focus().toggleCodeBlock().run(),
    },
    {
      name: 'Quote',
      isActive: editor.isActive('blockquote'),
      onClick: () => editor.chain().focus().toggleBlockquote().run(),
    },
    { name: '|', isActive: false, onClick: () => {} },
    {
      name: 'Undo',
      isActive: false,
      onClick: () => editor.chain().focus().undo().run(),
    },
    {
      name: 'Redo',
      isActive: false,
      onClick: () => editor.chain().focus().redo().run(),
    },
  ]

  return (
    <div className="tiptap-toolbar">
      {buttons.map((button, index) =>
        button.name === '|' ? (
          <div key={index} className="w-px bg-gray-300 mx-1"></div>
        ) : (
          <button
            key={index}
            onClick={button.onClick}
            className={button.isActive ? 'is-active' : ''}
            type="button"
          >
            {button.name}
          </button>
        )
      )}
    </div>
  )
}
