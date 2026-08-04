import assert from 'node:assert/strict'
import test from 'node:test'

import { siteStorageBytes } from './storage.js'

test('siteStorageBytes sums site files and its database schemas', () => {
  const breakdown = {
    bench: {
      sites: [
        { name: 'a.localhost', bytes: 100 },
        { name: 'b.localhost', bytes: 7 },
      ],
    },
    database: {
      databases: [
        { schema: '_a', site: 'a.localhost', bytes: 40 },
        { schema: '_b', site: 'b.localhost', bytes: 5 },
        { schema: 'mysql', site: null, bytes: 999 },
      ],
    },
  }
  assert.equal(siteStorageBytes(breakdown, 'a.localhost'), 140)
  assert.equal(siteStorageBytes(breakdown, 'b.localhost'), 12)
})

test('siteStorageBytes is 0 for an unknown site or empty breakdown', () => {
  assert.equal(siteStorageBytes({}, 'missing.localhost'), 0)
  assert.equal(siteStorageBytes(null, 'missing.localhost'), 0)
})
