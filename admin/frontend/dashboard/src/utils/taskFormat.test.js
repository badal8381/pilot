import assert from 'node:assert/strict'
import test from 'node:test'

import {
  isTaskActive,
  redirectRouteOnSuccess,
  relativeTime,
  siteRoute,
  statusConfig,
  taskActivityLabel,
} from './taskFormat.js'

test('queued tasks have their own presentation', () => {
  assert.equal(statusConfig({ status: 'queued' }).label, 'Queued')
  assert.equal(statusConfig({ status: 'queued' }).theme, 'blue')
  assert.equal(taskActivityLabel({ status: 'queued', queue_position: 3 }), 'Queued · #3 in queue')
})

test('queued and running tasks are active', () => {
  assert.equal(isTaskActive({ status: 'queued' }), true)
  assert.equal(isTaskActive({ status: 'running' }), true)
  assert.equal(isTaskActive({ status: 'success' }), false)
  assert.equal(isTaskActive(null), false)
})

test('task timing tolerates a missing timestamp', () => {
  assert.equal(relativeTime(null), '')
  assert.equal(taskActivityLabel({ status: 'success', started_at: null, queued_at: null }), '')
})

test('siteRoute links to the site behind a site-scoped task', () => {
  assert.deepEqual(siteRoute({ command: 'new-site', args: { name: 'a.local' } }), {
    name: 'SiteDetail',
    params: { name: 'a.local' },
  })
  assert.equal(siteRoute({ command: 'build', args: {} }), null)
})

test('site-creating and app tasks redirect to the site page on success', () => {
  assert.deepEqual(redirectRouteOnSuccess({ command: 'new-site', args: { name: 'a.local' } }), {
    name: 'SiteDetail',
    params: { name: 'a.local' },
  })
  assert.deepEqual(
    redirectRouteOnSuccess({ command: 'install-app', args: { site: 'a.local', app: 'erpnext' } }),
    {
      name: 'SiteDetail',
      params: { name: 'a.local' },
      query: { app: 'erpnext', action: 'install-app' },
    },
  )
  assert.deepEqual(
    redirectRouteOnSuccess({
      command: 'uninstall-app',
      args: { site: 'a.local', app: 'erpnext' },
    }),
    {
      name: 'SiteDetail',
      params: { name: 'a.local' },
      query: { app: 'erpnext', action: 'uninstall-app' },
    },
  )
  assert.deepEqual(
    redirectRouteOnSuccess({
      command: 'get-and-install-app',
      args: { site: 'a.local', marketplace_app: 'erpnext' },
    }),
    {
      name: 'SiteDetail',
      params: { name: 'a.local' },
      query: { app: 'erpnext', action: 'install-app' },
    },
  )
  assert.deepEqual(
    redirectRouteOnSuccess({ command: 'get-and-install-app', args: { site: 'a.local', repo: 'x' } }),
    { name: 'SiteDetail', params: { name: 'a.local' } },
  )
  // A dropped site has no detail page left to land on.
  assert.deepEqual(redirectRouteOnSuccess({ command: 'drop-site', args: { site: 'a.local' } }), {
    name: 'Sites',
  })
  assert.equal(redirectRouteOnSuccess({ command: 'backup-site', args: { site: 'a.local' } }), null)
})
