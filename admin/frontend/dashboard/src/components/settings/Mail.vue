<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { Button, ErrorMessage, Spinner, TextInput, toast } from 'frappe-ui'

import { apiErrorMessage } from '@/api/client'
import { settingsApi } from '@/api/settings'

const loading = ref(true)
const saving = ref(false)
const error = ref('')
const smtpUrl = ref('')
const smtpPassword = ref('')
const smtpPasswordSet = ref(false)
const recipients = ref([])

const savedPayload = ref('')
const dirty = computed(() => JSON.stringify(buildPayload()) !== savedPayload.value)

const buildPayload = () => ({
  smtp_url: smtpUrl.value.trim(),
  smtp_password: smtpPassword.value,
  email_recipients: recipients.value.map((r) => r.trim()).filter(Boolean),
})

const addRecipient = () => {
  recipients.value.push('')
}

const removeRecipient = (index) => {
  recipients.value.splice(index, 1)
}

// Mirrors the server: scheme, a host, a readable port, and no inline password.
const mailUrlIsValid = (url) => {
  if (!/^smtps?:\/\//.test(url) || !URL.canParse(url)) return false
  const parsed = new URL(url)
  return Boolean(parsed.hostname) && !/\s/.test(url)
}

const mailUrlHasPassword = (url) => URL.canParse(url) && Boolean(new URL(url).password)

const recipientError = (address) => {
  const trimmed = address.trim()
  if (trimmed && !/^[^@\s]+@[^@\s]+$/.test(trimmed)) return 'Must be an email address.'
  return ''
}

const mailError = computed(() => {
  const url = smtpUrl.value.trim()
  if (url && !mailUrlIsValid(url))
    return 'Server URL must look like smtp://user@mail.example.com:587 or smtps://...'
  if (url && mailUrlHasPassword(url)) return 'Put the password in the field below, not in the URL.'
  const addresses = buildPayload().email_recipients
  if (addresses.length && !url) return 'A server URL is required to send alert emails.'
  return ''
})

const canSave = computed(
  () => !mailError.value && recipients.value.every((address) => !recipientError(address)),
)

const save = async () => {
  if (!canSave.value) return

  error.value = ''
  saving.value = true
  try {
    const result = await settingsApi.update({ resource_limits: buildPayload() })
    if (result.error) {
      error.value = apiErrorMessage(result, 'Failed to save.')
      return
    }
    smtpPasswordSet.value = smtpPasswordSet.value || Boolean(smtpPassword.value)
    smtpPassword.value = ''
    savedPayload.value = JSON.stringify(buildPayload())
    toast.success('Mail settings saved')
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
    smtpUrl.value = saved.smtp_url || ''
    smtpPasswordSet.value = Boolean(saved.smtp_password_set)
    recipients.value = saved.email_recipients?.length ? [...saved.email_recipients] : ['']
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
    <p class="text-ink-gray-5 text-p-sm">
      Send resource and uptime alerts to a mailbox, alongside Central and any webhook endpoints.
    </p>

    <div class="space-y-1.5">
      <p class="font-medium text-ink-gray-7 text-base">Server URL</p>
      <TextInput
        v-model="smtpUrl"
        placeholder="smtp://alerts@example.com@smtp.example.com:587"
        class="w-full"
      />
    </div>

    <div class="space-y-1.5">
      <p class="font-medium text-ink-gray-7 text-base">Password</p>
      <TextInput
        v-model="smtpPassword"
        type="password"
        :placeholder="smtpPasswordSet ? 'Unchanged' : 'SMTP password'"
        class="w-full"
      />
    </div>

    <div class="space-y-2">
      <div class="flex justify-between items-center">
        <p class="font-medium text-ink-gray-7 text-base">Recipients</p>
        <Button variant="subtle" icon-left="lucide-plus" @click="addRecipient">Add recipient</Button>
      </div>

      <div class="space-y-2">
        <div v-for="(address, index) in recipients" :key="index">
          <div class="flex items-center gap-2">
            <TextInput v-model="recipients[index]" placeholder="ops@example.com" class="w-full" />
            <Button
              variant="subtle"
              icon="lucide-x"
              label="Remove recipient"
              tooltip="Remove recipient"
              @click="removeRecipient(index)"
            />
          </div>
          <p v-if="recipientError(address)" class="mt-1.5 text-ink-red-5 text-p-sm">
            {{ recipientError(address) }}
          </p>
        </div>
      </div>
    </div>

    <p v-if="mailError" class="text-ink-red-5 text-p-sm">{{ mailError }}</p>

    <ErrorMessage v-if="error" :message="error" />
    <div v-if="dirty" class="flex justify-end">
      <Button variant="solid" :loading="saving" :disabled="!canSave" @click="save">
        Save changes
      </Button>
    </div>
  </div>
</template>
