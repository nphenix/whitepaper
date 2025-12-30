import React, { useState, useEffect } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import { Table } from '@tiptap/extension-table';
import TableRow from '@tiptap/extension-table-row';
import TableCell from '@tiptap/extension-table-cell';
import TableHeader from '@tiptap/extension-table-header';
import Placeholder from '@tiptap/extension-placeholder';
import { Heading1, Heading2, Heading3, Table as TableIcon, FileText, Quote } from 'lucide-react';

interface RichTextEditorProps {
  content: string;
  onChange?: (content: string) => void;
  editable?: boolean;
}

interface SlashCommand {
  title: string;
  description: string;
  icon: React.ReactNode;
  command: () => void;
}

export default function RichTextEditor({ content, onChange, editable = true }: RichTextEditorProps) {
  const [showSlashMenu, setShowSlashMenu] = useState(false);
  const [slashMenuPosition, setSlashMenuPosition] = useState({ x: 0, y: 0 });
  const [slashFilter, setSlashFilter] = useState('');
  const [slashStartPos, setSlashStartPos] = useState(0);

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: {
          levels: [1, 2, 3],
        },
      }),
      Table.configure({
        resizable: true,
      }),
      TableRow,
      TableHeader,
      TableCell,
      Placeholder.configure({
        placeholder: '输入 / 来查看命令...',
      }),
    ],
    content: convertMarkdownToHTML(content),
    editable,
    onUpdate: ({ editor }) => {
      const html = editor.getHTML();
      onChange?.(html);
    },
    editorProps: {
      attributes: {
        class: 'prose prose-lg max-w-none focus:outline-none',
      },
      handleKeyDown: (view, event) => {
        if (event.key === '/') {
          const { selection } = view.state;
          const pos = view.coordsAtPos(selection.from);
          setSlashMenuPosition({ x: pos.left, y: pos.bottom });
          setSlashFilter('');
          setSlashStartPos(selection.from);
          setTimeout(() => setShowSlashMenu(true), 0);
        } else if (showSlashMenu && event.key === 'Escape') {
          setShowSlashMenu(false);
        }
        return false;
      },
      handleTextInput: (_view, _from, _to, text) => {
        if (showSlashMenu && text !== '/') {
          setSlashFilter(prev => prev + text);
        }
        return false;
      },
    },
  });

  useEffect(() => {
    if (editor && content) {
      const htmlContent = convertMarkdownToHTML(content);
      if (editor.getHTML() !== htmlContent) {
        editor.commands.setContent(htmlContent);
      }
    }
  }, [content, editor]);

  const deleteTriggerText = () => {
    if (editor) {
      const currentPos = editor.state.selection.from;
      editor.chain().focus().deleteRange({ from: slashStartPos, to: currentPos }).run();
    }
  };

  const slashCommands: SlashCommand[] = [
    {
      title: '一级标题',
      description: '大号标题',
      icon: <Heading1 size={18} className="text-blue-600" />,
      command: () => {
        deleteTriggerText();
        editor?.chain().focus().toggleHeading({ level: 1 }).run();
        setShowSlashMenu(false);
      },
    },
    {
      title: '二级标题',
      description: '中号标题',
      icon: <Heading2 size={18} className="text-blue-600" />,
      command: () => {
        deleteTriggerText();
        editor?.chain().focus().toggleHeading({ level: 2 }).run();
        setShowSlashMenu(false);
      },
    },
    {
      title: '三级标题',
      description: '小号标题',
      icon: <Heading3 size={18} className="text-blue-600" />,
      command: () => {
        deleteTriggerText();
        editor?.chain().focus().toggleHeading({ level: 3 }).run();
        setShowSlashMenu(false);
      },
    },
    {
      title: '表格',
      description: '插入表格',
      icon: <TableIcon size={18} className="text-purple-600" />,
      command: () => {
        deleteTriggerText();
        editor?.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run();
        setShowSlashMenu(false);
      },
    },
    {
      title: '引用',
      description: '插入引用块',
      icon: <Quote size={18} className="text-green-600" />,
      command: () => {
        deleteTriggerText();
        editor?.chain().focus().toggleBlockquote().run();
        setShowSlashMenu(false);
      },
    },
    {
      title: '文献引用',
      description: '添加文献引用',
      icon: <FileText size={18} className="text-orange-600" />,
      command: () => {
        deleteTriggerText();
        editor?.chain().focus().insertContent('[引用]').run();
        setShowSlashMenu(false);
      },
    },
  ];

  const filteredCommands = slashCommands.filter(cmd =>
    cmd.title.toLowerCase().includes(slashFilter.toLowerCase()) ||
    cmd.description.toLowerCase().includes(slashFilter.toLowerCase())
  );

  if (!editor) {
    return null;
  }

  return (
    <div className="relative" data-testid="rich-text-editor">
      <EditorContent editor={editor} />

      {showSlashMenu && (
        <div
          className="fixed z-50 bg-white rounded-xl shadow-2xl border border-slate-200 overflow-hidden min-w-[280px] max-h-[400px] overflow-y-auto"
          style={{
            left: `${slashMenuPosition.x}px`,
            top: `${slashMenuPosition.y}px`,
          }}
        >
          <div className="p-2">
            <div className="text-xs text-slate-500 px-3 py-2 font-medium">基本块</div>
            {filteredCommands.map((cmd, index) => (
              <button
                key={index}
                onClick={cmd.command}
                className="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-gradient-to-r hover:from-blue-50 hover:to-blue-100 rounded-lg transition-all group text-left"
              >
                <div className="flex-shrink-0">{cmd.icon}</div>
                <div className="flex-1">
                  <div className="text-sm font-medium text-slate-900">{cmd.title}</div>
                  <div className="text-xs text-slate-500">{cmd.description}</div>
                </div>
              </button>
            ))}
            {filteredCommands.length === 0 && (
              <div className="px-3 py-4 text-sm text-slate-400 text-center">
                未找到匹配的命令
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function convertMarkdownToHTML(markdown: string): string {
  if (!markdown) return '';
  
  let html = markdown
    .replace(/^### (.*$)/gim, '<h3>$1</h3>')
    .replace(/^## (.*$)/gim, '<h2>$1</h2>')
    .replace(/^# (.*$)/gim, '<h1>$1</h1>')
    .replace(/\*\*(.*)\*\*/gim, '<strong>$1</strong>')
    .replace(/\*(.*)\*/gim, '<em>$1</em>')
    .replace(/\n/gim, '<br />');
  
  return html;
}
