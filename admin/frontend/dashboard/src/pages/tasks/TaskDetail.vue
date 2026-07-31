<template>
  <div v-if="loading" class="flex justify-center py-12">
    <LoadingText />
  </div>
  <div v-else-if="error" class="py-12">
    <ErrorMessage :message="error" />
  </div>
  <div v-else-if="task" class="mx-auto max-w-3xl">
    <!-- The breadcrumb carries the task's name and links back to the list, so
         the page needs neither a duplicate heading nor a back arrow - both of
         which were pushing the content off the column's left edge. -->
    <Teleport defer to="#header-badge">
      <Badge
        :label="statusConfig(task).label"
        :theme="statusConfig(task).theme"
        variant="subtle"
        size="md"
      />
    </Teleport>

    <!-- Rendered in place on mobile: that header is already carrying the
         breadcrumb, the badge and the update button, and Debug/Cancel would
         push it past the edge. -->
    <Teleport defer to="#header-actions" :disabled="isMobile">
      <div class="flex items-center gap-2" :class="isMobile ? 'mb-4' : ''">
        <Button
          variant="subtle"
          size="sm"
          :loading="loading"
          icon="lucide-refresh-cw"
          label="Refresh"
          tooltip="Refresh"
          @click="load"
        />
        <Button
          v-if="task.status === 'failed' && aiConnected"
          variant="subtle"
          size="sm"
          icon-left="lucide-sparkles"
          @click="showDebug = true"
        >
          Debug with AI
        </Button>
        <Button
          v-if="isTaskCancellable(task)"
          variant="subtle"
          size="sm"
          theme="red"
          icon-left="lucide-x"
          @click="cancelTask"
        >
          Cancel
        </Button>
      </div>
    </Teleport>

    <TaskDebugDialog v-model="showDebug" :task-id="taskId" />

    <!-- Metadata: no card. The elevation token is the same colour as the page,
         so all the box did was inset these labels out of line with the steps. -->
    <div
      class="gap-4 grid grid-cols-2"
      :class="metadata.length > 3 ? 'sm:grid-cols-4' : 'sm:grid-cols-3'"
    >
      <div v-for="item in metadata" :key="item.label" class="min-w-0">
        <p class="text-ink-gray-5 text-sm">{{ item.label }}</p>
        <!-- An arrow on hover, not an underline: the arrow says where the link
             goes, and it appears in reserved space so nothing reflows. -->
        <RouterLink
          v-if="item.route"
          :to="item.route"
          class="group flex items-center gap-1 mt-1 min-w-0 text-ink-gray-8 text-base no-underline"
        >
          <span class="truncate">{{ item.value }}</span>
          <span
            class="opacity-0 group-hover:opacity-100 size-3.5 text-ink-gray-5 transition-opacity shrink-0 lucide-arrow-up-right"
          />
        </RouterLink>
        <p v-else class="mt-1 text-ink-gray-8 text-base truncate">{{ item.value }}</p>
      </div>
    </div>

    <!-- Inside the column, beside the action that raises it: a cancel failure
         rendered full-width was out of line exactly when it mattered most. -->
    <ErrorMessage v-if="actionError" :message="actionError" class="mt-3" />

    <!-- Steps -->
    <div class="mt-4">
      <TaskStream
        v-if="isTaskActive(task)"
        :url="tasksApi.streamUrl(taskId)"
        :empty-text="task.status === 'queued' ? 'Waiting for this task to start…' : 'No output yet…'"
        v-slot="{ rawLines: streamedLines, streaming }"
        @status="updateStatus"
        @done="handleDone"
      >
        <TaskSteps :raw-lines="streamedLines" :streaming="streaming" :task-status="task.status" />
      </TaskStream>
      <TaskSteps v-else :raw-lines="rawLines" :task-status="task.status" />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Badge, Button, ErrorMessage, LoadingText } from 'frappe-ui'
import { apiErrorMessage } from '@/api/client'
import { tasksApi } from '@/api/tasks'
import { settingsApi } from '@/api/settings'
import TaskDebugDialog from '@/components/tasks/TaskDebugDialog.vue'
import { useBreadcrumbs } from '@/composables/common/useBreadcrumbs'
import { useIsMobile } from '@/composables/common/useIsMobile'
import { useTaskDetail } from '@/composables/tasks/useTaskDetail'
import {
  commandLabel,
  fmtDateTime,
  fmtDuration,
  isTaskActive,
  isTaskCancellable,
  redirectRouteOnSuccess,
  siteLabel,
  siteRoute,
  statusConfig,
} from '@/utils/taskFormat'

const route = useRoute()
const router = useRouter()
const taskId = route.params.taskId

const isMobile = useIsMobile()
const { setBreadcrumbs } = useBreadcrumbs()
const { task, rawLines, loading, error, load } = useTaskDetail(taskId)

// "Task" told you nothing you did not already know. The trail carries the list
// and the task's own name, which is why the page can drop its heading.
setBreadcrumbs([{ label: 'Tasks', route: { name: 'Tasks' } }])
watch(
  () => task.value?.command,
  (command) => {
    if (!command) return
    setBreadcrumbs([
      { label: 'Tasks', route: { name: 'Tasks' } },
      { label: commandLabel(command) },
    ])
  },
)

const actionError = ref('')
const showDebug = ref(false)
const aiConnected = ref(false)

async function loadAiStatus() {
  try {
    const data = await settingsApi.get()
    aiConnected.value = Boolean(data.llm?.provider && data.llm?.api_key_set)
  } catch {
    aiConnected.value = false
  }
}

const metadata = computed(() => {
  const items = [
    { label: 'Started', value: fmtDateTime(task.value.started_at) },
    {
      label: 'Finished',
      value: task.value.finished_at ? fmtDateTime(task.value.finished_at) : '-',
    },
    { label: 'Duration', value: fmtDuration(task.value.duration_seconds) || '-' },
  ]
  if (task.value.status === 'queued' && task.value.queue_position) {
    items.unshift({ label: 'Queue position', value: `#${task.value.queue_position}` })
  }
  const site = siteLabel(task.value)
  if (site !== 'Server-level') {
    items.unshift({ label: 'Site', value: site, route: siteRoute(task.value) })
  }
  return items
})

function updateStatus(event) {
  if (!['queued', 'running'].includes(event.status)) return
  task.value.status = event.status
  task.value.queue_position = event.queue_position
  task.value.is_cancellable = event.is_cancellable
}

function handleDone(success) {
  load()
  if (!success) return
  const redirect = redirectRouteOnSuccess(task.value)
  if (redirect) router.push(redirect)
}

async function cancelTask() {
  actionError.value = ''
  try {
    const response = await tasksApi.cancel(taskId)
    if (!response.ok) {
      const result = await response.json()
      actionError.value = apiErrorMessage(result, 'Failed to cancel task')
      return
    }
    load()
  } catch (caught) {
    actionError.value = caught.message || 'Failed to cancel task'
  }
}

onMounted(() => {
  load()
  loadAiStatus()
})
</script>
