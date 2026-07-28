<template>
  <div v-if="loading" class="flex justify-center items-center h-40">
    <span class="size-5 text-ink-gray-4 animate-spin lucide-loader-circle"></span>
  </div>
  <div v-else class="space-y-5">
    <div
      v-if="loadError"
      class="py-12 border border-dashed rounded-xl border-outline-red-2 text-ink-red-3 text-p-sm text-center"
    >
      {{ loadError }}
    </div>
    <template v-else>
      <div
        v-if="!activeTokens.length"
        class="flex flex-col items-center gap-2.5 py-10 border border-dashed rounded-lg border-outline-gray-2 text-center"
      >
        <div class="flex justify-center items-center bg-surface-gray-2 rounded-full size-11">
          <span class="size-5 text-ink-gray-5 lucide-key-round"></span>
        </div>
        <p class="font-medium text-ink-gray-7 text-sm">No active sessions</p>
        <p class="max-w-xs text-ink-gray-5 text-xs">Sign-ins appear here while their tokens are valid.</p>
      </div>

      <ListView
        v-else
        :columns="columns"
        :rows="rows"
        row-key="jti"
        :options="{ selectable: false, showTooltip: false }"
      >
        <template #cell="{ column, row, item }">
          <span v-if="column.key === 'ip'" class="font-mono text-ink-gray-6 text-xs">{{ row.ip }}</span>
          <span
            v-else-if="column.key === 'activity'"
            class="text-ink-gray-6 text-xs"
            :title="row.jti === currentJti ? '' : row.lastActivityExact"
          >
            {{ row.jti === currentJti ? 'Current session' : row.lastActivity }}
          </span>
          <span v-else-if="column.key === 'exp'" class="text-ink-gray-6 text-xs">{{ row.expires }}</span>
          <div v-else-if="column.key === 'actions'" class="flex justify-end">
            <Button
              v-if="row.jti !== currentJti"
              variant="ghost"
              size="sm"
              theme="red"
              icon="lucide-log-out"
              title="Revoke session"
              @click="promptRevoke(row)"
            />
          </div>
          <ListRowItem v-else :column="column" :row="row" :item="item" :align="column.align" />
        </template>
      </ListView>
    </template>
  </div>

  <Dialog v-model="showRevoke" :options="{ title: 'Revoke session', size: 'md' }">
    <template #body-content>
      <p class="text-ink-gray-7 text-p-sm">
        Revoke this session? Its token stops working immediately and whoever holds it must sign in
        again.
      </p>
      <p class="mt-2 font-mono text-ink-gray-5 text-xs">{{ revoking?.ip }}</p>
      <div class="flex justify-end gap-2 mt-4">
        <Button variant="ghost" @click="showRevoke = false">Cancel</Button>
        <Button variant="solid" theme="red" :loading="revokeBusy" @click="confirmRevoke">
          Revoke
        </Button>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { Button, Dialog, ListView, ListRowItem, toast } from 'frappe-ui'
import { sessionApi } from '@/api/session'
import { fmtDateTime, relativeTime } from '@/utils/taskFormat'

const loading = ref(true)
const loadError = ref('')
const activeTokens = ref([])
const currentJti = ref('')
const showRevoke = ref(false)
const revoking = ref(null)
const revokeBusy = ref(false)

const columns = [
  { label: 'IP address', key: 'ip', align: 'left', width: '10rem' },
  { label: 'Last activity', key: 'activity', align: 'left', width: '11rem' },
  { label: 'Expires', key: 'exp', align: 'left', width: '11rem' },
  { label: '', key: 'actions', align: 'right', width: '3.5rem' },
]

const rows = computed(() =>
  activeTokens.value.map((t) => ({
    jti: t.jti,
    ip: t.ip || '-',
    exp: t.exp,
    expires: formatDate(t.exp),
    lastActivity: t.last_seen ? relativeTime(new Date(t.last_seen * 1000).toISOString()) : '-',
    lastActivityExact: formatDate(t.last_seen),
  })),
)

function formatDate(seconds) {
  return seconds ? fmtDateTime(new Date(seconds * 1000).toISOString()) : '-'
}

function promptRevoke(row) {
  revoking.value = row
  showRevoke.value = true
}

async function confirmRevoke() {
  revokeBusy.value = true
  try {
    const response = await sessionApi.revoke(revoking.value.jti)
    if (response.ok) {
      toast.success('Session revoked')
      showRevoke.value = false
      await load()
    } else {
      toast.error('Could not revoke session')
    }
  } catch (e) {
    toast.error(e.message || 'Could not revoke session')
  } finally {
    revokeBusy.value = false
  }
}

async function load() {
  try {
    const data = await sessionApi.list()
    activeTokens.value = data.active_tokens || []
    currentJti.value = data.current_jti || ''
  } catch (e) {
    loadError.value = e.message || 'Could not load authentication data.'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
