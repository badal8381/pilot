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
      <TabButtons v-model="activeTab" :options="tabs" />

      <Alert :title="info.title" theme="blue" :dismissible="false">
        <template #description>
          <p class="text-ink-gray-6 text-p-sm">{{ info.description }}</p>
        </template>
      </Alert>

      <div
        v-if="!currentRows.length"
        class="flex flex-col items-center gap-2.5 py-10 border border-dashed rounded-lg border-outline-gray-2 text-center"
      >
        <div class="flex justify-center items-center bg-surface-gray-2 rounded-full size-11">
          <span :class="info.emptyIcon" class="size-5 text-ink-gray-5"></span>
        </div>
        <p class="font-medium text-ink-gray-7 text-sm">{{ info.emptyTitle }}</p>
        <p class="max-w-xs text-ink-gray-5 text-xs">{{ info.emptyHint }}</p>
      </div>

      <ListView
        v-else
        :columns="columns"
        :rows="currentRows"
        row-key="jti"
        :options="{ selectable: false, showTooltip: false }"
      >
        <template #cell="{ column, row, item }">
          <div v-if="column.key === 'jti'" class="flex items-center gap-2 w-full min-w-0">
            <button
              class="min-w-0 font-mono text-ink-gray-6 text-xs text-left truncate"
              title="Click to copy"
              @click="copy(row.jti)"
            >
              {{ row.jti }}
            </button>
            <Badge
              v-if="row.jti === currentJti"
              class="shrink-0"
              theme="green"
              variant="subtle"
              label="This session"
            />
          </div>
          <span v-else-if="column.key === 'exp'" class="text-ink-gray-6 text-xs">
            {{ row.expires }}
          </span>
          <div v-else-if="column.key === 'actions'" class="flex justify-end">
            <Button
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
      <p class="mt-2 font-mono text-ink-gray-5 text-xs break-all">{{ revoking?.jti }}</p>
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
import { Alert, Badge, Button, Dialog, ListView, ListRowItem, TabButtons, toast } from 'frappe-ui'
import { sessionApi } from '@/api/session'
import { fmtDateTime } from '@/utils/taskFormat'

const INFO = {
  active: {
    title: 'Active sessions',
    description:
      'Each row is a sign-in that is currently valid — a browser logged into this ' +
      'bench. The token ID (jti) uniquely identifies that session, and it stops working on its ' +
      'own once it expires. Revoke one to sign it out immediately.',
    emptyIcon: 'lucide-key-round',
    emptyTitle: 'No active sessions',
    emptyHint: 'Sign-ins appear here while their tokens are valid.',
  },
  revoked: {
    title: 'Revoked sessions',
    description:
      'Sessions that were signed out before they expired. A revoked token is rejected on ' +
      'every request until its original expiry, then it drops off this list automatically.',
    emptyIcon: 'lucide-shield-off',
    emptyTitle: 'No revoked sessions',
    emptyHint: 'Tokens you revoke early are listed here until they expire.',
  },
}

const loading = ref(true)
const loadError = ref('')
const activeTokens = ref([])
const revokedTokens = ref([])
const currentJti = ref('')
const activeTab = ref('active')
const showRevoke = ref(false)
const revoking = ref(null)
const revokeBusy = ref(false)

const tabs = computed(() => [
  { label: `Active (${activeTokens.value.length})`, value: 'active' },
  { label: `Revoked (${revokedTokens.value.length})`, value: 'revoked' },
])

const info = computed(() => INFO[activeTab.value])

const columns = computed(() => {
  const base = [
    { label: 'Token ID (jti)', key: 'jti', align: 'left', width: '13rem' },
    { label: 'Expires', key: 'exp', align: 'left', width: '11rem' },
  ]
  if (activeTab.value === 'active') {
    base.push({ label: '', key: 'actions', align: 'right', width: '3.5rem' })
  }
  return base
})

const currentRows = computed(() =>
  (activeTab.value === 'active' ? activeTokens.value : revokedTokens.value).map((t) => ({
    jti: t.jti,
    exp: t.exp,
    expires: formatExpiry(t.exp),
  })),
)

function formatExpiry(exp) {
  if (!exp) return '-'
  return fmtDateTime(new Date(exp * 1000).toISOString())
}

async function copy(jti) {
  try {
    await navigator.clipboard.writeText(jti)
    toast.success('Token ID copied')
  } catch {
    toast.error('Could not copy')
  }
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
    revokedTokens.value = data.revoked_tokens || []
    currentJti.value = data.current_jti || ''
  } catch (e) {
    loadError.value = e.message || 'Could not load authentication data.'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
