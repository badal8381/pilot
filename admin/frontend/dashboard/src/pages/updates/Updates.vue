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
        class="flex items-center gap-3 hover:bg-surface-gray-1 px-3 py-2.5 rounded no-underline transition-colors"
      >
        <span
          class="place-items-center grid rounded size-6 shrink-0"
          :class="rowIcon(op).iconBg"
        >
          <span class="size-3.5" :class="rowIcon(op).icon" />
        </span>

        <div class="flex-1 min-w-0">
          <!-- A block, not a span: `truncate` is inert on an inline box. -->
          <p class="font-medium text-ink-gray-9 text-base truncate">{{ opTitle(op) }}</p>
          <p class="mt-0.5 text-ink-gray-6 text-p-sm truncate">{{ subtitle(op) }}</p>
        </div>

        <span class="text-ink-gray-6 text-sm shrink-0">{{ timing(op) }}</span>
        <span class="lucide-chevron-right size-4 text-ink-gray-6 shrink-0" />
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
import { Button, ErrorMessage } from 'frappe-ui'
import EmptyState from '@/components/common/EmptyState.vue'
import ListRowSkeleton from '@/components/common/ListRowSkeleton.vue'
import { updatesApi } from '@/api/updates'
import { appsSummary, opTitle, pendingActionLabel, stateIcon, stateLabel } from '@/utils/updateFormat'
import { fmtDuration, relativeTime } from '@/utils/taskFormat'

const operations = ref([])
const loading = ref(false)
const error = ref('')

const rowIcon = (op) => stateIcon(op.pending_action ? 'retrying' : op.state)

function subtitle(op) {
  const count = op.sites?.length || 0
  const parts = [
    op.pending_action ? pendingActionLabel(op.pending_action) : stateLabel(op.state),
    `${count} site${count === 1 ? '' : 's'}`,
    appsSummary(op),
  ]
  return parts.filter(Boolean).join(' · ')
}

// Duration and age live together on the right, the way the task rows read them.
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
