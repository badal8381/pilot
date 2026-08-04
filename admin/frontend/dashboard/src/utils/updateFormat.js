import { fmtDateTime } from './taskFormat.js'

export const ACTIVE_STATES = [
  'preparing',
  'backing_up',
  'updating',
  'migrating',
  'retrying',
  'reverting_apps',
  'reverting_sites',
  'restarting',
]
export const ATTENTION_STATES = ['needs_attention', 'revert_failed']

// The API's status filter matches one state exactly, so these groups can only
// be applied client-side.
const FILTER_STATES = {
  active: ACTIVE_STATES,
  attention: ATTENTION_STATES,
  completed: ['completed'],
  reverted: ['reverted'],
}

// One-word labels: five of them have to fit a 375px phone without scrolling.
export const UPDATE_FILTERS = [
  { label: 'All', value: 'all' },
  { label: 'Running', value: 'active' },
  { label: 'Attention', value: 'attention' },
  { label: 'Completed', value: 'completed' },
  { label: 'Reverted', value: 'reverted' },
]

// Every state belongs to exactly one group, so no update is unreachable.
export function matchesUpdateFilter(operation, filter) {
  if (filter === 'all') return true
  return (FILTER_STATES[filter] || []).includes(operation?.state)
}

export function opTitle(op) {
  if (op?.kind === 'site_migrate') return `Migrate ${op.sites?.[0]?.name || 'site'}`
  // Operations store no name; two picked apps read fine by name, more become a count.
  const picked = op?.apps_filter || []
  if (picked.length && picked.length <= 2) return `Update ${picked.join(', ')}`
  const count = picked.length || op?.apps?.length || 0
  if (count) return `Update ${count} app${count === 1 ? '' : 's'}`
  return fmtDateTime(op?.started_at || op?.created_at)
}

/**
 * The Site column. One site reads by name; several would outgrow the column, so
 * they collapse to a count and `siteNames` carries the full list into the cell's
 * tooltip. An operation touching no site is bench-level work.
 */
export function sitesLabel(op) {
  const sites = op?.sites || []
  if (!sites.length) return 'Server'
  if (sites.length === 1) return sites[0].name
  return `${sites.length} sites`
}

export function siteNames(op) {
  return (op?.sites || []).map((site) => site.name).join(', ')
}

export function patchSkipped(op) {
  const patch = op?.diagnosis?.patch
  if (!patch) return false
  return (op.decisions || []).some(
    (decision) =>
      decision.action === 'bypass_patch' &&
      decision.patch === patch &&
      decision.site === op.failed_site,
  )
}

const ACTION_LABEL = {
  retry: 'Retry',
  restore: 'Restore',
  bypass_patch: 'Skip patch',
}

export function pendingActionLabel(pending) {
  if (!pending) return ''
  const action = ACTION_LABEL[pending.role] || 'Action'
  return pending.status === 'running' ? `${action} in progress` : `${action} queued`
}

const STATE_TONE = {
  completed: 'green',
  reverted: 'blue',
  needs_attention: 'red',
  revert_failed: 'red',
  preparing: 'orange',
  backing_up: 'orange',
  updating: 'orange',
  migrating: 'orange',
  retrying: 'orange',
  reverting_apps: 'orange',
  reverting_sites: 'orange',
  restarting: 'orange',
}

const STATE_LABEL = {
  completed: 'Completed',
  reverted: 'Reverted',
  needs_attention: 'Needs attention',
  revert_failed: 'Revert failed',
  preparing: 'Preparing',
  backing_up: 'Backing up',
  updating: 'Updating',
  migrating: 'Migrating',
  retrying: 'Retrying',
  reverting_apps: 'Reverting apps',
  reverting_sites: 'Recovering sites',
  restarting: 'Restarting services',
}

export function stateTone(state) {
  return STATE_TONE[state] || 'gray'
}

export function stateLabel(state) {
  return STATE_LABEL[state] || state
}

// Per-site lifecycle: pending -> backing up -> running -> success / failed / recovered
export function siteStatus(site) {
  if (site.migration_status === 'recovering')
    return { label: 'Recovering', tone: 'orange', busy: true, value: 'recovering' }
  if (site.migration_status === 'recovered')
    return { label: 'Recovered', tone: 'green', value: 'recovered' }
  if (site.migration_status === 'success')
    return { label: 'Success', tone: 'green', value: 'success' }
  if (site.migration_status === 'running')
    return { label: 'Migrating', tone: 'orange', busy: true, value: 'running' }
  if (site.migration_status === 'failed') return { label: 'Failed', tone: 'red', value: 'failed' }
  if (site.backup_status === 'backing_up')
    return { label: 'Backing up', tone: 'orange', busy: true, value: 'backing_up' }
  if (site.backup_status === 'failed') return { label: 'Failed', tone: 'red', value: 'failed' }
  if (site.backup_status === 'backed_up')
    return { label: 'Backed up', tone: 'blue', value: 'backed_up' }
  if (site.backup_status === 'unsupported')
    return { label: 'Backup skipped', tone: 'gray', value: 'unsupported' }
  return { label: 'Pending', tone: 'gray', value: 'pending' }
}
