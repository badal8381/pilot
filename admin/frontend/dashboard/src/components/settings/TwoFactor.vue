<template>
  <div v-if="loading" class="flex justify-center items-center h-40">
    <span class="size-5 text-ink-gray-4 animate-spin lucide-loader-circle"></span>
  </div>
  <div v-else class="space-y-5">
    <Alert :title="status.enabled ? 'Two-factor is on' : 'Two-factor is off'" theme="blue" :dismissible="false">
      <template #description>
        <p class="text-ink-gray-6 text-p-sm">
          Requires a code from any enrolled device at every sign-in. Up to
          {{ status.max_devices }} devices can be enrolled. To set up more than one
          authenticator app for the same person, share that device's setup key instead of
          enrolling again.
        </p>
      </template>
    </Alert>

    <div class="flex justify-between items-center">
      <p class="font-medium text-ink-gray-8 text-sm">
        Devices
        <span class="font-normal text-ink-gray-5">
          ({{ status.credentials.length }} of {{ status.max_devices }})
        </span>
      </p>
      <Button
        v-if="!atDeviceLimit"
        variant="subtle"
        icon-left="lucide-plus"
        @click="openAdd"
        >Add device</Button
      >
    </div>

    <div
      v-if="atDeviceLimit"
      class="bg-surface-amber-1 p-3 border border-outline-amber-2 rounded-lg text-ink-amber-8 text-p-sm"
    >
      All {{ status.max_devices }} device slots are in use. Remove one to enrol another, or share
      an existing device's setup key to add another authenticator app.
    </div>

    <div
      v-if="!status.credentials.length"
      class="py-10 border border-dashed rounded-lg border-outline-gray-2 text-ink-gray-5 text-p-sm text-center"
    >
      No devices enrolled. Add one to turn on two-factor authentication.
    </div>
    <ListView
      v-else
      :columns="columns"
      :rows="status.credentials"
      row-key="id"
      :options="{ selectable: false, showTooltip: false }"
    >
      <template #cell="{ column, row, item }">
        <span v-if="column.key === 'label'" class="text-ink-gray-7 text-sm truncate">
          {{ row.label }}
        </span>
        <Badge
          v-else-if="column.key === 'status'"
          :theme="row.confirmed ? 'green' : 'orange'"
          variant="subtle"
          :label="row.confirmed ? 'Active' : 'Awaiting setup'"
        />
        <span v-else-if="column.key === 'last_used_at'" class="text-ink-gray-6 text-xs">
          {{ row.last_used_at ? fmtDateTime(new Date(row.last_used_at * 1000).toISOString()) : 'Never' }}
        </span>
        <div v-else-if="column.key === 'actions'" class="flex justify-end">
          <Button variant="ghost" size="sm" theme="red" icon="lucide-trash-2" @click="promptRemove(row)" />
        </div>
        <ListRowItem v-else :column="column" :row="row" :item="item" :align="column.align" />
      </template>
    </ListView>

    <div v-if="status.enabled" class="pt-2 border-t border-outline-gray-1">
      <SettingsRow
        label="Recovery codes"
        :description="`${status.recovery_codes_remaining} unused. Use one when no device is available.`"
      >
        <Button size="sm" variant="subtle" @click="showRegenerate = true">Regenerate</Button>
      </SettingsRow>
    </div>
  </div>

  <Dialog v-model="showAdd" :options="{ title: 'Add device', size: 'md' }">
    <template #body-content>
      <div v-if="!enrollment" class="space-y-3">
        <FormControl v-model="label" label="Device name" placeholder="My Phone" />
      </div>
      <div v-else class="space-y-3">
        <p class="text-ink-gray-6 text-p-sm">
          Scan this with an authenticator app, then enter the code it shows. Scan it with every
          app that should hold this device now — it is shown only once and cannot be retrieved
          afterwards.
        </p>
        <div class="flex justify-center bg-surface-white p-4 border border-outline-gray-2 rounded-lg">
          <QrcodeVue :value="enrollment.provisioning_url" :size="176" level="M" render-as="svg" />
        </div>
        <details class="text-ink-gray-6 text-p-sm">
          <summary class="cursor-pointer">Can't scan? Enter the key by hand</summary>
          <div class="bg-surface-gray-2 mt-2 p-3 rounded-lg">
            <p class="font-mono text-ink-gray-8 text-sm break-all">{{ enrollment.secret }}</p>
            <button class="mt-1 text-ink-blue-3 text-xs" @click="copy(enrollment.secret)">
              Copy key
            </button>
          </div>
        </details>
        <FormControl v-model="otp" label="Code from the app" placeholder="123456" />
      </div>
      <ErrorMessage v-if="error" :message="error" class="mt-2" />
      <div class="flex justify-end gap-2 mt-4">
        <Button variant="ghost" @click="showAdd = false">Cancel</Button>
        <Button v-if="!enrollment" variant="solid" :loading="busy" @click="startEnrollment">
          Continue
        </Button>
        <Button v-else variant="solid" :loading="busy" @click="confirmEnrollment">Verify</Button>
      </div>
    </template>
  </Dialog>

  <Dialog v-model="showCodes" :options="{ title: 'Save your recovery codes', size: 'md' }">
    <template #body-content>
      <p class="text-ink-gray-7 text-p-sm">
        These are shown once. Store them somewhere safe — each one signs you in when no device
        is available, and works only once.
      </p>
      <div class="gap-2 grid grid-cols-2 bg-surface-gray-2 mt-3 p-3 rounded-lg">
        <span v-for="code in codes" :key="code" class="font-mono text-ink-gray-8 text-xs">
          {{ code }}
        </span>
      </div>
      <div class="flex justify-end gap-2 mt-4">
        <Button variant="subtle" @click="copy(codes.join('\n'))">Copy all</Button>
        <Button variant="solid" @click="showCodes = false">Continue</Button>
      </div>
    </template>
  </Dialog>

  <Dialog v-model="showRemove" :options="{ title: 'Remove device', size: 'md' }">
    <template #body-content>
      <p class="text-ink-gray-7 text-p-sm">
        Remove <strong>{{ removing?.label }}</strong
        >? Its codes stop working. Removing the last device turns two-factor off.
      </p>
      <ErrorMessage v-if="error" :message="error" class="mt-2" />
      <div class="flex justify-end gap-2 mt-4">
        <Button variant="ghost" @click="showRemove = false">Cancel</Button>
        <Button variant="solid" theme="red" :loading="busy" @click="confirmRemove">Remove</Button>
      </div>
    </template>
  </Dialog>

  <Dialog v-model="showRegenerate" :options="{ title: 'Regenerate recovery codes', size: 'md' }">
    <template #body-content>
      <p class="text-ink-gray-7 text-p-sm">
        This replaces all existing codes, including unused ones. Anything you saved earlier stops
        working.
      </p>
      <ErrorMessage v-if="error" :message="error" class="mt-2" />
      <div class="flex justify-end gap-2 mt-4">
        <Button variant="ghost" @click="showRegenerate = false">Cancel</Button>
        <Button variant="solid" :loading="busy" @click="regenerate">Regenerate</Button>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { Alert, Badge, Button, Dialog, ErrorMessage, FormControl, ListView, ListRowItem, toast } from 'frappe-ui'
import QrcodeVue from 'qrcode.vue'
import SettingsRow from '@/components/settings/SettingsRow.vue'
import { twoFactorApi } from '@/api/twoFactor'
import { fmtDateTime } from '@/utils/taskFormat'

const columns = [
  { label: 'Device', key: 'label', align: 'left' },
  { label: 'Status', key: 'status', align: 'left', width: '9rem' },
  { label: 'Last used', key: 'last_used_at', align: 'left', width: '11rem' },
  { label: '', key: 'actions', align: 'right', width: '3.5rem' },
]

const loading = ref(true)
const busy = ref(false)
const error = ref('')
const status = ref({
  enabled: false,
  credentials: [],
  recovery_codes_remaining: 0,
  max_devices: 0,
})

const atDeviceLimit = computed(
  () => status.value.max_devices > 0 && status.value.credentials.length >= status.value.max_devices,
)

const showAdd = ref(false)
const showCodes = ref(false)
const showRemove = ref(false)
const showRegenerate = ref(false)

const label = ref('')
const otp = ref('')
const enrollment = ref(null)
const codes = ref([])
const removing = ref(null)

function openAdd() {
  label.value = ''
  otp.value = ''
  enrollment.value = null
  error.value = ''
  showAdd.value = true
}

async function startEnrollment() {
  error.value = ''
  busy.value = true
  try {
    enrollment.value = await twoFactorApi.startEnrollment(label.value)
  } catch (e) {
    error.value = e.message || 'Could not start enrollment.'
  } finally {
    busy.value = false
  }
}

async function confirmEnrollment() {
  error.value = ''
  busy.value = true
  try {
    const result = await twoFactorApi.confirm(enrollment.value.id, otp.value)
    status.value = result
    showAdd.value = false
    if (result.recovery_codes) {
      codes.value = result.recovery_codes
      showCodes.value = true
    }
    toast.success('Device added')
  } catch (e) {
    error.value = e.message || 'Could not verify that code.'
  } finally {
    busy.value = false
  }
}

function promptRemove(row) {
  removing.value = row
  error.value = ''
  showRemove.value = true
}

async function confirmRemove() {
  error.value = ''
  busy.value = true
  try {
    status.value = await twoFactorApi.removeDevice(removing.value.id)
    showRemove.value = false
    toast.success('Device removed')
  } catch (e) {
    error.value = e.message || 'Could not remove that device.'
  } finally {
    busy.value = false
  }
}

async function regenerate() {
  error.value = ''
  busy.value = true
  try {
    const result = await twoFactorApi.regenerateRecoveryCodes()
    codes.value = result.recovery_codes
    showRegenerate.value = false
    showCodes.value = true
    await load()
  } catch (e) {
    error.value = e.message || 'Could not regenerate recovery codes.'
  } finally {
    busy.value = false
  }
}

async function copy(text) {
  try {
    await navigator.clipboard.writeText(text)
    toast.success('Copied')
  } catch {
    toast.error('Could not copy')
  }
}

async function load() {
  try {
    status.value = await twoFactorApi.status()
  } catch (e) {
    toast.error(e.message || 'Could not load two-factor settings.')
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
