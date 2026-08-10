<template>
  <div v-if="loading" class="flex justify-center items-center h-40">
    <Spinner size="lg" class="text-ink-gray-4" />
  </div>
  <div v-else class="space-y-6">
    <div v-for="alert in RESOURCE_ALERTS" :key="alert.key" class="space-y-3">
      <SettingsSwitch
        :label="alert.label"
        :description="alert.description"
        :model-value="limits[alert.key] > 0"
        @update:model-value="(on) => setEnabled(alert.key, on)"
      />
      <div v-if="limits[alert.key] > 0" class="flex items-center gap-2 pl-0.5">
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

    <SettingsSwitch
      label="Site uptime"
      description="Alert when a site stops responding to its uptime check."
      :model-value="siteUptime"
      @update:model-value="(on) => (siteUptime = on)"
    />

    <details class="group">
      <!-- Disclosure markup matches Waf.vue's Advanced section. -->
      <summary
        class="flex items-center gap-1.5 pr-1.5 rounded-sm w-fit text-ink-gray-6 text-base cursor-pointer select-none"
        @click="(e) => e.currentTarget.blur()"
      >
        <span
          class="size-4 transition-transform group-open:rotate-90 lucide-chevron-right"
        ></span>Advanced
      </summary>
      <div class="space-y-4 mt-4">
        <p class="text-ink-gray-5 text-p-sm">
          Alerts go to Central. Add webhook endpoints to receive them yourself as well. Each is sent
          a POST with an <code>Authorization: Bearer</code> header carrying its token, so keep the
          secret out of the URL.
        </p>

        <div v-for="(webhook, index) in webhooks" :key="index" class="flex items-start gap-3">
          <div class="flex-1 space-y-1.5">
            <p v-if="index === 0" class="font-medium text-ink-gray-7 text-base">Endpoint URL</p>
            <TextInput
              v-model="webhook.url"
              type="text"
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
            class="mt-1.5"
            :class="{ 'sm:mt-8': index === 0 }"
            variant="subtle"
            icon="lucide-x"
            label="Remove endpoint"
            tooltip="Remove endpoint"
            @click="removeWebhook(index)"
          />
        </div>

        <div class="flex justify-start">
          <Button variant="subtle" icon-left="lucide-plus" @click="addWebhook">
            Add endpoint
          </Button>
        </div>
      </div>
    </details>

    <ErrorMessage v-if="error" :message="error" />

    <div v-if="dirty" class="flex justify-end">
      <Button variant="solid" :loading="saving" @click="save">Save changes</Button>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { Button, ErrorMessage, Spinner, TextInput, toast } from 'frappe-ui'
import SettingsSwitch from '@/components/settings/SettingsSwitch.vue'
import { apiErrorMessage } from '@/api/client'
import { settingsApi } from '@/api/settings'

// The stored percentage is the only state: 0 means the alert is off, so the
// switch reads from it and turning one on seeds this starting limit.
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
const limits = ref(Object.fromEntries(RESOURCE_ALERTS.map((alert) => [alert.key, 0])))
const siteUptime = ref(true)
const webhooks = ref([])

const savedPayload = ref('')
const dirty = computed(() => JSON.stringify(buildPayload()) !== savedPayload.value)

function buildPayload() {
  return {
    ...Object.fromEntries(
      RESOURCE_ALERTS.map((alert) => [alert.key, Number(limits.value[alert.key]) || 0]),
    ),
    site_uptime: siteUptime.value,
    // A blank token on a stored endpoint means "keep the one you have", the
    // same contract s3.secret_key and llm.api_key already use.
    webhook_endpoints: webhooks.value.map((webhook) => ({
      url: webhook.url.trim(),
      token: webhook.token,
    })),
  }
}

function addWebhook() {
  webhooks.value.push({ url: '', token: '', token_set: false })
}

function removeWebhook(index) {
  webhooks.value.splice(index, 1)
}

function setEnabled(key, enabled) {
  const alert = RESOURCE_ALERTS.find((entry) => entry.key === key)
  limits.value[key] = enabled ? alert.initial : 0
}

function validate() {
  for (const alert of RESOURCE_ALERTS) {
    const limit = Number(limits.value[alert.key])
    if (!Number.isInteger(limit) || limit < 0 || limit > 100)
      return `${alert.label} limit must be a whole percentage between 1 and 100.`
  }
  return webhookProblem()
}

// The token rides in a header, so an endpoint that is not TLS would put it on
// the wire in clear text.
function webhookProblem() {
  for (const [index, webhook] of webhooks.value.entries()) {
    const position = `Endpoint ${index + 1}`
    const url = webhook.url.trim()
    if (!url) return `${position} needs a URL.`
    if (!URL.canParse(url) || !url.startsWith('https://'))
      return `${position} must be an https:// URL.`
    if (!webhook.token && !webhook.token_set) return `${position} needs a token.`
  }
  return ''
}

async function save() {
  error.value = validate()
  if (error.value) return

  saving.value = true
  try {
    const payload = buildPayload()
    const result = await settingsApi.update({ resource_limits: payload })
    if (result.error) {
      error.value = apiErrorMessage(result, 'Failed to save.')
      return
    }
    // Drop the typed secrets once they are stored, so the form stops holding
    // them and reads back the same way a reload would.
    for (const webhook of webhooks.value) {
      webhook.token_set = webhook.token_set || Boolean(webhook.token)
      webhook.token = ''
    }
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
    for (const alert of RESOURCE_ALERTS) limits.value[alert.key] = Number(saved[alert.key]) || 0
    // Uptime alerts are on unless the host has explicitly turned them off.
    siteUptime.value = saved.site_uptime ?? true
    webhooks.value = (saved.webhook_endpoints || []).map((webhook) => ({
      url: webhook.url || '',
      token: '',
      token_set: Boolean(webhook.token_set),
    }))
    savedPayload.value = JSON.stringify(buildPayload())
  } catch (e) {
    error.value = e.message || 'Could not load settings.'
  } finally {
    loading.value = false
  }
})
</script>
