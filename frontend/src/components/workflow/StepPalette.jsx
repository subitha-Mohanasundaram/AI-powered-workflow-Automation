import { Globe, Mail, Code2, Bell, Clock, Database, Zap, FileText, Search, BarChart2 } from 'lucide-react'

const steps = [
  { type: 'http_request', label: 'HTTP Request', icon: Globe, color: 'text-blue-400' },
  { type: 'send_email', label: 'Send Email', icon: Mail, color: 'text-emerald-400' },
  { type: 'run_script', label: 'Run Script', icon: Code2, color: 'text-yellow-400' },
  { type: 'send_notification', label: 'Notification', icon: Bell, color: 'text-violet-400' },
  { type: 'wait', label: 'Wait / Delay', icon: Clock, color: 'text-slate-400' },
  { type: 'database_query', label: 'DB Query', icon: Database, color: 'text-orange-400' },
  { type: 'trigger', label: 'Trigger', icon: Zap, color: 'text-brand' },
  { type: 'parse_data', label: 'Parse Data', icon: FileText, color: 'text-pink-400' },
  { type: 'web_search', label: 'Web Search', icon: Search, color: 'text-cyan-400' },
  { type: 'transform', label: 'Transform', icon: BarChart2, color: 'text-indigo-400' },
]

export default function StepPalette() {
  const onDragStart = (e, nodeType) => {
    e.dataTransfer.setData('application/reactflow', nodeType)
    e.dataTransfer.effectAllowed = 'move'
  }

  return (
    <aside className="w-52 flex-shrink-0 flex flex-col glass border-r border-white/10 overflow-y-auto">
      <div className="px-4 py-3 border-b border-white/10">
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Step Palette</h3>
        <p className="text-xs text-slate-600 mt-0.5">Drag to canvas</p>
      </div>
      <div className="p-2 space-y-1">
        {steps.map(({ type, label, icon: Icon, color }) => (
          <div
            key={type}
            draggable
            onDragStart={(e) => onDragStart(e, type)}
            className="flex items-center gap-2.5 px-3 py-2.5 rounded-lg border border-white/5 bg-surface-dark/50
                       hover:border-brand/30 hover:bg-brand/5 cursor-grab active:cursor-grabbing
                       transition-all duration-150 group"
          >
            <Icon className={`w-4 h-4 flex-shrink-0 ${color}`} />
            <span className="text-xs text-slate-300 group-hover:text-slate-100">{label}</span>
          </div>
        ))}
      </div>
    </aside>
  )
}
