import { commandLabel, relativeTime } from '@/utils/taskFormat'

const typeMetaMap = {
  backup: { icon: 'lucide-database', iconBg: 'bg-surface-blue-2 text-ink-blue-7' },
  app: { icon: 'lucide-package', iconBg: 'bg-surface-purple-2 text-ink-purple-7' },
  session: { icon: 'lucide-key-round', iconBg: 'bg-surface-amber-2 text-ink-amber-7' },
  ssh_key: { icon: 'lucide-key', iconBg: 'bg-surface-gray-2 text-ink-gray-7' },
  git: { icon: 'lucide-git-branch', iconBg: 'bg-surface-gray-2 text-ink-gray-7' },
  task: { icon: 'lucide-list-checks', iconBg: 'bg-surface-blue-2 text-ink-blue-7' },
  bypass_patch: { icon: 'lucide-wrench', iconBg: 'bg-surface-red-2 text-ink-red-7' },
}

const defaultTypeMeta = { icon: 'lucide-activity', iconBg: 'bg-surface-gray-2 text-ink-gray-7' }

export function activityTypeMeta(entry) {
  return typeMetaMap[entry.type] || defaultTypeMeta
}

export function activityTypeIcon(type) {
  return (typeMetaMap[type] || defaultTypeMeta).icon
}

const typeLabels = {
  backup: 'Backup',
  app: 'App',
  session: 'Session',
  ssh_key: 'SSH key',
  git: 'Git',
  task: 'Task',
  bypass_patch: 'Patch',
}

export const activityTypeOptions = [
  { label: 'All types', value: '', icon: 'lucide-layout-grid' },
  ...Object.entries(typeLabels).map(([value, label]) => ({
    label,
    value,
    icon: activityTypeIcon(value),
  })),
]

const sessionEventLabels = {
  login_redeemed: 'Signed in with a login link',
  issued: 'Session started',
  revoked: 'Session logged out',
  other_sessions_revoked: 'Other sessions logged out',
  admin_password_changed: 'Admin password changed',
  two_factor_device_added: 'Two-factor device added',
  two_factor_device_removed: 'Two-factor device removed',
  recovery_codes_regenerated: 'Recovery codes regenerated',
}

export function activityLabel(entry) {
  const site = entry.site ? ` on ${entry.site}` : ''
  switch (entry.type) {
    case 'backup':
      if (entry.event === 'download') return `Backup file downloaded${site}`
      if (entry.event === 'delete') return `Backup deleted${site}`
      return `Backup ${entry.status === 'failed' ? 'failed' : 'completed'}${site}`
    case 'app':
      return `App ${entry.app} ${entry.event}${site}`
    case 'session':
      return sessionEventLabels[entry.event] || 'Session updated'
    case 'ssh_key':
      return entry.event === 'added' ? 'SSH key added' : 'SSH key removed'
    case 'git':
      return entry.event === 'connected'
        ? `Connected ${entry.provider} account${entry.username ? ` (${entry.username})` : ''}`
        : 'Git account disconnected'
    case 'task':
      return `Queued ${commandLabel(entry.command)}`
    case 'bypass_patch':
      return `Bypassed patch${site}`
    default:
      return entry.event ? `${entry.type} ${entry.event}` : entry.type
  }
}

export function activityResourceRoute(entry) {
  if (entry.site) return { name: 'SiteDetail', params: { name: entry.site } }
  if (entry.type === 'task' && entry.task_id)
    return { name: 'TaskDetail', params: { taskId: entry.task_id } }
  return null
}

export function activityResourceLabel(entry) {
  if (entry.site) return entry.site
  if (entry.type === 'task' && entry.task_id) return entry.task_id
  return ''
}

export function activityActorLabel(entry) {
  return entry.actor || entry.ip || 'System'
}

export function activityTime(entry) {
  return relativeTime(entry.logged_at)
}
