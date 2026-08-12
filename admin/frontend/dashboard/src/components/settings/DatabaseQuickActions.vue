<template>
  <Teleport defer to="#settings-header-actions">
    <Tooltip text="Refresh database capabilities">
      <Button
        variant="ghost"
        icon="lucide-refresh-cw"
        :loading="loading"
        aria-label="Refresh database capabilities"
        @click="load"
      />
    </Tooltip>
  </Teleport>

  <div v-if="loading && !capabilities" class="flex justify-center items-center h-40">
    <span class="size-5 text-ink-gray-4 animate-spin lucide-loader-circle"></span>
  </div>
  <div v-else>
    <ErrorMessage v-if="error" :message="error" class="mb-4" />

    <div v-if="capabilities" class="pb-4">
      <Badge :label="engineLabel" theme="gray" size="sm" />
    </div>

    <div
      v-if="showManagedMariaDBDisclaimer"
      class="mb-4 border border-outline-gray-2 bg-surface-gray-1 px-3 py-2 text-ink-gray-7 text-sm"
    >
      Database actions are available only for Pilot-managed MariaDB instances.
    </div>

    <div v-if="capabilities" class="divide-y divide-outline-alpha-gray-1">
      <SettingsRow
        label="Performance Schema"
        description="Collect database instrumentation for deeper performance diagnostics."
      >
        <Switch
          :model-value="Boolean(action('performance_schema').enabled)"
          :disabled="!action('performance_schema').available || Boolean(activeAction)"
          aria-label="Performance Schema"
          @update:model-value="confirmPerformanceSchema"
        />
      </SettingsRow>

      <SettingsRow
        label="Update InnoDB Buffer Pool Size"
        :description="bufferPoolDescription"
      >
        <Button
          size="sm"
          variant="subtle"
          :disabled="!action('innodb_buffer_pool_size').available || Boolean(activeAction)"
          @click="openSizingAction('innodb_buffer_pool_size')"
        >
          Update
        </Button>
      </SettingsRow>

      <SettingsRow
        label="Update Max DB Connections"
        :description="maxConnectionsDescription"
      >
        <Button
          size="sm"
          variant="subtle"
          :disabled="!action('max_connections').available || Boolean(activeAction)"
          @click="openSizingAction('max_connections')"
        >
          Update
        </Button>
      </SettingsRow>

      <SettingsRow
        label="Manage Binlogs"
        description="Inspect binary logs and safely purge complete log ranges."
      >
        <Button
          size="sm"
          variant="subtle"
          :disabled="!action('manage_binlogs').available"
          @click="openBinlogs"
        >
          View
        </Button>
      </SettingsRow>

      <SettingsRow
        label="Restart MariaDB"
        description="Restart the database service and verify that it accepts connections."
      >
        <Button
          size="sm"
          variant="subtle"
          :disabled="!action('restart').available || Boolean(activeAction)"
          :loading="activeAction === 'restart'"
          @click="confirmRestart"
        >
          Restart
        </Button>
      </SettingsRow>
    </div>
  </div>

  <Dialog v-model="confirmationOpen" :title="confirmationTitle" size="sm">
    <p v-if="confirmation?.message" class="text-ink-gray-7 text-sm">
      {{ confirmation.message }}
    </p>
    <ErrorMessage v-if="actionError" :message="actionError" class="mt-3" />
    <div class="flex justify-end gap-2 mt-4">
      <Button variant="ghost" :disabled="Boolean(activeAction)" @click="confirmationOpen = false">
        Cancel
      </Button>
      <Button variant="solid" :loading="Boolean(activeAction)" @click="runConfirmedAction">
        {{ confirmation?.buttonLabel }}
      </Button>
    </div>
  </Dialog>

  <Dialog v-model="sizingOpen" :title="sizingTitle" size="sm">
    <div v-if="sizingAction" class="space-y-4">
      <FormControl
        v-model.number="sizingValue"
        type="number"
        :label="sizingAction.inputLabel"
        :min="sizingAction.min"
        :max="sizingAction.max"
        step="1"
        autocomplete="off"
      />
      <div class="text-ink-gray-6 text-sm">
        <p>
          Recommended:
          {{ formatSizingValue(sizingAction.recommended, sizingAction.unit) }}
        </p>
        <p>
          Allowed: {{ formatSizingValue(sizingAction.min, sizingAction.unit) }} to
          {{ formatSizingValue(sizingAction.max, sizingAction.unit) }}
        </p>
      </div>
      <p v-if="sizingRequiresRestart" class="text-ink-orange-6 text-sm">
        MariaDB will restart because this value is above its current live Buffer Pool ceiling of
        {{ formatSizingValue(sizingAction.dynamicMax, 'MB') }}.
      </p>
      <ErrorMessage v-if="sizingValidationError" :message="sizingValidationError" />
      <ErrorMessage v-if="actionError" :message="actionError" />
      <div class="flex justify-end gap-2">
        <Button variant="ghost" :disabled="Boolean(activeAction)" @click="sizingOpen = false">
          Cancel
        </Button>
        <Button
          variant="solid"
          :loading="Boolean(activeAction)"
          :disabled="Boolean(sizingValidationError) || sizingUnchanged"
          @click="runSizingAction"
        >
          {{ sizingRequiresRestart ? 'Update and restart' : 'Update' }}
        </Button>
      </div>
    </div>
  </Dialog>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Badge, Button, Dialog, ErrorMessage, FormControl, Switch, Tooltip } from 'frappe-ui'
import { databaseApi } from '@/api/database'
import SettingsRow from '@/components/settings/SettingsRow.vue'
import { openTaskDetailPage } from '@/utils/taskRoute'

const router = useRouter()

const loading = ref(false)
const capabilities = ref(null)
const error = ref('')
const actionError = ref('')
const activeAction = ref('')
const confirmation = ref(null)
const sizingAction = ref(null)
const sizingValue = ref('')

const confirmationOpen = computed({
  get: () => Boolean(confirmation.value),
  set: (value) => {
    if (!value && !activeAction.value) confirmation.value = null
  },
})
const confirmationTitle = computed(() => confirmation.value?.title || 'Database action')
const sizingOpen = computed({
  get: () => Boolean(sizingAction.value),
  set: (value) => {
    if (!value && !activeAction.value) sizingAction.value = null
  },
})
const sizingTitle = computed(() => sizingAction.value?.title || 'Update database setting')
const sizingValidationError = computed(() => {
  if (!sizingAction.value) return ''
  if (!Number.isInteger(sizingValue.value)) return 'Enter a whole number.'
  if (sizingValue.value < sizingAction.value.min || sizingValue.value > sizingAction.value.max) {
    return `Enter a value between ${sizingAction.value.min} and ${sizingAction.value.max}.`
  }
  return ''
})
const sizingRequiresRestart = computed(
  () =>
    sizingAction.value?.action === 'innodb_buffer_pool_size' &&
    Number.isFinite(sizingAction.value.dynamicMax) &&
    sizingValue.value > sizingAction.value.dynamicMax,
)
const sizingUnchanged = computed(
  () => sizingAction.value !== null && sizingValue.value === sizingAction.value.current,
)
const showManagedMariaDBDisclaimer = computed(
  () =>
    capabilities.value !== null &&
    (capabilities.value.engine !== 'mariadb' || !capabilities.value.managed),
)
const engineLabel = computed(() => {
  const labels = { mariadb: 'MariaDB', postgres: 'PostgreSQL', sqlite: 'SQLite' }
  return labels[capabilities.value?.engine] || 'Database'
})
const bufferPoolDescription = computed(() => {
  const capability = action('innodb_buffer_pool_size')
  const description = ''
  if (!capability.available) return description
  return `${description} Current: ${formatSizingValue(capability.current_mb, 'MB')}`
})
const maxConnectionsDescription = computed(() => {
  const current = action('max_connections').current
  return `Current: ${Number.isInteger(current) ? current : 'unavailable'}`
})

function action(name) {
  return capabilities.value?.actions?.[name] || {
    available: false,
    reason: 'Database capabilities are unavailable.',
  }
}

function formatSizingValue(value, unit = '') {
  return `${value}${unit ? ` ${unit}` : ''}`
}

function idempotencyKey(actionName) {
  const random = globalThis.crypto?.randomUUID?.() || Math.random().toString(36).slice(2)
  return `database-${actionName}-${Date.now()}-${random}`
}

function confirmRestart() {
  actionError.value = ''
  confirmation.value = {
    action: 'restart',
    title: 'Restart MariaDB',
    buttonLabel: 'Restart MariaDB',
    message:
      'Sites, web requests, workers, and scheduled jobs may briefly lose their database connection.',
    idempotencyKey: idempotencyKey('restart'),
  }
}

function confirmPerformanceSchema(enabled) {
  if (action('performance_schema').enabled === enabled) return
  actionError.value = ''
  confirmation.value = {
    action: 'performance_schema',
    enabled,
    title: `${enabled ? 'Enable' : 'Disable'} Performance Schema`,
    buttonLabel: `${enabled ? 'Enable' : 'Disable'} and restart`,
    message: `Pilot will ${enabled ? 'enable' : 'disable'} Performance Schema and restart MariaDB. Sites, web requests, workers, and scheduled jobs may briefly lose their database connection.`,
    idempotencyKey: idempotencyKey(`performance-${enabled ? 'on' : 'off'}`),
  }
}

function openSizingAction(actionName) {
  actionError.value = ''
  const capability = action(actionName)
  if (!capability.available) return
  if (actionName === 'innodb_buffer_pool_size') {
    sizingValue.value = capability.current_mb
    sizingAction.value = {
      action: actionName,
      title: 'Update InnoDB Buffer Pool Size',
      inputLabel: 'Buffer Pool size (MB)',
      current: capability.current_mb,
      recommended: capability.recommended_mb,
      min: capability.min_mb,
      max: capability.max_mb,
      dynamicMax: capability.dynamic_max_mb,
      unit: 'MB',
      idempotencyKey: idempotencyKey('innodb-buffer-pool-size'),
    }
    return
  }
  sizingValue.value = capability.current
  sizingAction.value = {
    action: actionName,
    title: 'Update Max DB Connections',
    inputLabel: 'Maximum connections',
    current: capability.current,
    recommended: capability.recommended,
    min: capability.min,
    max: capability.max,
    dynamicMax: null,
    unit: '',
    idempotencyKey: idempotencyKey('max-connections'),
  }
}

async function runConfirmedAction() {
  if (!confirmation.value || activeAction.value) return
  const pending = confirmation.value
  activeAction.value = pending.action
  actionError.value = ''
  try {
    const task =
      pending.action === 'restart'
        ? await databaseApi.quickActions.restart(pending.idempotencyKey)
        : await databaseApi.quickActions.setPerformanceSchema(
            pending.enabled,
            pending.idempotencyKey,
          )
    confirmation.value = null
    openTaskDetailPage(router, task.task_id)
  } catch (e) {
    actionError.value = e.message || 'Could not start the database action.'
  } finally {
    activeAction.value = ''
  }
}

async function runSizingAction() {
  if (
    !sizingAction.value ||
    sizingValidationError.value ||
    sizingUnchanged.value ||
    activeAction.value
  )
    return
  const pending = sizingAction.value
  activeAction.value = pending.action
  actionError.value = ''
  try {
    const task =
      pending.action === 'innodb_buffer_pool_size'
        ? await databaseApi.quickActions.setInnoDBBufferPoolSize(
            sizingValue.value,
            pending.idempotencyKey,
          )
        : await databaseApi.quickActions.setMaxConnections(
            sizingValue.value,
            pending.idempotencyKey,
          )
    sizingAction.value = null
    openTaskDetailPage(router, task.task_id)
  } catch (e) {
    actionError.value = e.message || 'Could not start the database action.'
  } finally {
    activeAction.value = ''
  }
}

function openBinlogs() {
  router.push('/database/analyzer')
}

async function load() {
  if (loading.value) return
  loading.value = true
  error.value = ''
  try {
    capabilities.value = await databaseApi.quickActions.capabilities()
  } catch (e) {
    capabilities.value = null
    error.value = e.message || 'Could not load database capabilities.'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
