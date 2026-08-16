<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Badge, Button, ErrorMessage, LoadingText } from 'frappe-ui'

import TaskDebugDialog from '@/components/tasks/TaskDebugDialog.vue'
import TaskSteps from '@/components/tasks/TaskSteps.vue'
import TaskStream from '@/components/tasks/TaskStream.vue'

import { apiErrorMessage } from '@/api/client'
import { tasksApi } from '@/api/tasks'
import { settingsApi } from '@/api/settings'
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
  statusConfig,
  taskScope,
} from '@/utils/taskFormat'

const route = useRoute()
const router = useRouter()
const taskId = route.params.taskId

const isMobile = useIsMobile()
const { setBreadcrumbs } = useBreadcrumbs()
const { task, rawLines, loading, error, load } = useTaskDetail(taskId)

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

const loadAiStatus = async () => {
  try {
    const data = await settingsApi.get()
    aiConnected.value = Boolean(data.llm?.provider && data.llm?.api_key_set)
  } catch {
    aiConnected.value = false
  }
}

const scope = computed(() => taskScope(task.value))

const metaLine = computed(() => {
  const parts = []
  if (task.value.status === 'queued' && task.value.queue_position)
    parts.push(`#${task.value.queue_position} in queue`)
  if (task.value.started_at) parts.push(`Started ${fmtDateTime(task.value.started_at)}`)
  const duration = fmtDuration(task.value.duration_seconds)
  if (duration) parts.push(`took ${duration}`)
  return parts.join(' · ')
})

const updateStatus = (event) => {
  if (!['queued', 'running'].includes(event.status)) return
  task.value.status = event.status
  task.value.queue_position = event.queue_position
  task.value.is_cancellable = event.is_cancellable
}

const handleDone = (success) => {
  load()
  if (!success) return
  const redirect = redirectRouteOnSuccess(task.value)
  if (redirect) router.push(redirect)
}

const cancelTask = async () => {
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

<template>
  <div v-if="loading" class="flex justify-center py-12">
    <LoadingText />
  </div>
  <div v-else-if="error" class="py-12">
    <ErrorMessage :message="error" />
  </div>
  <div v-else-if="task" class="mx-auto max-w-3xl">
    <Teleport defer to="#header-badge">
      <Badge
        :label="statusConfig(task).label"
        :theme="statusConfig(task).theme"
        variant="subtle"
        size="md"
      />
    </Teleport>

    <!-- In place on mobile; the header row has no room for these there. -->
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

    <div class="flex justify-between items-center gap-4 mt-5 px-2 min-w-0">
      <RouterLink
        :to="scope.route"
        class="group flex items-center gap-1 min-w-0 font-medium text-ink-gray-9 text-lg no-underline"
      >
        <span class="truncate">{{ scope.label }}</span>
        <span
          class="opacity-0 group-hover:opacity-100 size-4 text-ink-gray-5 transition-opacity shrink-0 lucide-arrow-up-right"
        />
      </RouterLink>
      <p class="text-ink-gray-8 text-base shrink-0">{{ metaLine }}</p>
    </div>

    <ErrorMessage v-if="actionError" :message="actionError" class="mt-3" />

    <!-- Steps -->
    <div class="mt-3">
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
