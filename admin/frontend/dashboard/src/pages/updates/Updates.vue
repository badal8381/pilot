<template>
  <div class="mx-auto max-w-3xl">
    <Teleport defer to="#header-actions">
      <Button
        variant="subtle"
        size="sm"
        :loading="loading"
        icon="lucide-refresh-cw"
        label="Refresh"
        tooltip="Refresh"
        @click="load"
      />
    </Teleport>

    <div v-if="loading && !operations.length" class="-mx-3">
      <ListRowSkeleton v-for="index in 6" :key="index" :index="index - 1" />
    </div>
    <div v-else-if="error" class="mt-4">
      <ErrorMessage :message="error" />
    </div>

    <div
      v-else-if="operations.length"
      class="flex flex-col -mx-3 divide-y divide-outline-gray-1"
    >
      <RouterLink
        v-for="op in operations"
        :key="op.id"
        :to="{ name: 'UpdateDetail', params: { operationId: op.id } }"
        class="items-center gap-3 grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] hover:bg-surface-gray-1 px-3 py-2.5 rounded no-underline transition-colors"
      >
        <div class="min-w-0">
          <!-- A block, not a span: `truncate` is inert on an inline box. -->
          <p class="font-medium text-ink-gray-9 text-base truncate">{{ opTitle(op) }}</p>
          <p class="mt-0.5 text-ink-gray-6 text-p-sm truncate">{{ subtitle(op) }}</p>
        </div>

        <!-- Completed is the norm; only exceptional states get a badge. -->
        <Badge
          v-if="badge(op)"
          :label="badge(op).label"
          :theme="badge(op).theme"
          variant="subtle"
        />
        <span v-else />
        <div class="flex justify-end items-center gap-3 min-w-0">
          <span class="text-ink-gray-6 text-sm truncate">{{ timing(op) }}</span>
          <span class="lucide-chevron-right size-4 text-ink-gray-6 shrink-0" />
        </div>
      </RouterLink>
    </div>

    <EmptyState
      v-else
      icon="lucide-git-pull-request-arrow"
      title="No updates yet"
      description="App updates across your sites appear here, with backup and recovery."
    />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { Badge, Button, ErrorMessage } from 'frappe-ui'
import EmptyState from '@/components/common/EmptyState.vue'
import ListRowSkeleton from '@/components/common/ListRowSkeleton.vue'
import { updatesApi } from '@/api/updates'
import { opTitle, pendingActionLabel, stateLabel, stateTone } from '@/utils/updateFormat'
import { fmtDateTime, fmtDuration, relativeTime } from '@/utils/taskFormat'

const operations = ref([])
const loading = ref(false)
const error = ref('')

function badge(op) {
  if (op.pending_action) return { label: pendingActionLabel(op.pending_action), theme: 'amber' }
  if (op.state === 'completed') return null
  const tone = stateTone(op.state)
  return { label: stateLabel(op.state), theme: tone === 'orange' ? 'amber' : tone }
}

// Two runs of the same apps share a title, so the run time stays on the row to tell them apart.
function subtitle(op) {
  const sites = op.sites || []
  const where = sites.length === 1 ? sites[0].name : `${sites.length} sites`
  return [where, fmtDateTime(op.started_at || op.created_at)].join(' · ')
}

function timing(op) {
  const parts = []
  if (op.finished_at && op.started_at) {
    parts.push(`took ${fmtDuration((new Date(op.finished_at) - new Date(op.started_at)) / 1000)}`)
  }
  parts.push(relativeTime(op.started_at || op.created_at))
  return parts.filter(Boolean).join(' · ')
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [current, history] = await Promise.all([
      updatesApi.current().catch(() => null),
      updatesApi.list({ limit: 50 }),
    ])
    const rows = history.data || []
    // Pin the active/unresolved operation at the top (it is also in history).
    operations.value = current ? [current, ...rows.filter((op) => op.id !== current.id)] : rows
  } catch (e) {
    error.value = e?.message || 'Could not load updates.'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
