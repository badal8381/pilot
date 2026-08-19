<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { Button, ErrorMessage, Spinner, TextInput, toast } from 'frappe-ui'

import EmptyState from '@/components/common/EmptyState.vue'
import SettingsSwitch from '@/components/settings/SettingsSwitch.vue'

import { apiErrorMessage } from '@/api/client'
import { settingsApi } from '@/api/settings'

// Every resource alert starts off; site uptime is the only one on by default.
const RESOURCE_ALERTS = [
  {
    key: 'cpu_usage_limit',
    label: 'CPU usage',
    description: 'Alert when processor use on this host crosses the limit.',
    initial: 85,
  },
  {
    key: 'memory_usage_limit',
    label: 'Memory usage',
    description: 'Alert when memory use on this host crosses the limit.',
    initial: 90,
  },
  {
    key: 'disk_space_limit',
    label: 'Disk usage',
    description: 'Alert when disk use on this host crosses the limit.',
    initial: 90,
  },
]

const loading = ref(true)
const saving = ref(false)
const error = ref('')
// The switch owns whether an alert is on, so clearing the field keeps it mounted.
const enabled = ref(Object.fromEntries(RESOURCE_ALERTS.map((alert) => [alert.key, false])))
const limits = ref(Object.fromEntries(RESOURCE_ALERTS.map((alert) => [alert.key, ''])))
const siteUptime = ref(true)
const webhooks = ref([])
const mail = ref({
  smtp_url: '',
  smtp_password: '',
  smtp_password_set: false,
  email_recipients: '',
})

const savedPayload = ref('')
const dirty = computed(() => JSON.stringify(buildPayload()) !== savedPayload.value)

const buildPayload = () => {
  return {
    ...Object.fromEntries(
      RESOURCE_ALERTS.map((alert) => [
        alert.key,
        enabled.value[alert.key] ? Number(limits.value[alert.key]) || 0 : 0,
      ]),
    ),
    site_uptime: siteUptime.value,
    // Blank token means "keep the stored one"; original_url is how it is found.
    webhook_endpoints: webhooks.value.map((webhook) => ({
      url: webhook.url.trim(),
      token: webhook.token,
      original_url: webhook.original_url,
    })),
    smtp_url: mail.value.smtp_url.trim(),
    smtp_password: mail.value.smtp_password,
    email_recipients: recipients(),
  }
}

const recipients = () =>
  mail.value.email_recipients
    .split(',')
    .map((address) => address.trim())
    .filter(Boolean)

const setEnabled = (key, on) => {
  enabled.value[key] = on
  if (on && !Number(limits.value[key])) {
    limits.value[key] = String(RESOURCE_ALERTS.find((alert) => alert.key === key).initial)
  }
}

const addWebhook = () => {
  webhooks.value.push({ url: '', token: '', token_set: false, original_url: '' })
}

const removeWebhook = (index) => {
  webhooks.value.splice(index, 1)
}

// A row still being filled in says nothing and just holds the Save button.
const webhookError = (webhook) => {
  const url = webhook.url.trim()
  if (url && (!URL.canParse(url) || !/^https?:\/\//.test(url)))
    return 'Endpoint must be an http:// or https:// URL.'
  return ''
}

const webhookIsComplete = (webhook) => {
  return Boolean(webhook.url.trim()) && Boolean(webhook.token || webhook.token_set)
}

const limitError = (key) => {
  if (!enabled.value[key]) return ''
  const limit = Number(limits.value[key])
  if (!Number.isInteger(limit) || limit < 1 || limit > 100)
    return 'Limit must be a whole percentage between 1 and 100.'
  return ''
}

// Mirrors the server: scheme, a host, a readable port, and no inline password.
const mailUrlIsValid = (url) => {
  if (!/^smtps?:\/\//.test(url) || !URL.canParse(url)) return false
  const parsed = new URL(url)
  return Boolean(parsed.hostname) && !/\s/.test(url)
}

const mailUrlHasPassword = (url) => URL.canParse(url) && Boolean(new URL(url).password)

const mailError = computed(() => {
  const url = mail.value.smtp_url.trim()
  if (url && !mailUrlIsValid(url))
    return 'Server URL must look like smtp://user@mail.example.com:587 or smtps://...'
  if (url && mailUrlHasPassword(url)) return 'Put the password in the field below, not in the URL.'
  const addresses = recipients()
  if (addresses.length && !url) return 'A server URL is required to send alert emails.'
  if (addresses.some((address) => !/^[^@\s]+@[^@\s]+$/.test(address)))
    return 'Recipients must be comma-separated email addresses.'
  return ''
})

const canSave = computed(
  () =>
    RESOURCE_ALERTS.every((alert) => !limitError(alert.key)) &&
    webhooks.value.every((webhook) => webhookIsComplete(webhook) && !webhookError(webhook)) &&
    !mailError.value,
)

const save = async () => {
  if (!canSave.value) return

  error.value = ''
  saving.value = true
  try {
    const payload = buildPayload()
    const result = await settingsApi.update({ resource_limits: payload })
    if (result.error) {
      error.value = apiErrorMessage(result, 'Failed to save.')
      return
    }
    // Drop the typed secrets once stored, so the form reads back like a reload.
    for (const webhook of webhooks.value) {
      webhook.token_set = webhook.token_set || Boolean(webhook.token)
      webhook.token = ''
      webhook.original_url = webhook.url.trim()
    }
    mail.value.smtp_password_set = mail.value.smtp_password_set || Boolean(mail.value.smtp_password)
    mail.value.smtp_password = ''
    savedPayload.value = JSON.stringify(buildPayload())
    toast.success('Notification settings saved')
  } catch (e) {
    error.value = e.message || 'Failed to save.'
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  try {
    const data = await settingsApi.get()
    const saved = data.resource_limits || {}
    for (const alert of RESOURCE_ALERTS) {
      const limit = Number(saved[alert.key]) || 0
      enabled.value[alert.key] = limit > 0
      limits.value[alert.key] = limit ? String(limit) : ''
    }
    siteUptime.value = saved.site_uptime ?? true
    webhooks.value = (saved.webhook_endpoints || []).map((webhook) => ({
      url: webhook.url || '',
      token: '',
      token_set: Boolean(webhook.token_set),
      original_url: webhook.url || '',
    }))
    mail.value = {
      smtp_url: saved.smtp_url || '',
      smtp_password: '',
      smtp_password_set: Boolean(saved.smtp_password_set),
      email_recipients: (saved.email_recipients || []).join(', '),
    }
    savedPayload.value = JSON.stringify(buildPayload())
  } catch (e) {
    error.value = e.message || 'Could not load settings.'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div v-if="loading" class="flex justify-center items-center h-40">
    <Spinner size="lg" class="text-ink-gray-4" />
  </div>

  <div v-else class="space-y-6">
    <SettingsSwitch
      label="Site uptime"
      description="Alert when a site stops responding to its uptime check."
      :model-value="siteUptime"
      @update:model-value="(on) => (siteUptime = on)"
    />

    <div v-for="alert in RESOURCE_ALERTS" :key="alert.key" class="space-y-3">
      <SettingsSwitch
        :label="alert.label"
        :description="alert.description"
        :model-value="enabled[alert.key]"
        @update:model-value="(on) => setEnabled(alert.key, on)"
      />
      <div v-if="enabled[alert.key]" class="flex items-center gap-2 pl-0.5">
        <TextInput
          v-model="limits[alert.key]"
          type="number"
          min="1"
          max="100"
          class="w-24"
          :aria-label="`${alert.label} limit`"
        />
        <span class="text-ink-gray-6 text-base">% and above</span>
      </div>
    </div>

    <div class="space-y-2">
      <div class="flex justify-between items-center">
        <p class="font-medium text-ink-gray-8 text-base leading-normal">Webhook endpoints</p>
        <Button variant="subtle" icon-left="lucide-plus" @click="addWebhook">Add endpoint</Button>
      </div>

      <p class="text-ink-gray-5 text-p-sm">
        Alerts go to Central. Endpoints listed here receive them too, as a POST carrying an
        <code>Authorization: Bearer</code> header, so the token stays out of the URL.
      </p>

      <EmptyState
        compact
        v-if="!webhooks.length"
        icon="lucide-webhook"
        title="No webhook endpoints"
        description="Alerts are only reported to Central. Add an endpoint to receive them yourself."
      />

      <div v-else class="space-y-3">
        <div v-for="(webhook, index) in webhooks" :key="index">
          <div class="flex items-end gap-2">
            <div class="flex-1 space-y-1.5">
              <p v-if="index === 0" class="font-medium text-ink-gray-7 text-base">Endpoint URL</p>
              <TextInput
                v-model="webhook.url"
                placeholder="https://alerts.example.com/pilot"
                class="w-full"
              />
            </div>

            <div class="flex-1 space-y-1.5">
              <p v-if="index === 0" class="font-medium text-ink-gray-7 text-base">Token</p>
              <TextInput
                v-model="webhook.token"
                type="password"
                :placeholder="webhook.token_set ? 'Unchanged' : 'Bearer token'"
                class="w-full"
              />
            </div>

            <Button
              variant="subtle"
              icon="lucide-x"
              label="Remove endpoint"
              tooltip="Remove endpoint"
              @click="removeWebhook(index)"
            />
          </div>

          <p v-if="webhookError(webhook)" class="mt-1.5 text-ink-red-5 text-p-sm">
            {{ webhookError(webhook) }}
          </p>
        </div>
      </div>
    </div>

    <div class="space-y-2">
      <p class="font-medium text-ink-gray-8 text-base leading-normal">Email</p>

      <p class="text-ink-gray-5 text-p-sm">Send the same alerts to a mailbox.</p>

      <div class="gap-3 grid grid-cols-2">
        <div class="space-y-1.5 col-span-2">
          <p class="font-medium text-ink-gray-7 text-base">Server URL</p>
          <TextInput
            v-model="mail.smtp_url"
            placeholder="smtp://alerts@example.com@smtp.example.com:587"
            class="w-full"
          />
        </div>

        <div class="space-y-1.5">
          <p class="font-medium text-ink-gray-7 text-base">Password</p>
          <TextInput
            v-model="mail.smtp_password"
            type="password"
            :placeholder="mail.smtp_password_set ? 'Unchanged' : 'SMTP password'"
            class="w-full"
          />
        </div>

        <div class="space-y-1.5">
          <p class="font-medium text-ink-gray-7 text-base">Recipients</p>
          <TextInput
            v-model="mail.email_recipients"
            placeholder="ops@example.com, oncall@example.com"
            class="w-full"
          />
        </div>
      </div>

      <p v-if="mailError" class="text-ink-red-5 text-p-sm">{{ mailError }}</p>
    </div>

    <ErrorMessage v-if="error" :message="error" />

    <div v-if="dirty" class="flex justify-end">
      <Button variant="solid" :loading="saving" :disabled="!canSave" @click="save">
        Save changes
      </Button>
    </div>
  </div>
</template>
