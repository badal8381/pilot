<template>
  <div class="mx-auto max-w-3xl">
    <StickyToolbar class="flex sm:flex-row flex-col sm:items-center gap-2">
      <TabButtons
        class="shrink-0"
        :size="isMobile ? 'md' : 'sm'"
        :options="filterOptions"
        :modelValue="statusFilter"
        @update:modelValue="onFilterChange"
      />
      <div class="flex flex-1 items-center gap-2 min-w-0">
        <Dropdown :options="typeMenu" placement="bottom-start">
          <template #default="{ open }">
            <Button
              variant="subtle"
              :size="isMobile ? 'md' : 'sm'"
              :active="open"
              class="[&>.truncate]:text-left text-base"
            >
              <template #suffix><span class="size-4 shrink-0 lucide-chevron-down" /></template>
              {{ typeLabel }}
            </Button>
          </template>
        </Dropdown>
        <div class="flex-1 sm:flex-none min-w-0">
          <Dropdown :options="siteMenu" placement="bottom-start">
            <template #default="{ open }">
              <Button
                variant="subtle"
                :size="isMobile ? 'md' : 'sm'"
                :active="open"
                class="[&>.truncate]:flex-1 [&>.truncate]:text-left text-base w-full sm:w-auto min-w-0"
              >
                <template #suffix><span class="size-4 shrink-0 lucide-chevron-down" /></template>
                {{ siteLabelText }}
              </Button>
            </template>
          </Dropdown>
        </div>
        <Button
          class="ml-auto sm:ml-auto"
          variant="subtle"
          :size="isMobile ? 'md' : 'sm'"
          icon="lucide-refresh-cw"
          label="Refresh"
          tooltip="Refresh"
          :loading="loading"
          @click="load(statusFilter)"
        />
      </div>
    </StickyToolbar>

    <div v-if="loading" class="-mx-3 mt-4">
      <ListRowSkeleton v-for="index in 6" :key="index" :index="index - 1" />
    </div>
    <div v-else-if="error" class="mt-4">
      <ErrorMessage :message="error" />
    </div>

    <div
      v-else-if="visibleTasks.length"
      class="flex flex-col -mx-3 mt-4 divide-y divide-outline-gray-1"
    >
      <RouterLink
        v-for="task in visibleTasks"
        :key="task.task_id"
        :to="taskDetailRoute(task.task_id)"
        class="flex items-center gap-3 hover:bg-surface-gray-2 px-3 py-2.5 rounded no-underline transition-colors"
      >
        <span
          class="place-items-center grid rounded size-6 shrink-0"
          :class="statusConfig(task).iconBg"
        >
          <span class="size-3.5" :class="statusConfig(task).icon" />
        </span>

        <div class="flex-1 min-w-0">
          <!-- truncate is inert on inline boxes. -->
          <p class="font-medium text-ink-gray-9 text-base truncate">
            {{ commandLabel(task.command) }}
          </p>
          <p class="mt-0.5 text-ink-gray-6 text-p-sm truncate">
            {{ siteLabel(task) }}
            <template v-if="task.status === 'queued' && task.queue_position">
              · #{{ task.queue_position }} in queue</template
            >
          </p>
        </div>

        <span class="text-ink-gray-6 text-sm shrink-0">
          <template v-if="task.status !== 'queued' && fmtDuration(task.duration_seconds)"
            >took {{ fmtDuration(task.duration_seconds) }} · </template
          >{{ relativeTime(task.started_at || task.queued_at) }}
        </span>
        <span class="lucide-chevron-right size-4 text-ink-gray-6 shrink-0" />
      </RouterLink>
    </div>

    <EmptyState
      v-else
      class="mt-4"
      icon="lucide-list-checks"
      :title="isFiltered ? 'No matching tasks' : 'No tasks yet'"
      :description="
        isFiltered
          ? 'No background jobs match the filters you have applied.'
          : 'Background jobs - backups, deploys, migrations and more - appear here as they run.'
      "
    />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Button, Dropdown, ErrorMessage, TabButtons } from 'frappe-ui'
import EmptyState from '@/components/common/EmptyState.vue'
import ListRowSkeleton from '@/components/common/ListRowSkeleton.vue'
import StickyToolbar from '@/components/common/StickyToolbar.vue'
import { useIsMobile } from '@/composables/common/useIsMobile'
import { useTasks } from '@/composables/tasks/useTasks'
import {
  commandLabel,
  fmtDuration,
  relativeTime,
  siteLabel,
  statusConfig,
  TASK_TYPES,
  taskType,
} from '@/utils/taskFormat'
import { taskDetailRoute } from '@/utils/taskRoute'

const route = useRoute()
const router = useRouter()
const isMobile = useIsMobile()
const { tasks, loading, error, load } = useTasks()

const statusFilter = ref('all')

const filterOptions = [
  { label: 'All', value: 'all' },
  { label: 'Queued', value: 'queued' },
  { label: 'Running', value: 'running' },
  { label: 'Failed', value: 'failed' },
  { label: 'Succeeded', value: 'success' },
]

// Both filters live in the URL so filtered views are shareable.
const siteFilter = computed(() => (typeof route.query.site === 'string' ? route.query.site : ''))
const typeFilter = computed(() => (typeof route.query.type === 'string' ? route.query.type : ''))

const visibleTasks = computed(() =>
  tasks.value.filter(
    (task) =>
      (!siteFilter.value || siteLabel(task) === siteFilter.value) &&
      (!typeFilter.value || taskType(task) === typeFilter.value),
  ),
)

// "Other" is a fallback for unknown commands; listed only once one exists.
const typeMenu = computed(() => {
  const present = new Set(tasks.value.map(taskType))
  return [
    { label: 'All types', value: '' },
    ...TASK_TYPES.filter(
      ({ value }) => value !== 'other' || present.has('other') || typeFilter.value === 'other',
    ),
  ].map(({ value, label }) => ({ label, onClick: () => onTypeChange(value) }))
})

// Built from the loaded tasks; a site arriving via the URL is kept even
// when nothing matches, so the trigger still names what is filtering.
const siteMenu = computed(() => {
  const sites = new Set(tasks.value.map(siteLabel))
  if (siteFilter.value) sites.add(siteFilter.value)
  return [
    { label: 'All sites', value: '' },
    ...[...sites].sort().map((site) => ({ label: site, value: site })),
  ].map(({ value, label }) => ({ label, onClick: () => onSiteChange(value) }))
})

const typeLabel = computed(
  () => TASK_TYPES.find(({ value }) => value === typeFilter.value)?.label || 'All types',
)
const siteLabelText = computed(() => siteFilter.value || 'All sites')

// Patch, not replace: changing one filter must not clear the other.
function setFilterQuery(patch) {
  const query = { ...route.query, ...patch }
  for (const key of Object.keys(query)) if (!query[key]) delete query[key]
  router.replace({ name: 'Tasks', query })
}

const onSiteChange = (site) => setFilterQuery({ site })
const onTypeChange = (type) => setFilterQuery({ type })

// An empty list means something different when a filter is on - saying "no tasks
// yet" there would be a lie.
const isFiltered = computed(
  () => statusFilter.value !== 'all' || Boolean(siteFilter.value) || Boolean(typeFilter.value),
)

function onFilterChange(value) {
  statusFilter.value = value
  load(value)
}

onMounted(() => load(statusFilter.value))
</script>
