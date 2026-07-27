<template>
  <div class="space-y-4">
    <Alert title="Admin password" theme="blue" :dismissible="false">
      <template #description>
        <p class="text-ink-gray-6 text-p-sm">
          The password that signs in to this bench. Changing it signs out every other session
          immediately — this browser stays signed in.
        </p>
      </template>
    </Alert>

    <PasswordInput
      v-model="currentPassword"
      label="Current password"
      placeholder="••••••••"
      autocomplete="current-password"
    />
    <div class="space-y-2">
      <PasswordInput
        v-model="newPassword"
        label="New password"
        placeholder="New password"
        autocomplete="new-password"
      />
      <PasswordStrengthMeter :password="newPassword" />
    </div>
    <PasswordInput
      v-model="confirmPassword"
      label="Confirm new password"
      placeholder="Repeat new password"
      autocomplete="new-password"
    />

    <ErrorMessage v-if="error" :message="error" />
    <div class="flex justify-end">
      <Button variant="solid" :loading="saving" :disabled="!canSubmit" @click="save">
        Change password
      </Button>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Alert, Button, ErrorMessage, toast } from 'frappe-ui'
import PasswordInput from '@/components/common/PasswordInput.vue'
import PasswordStrengthMeter from '@/components/common/PasswordStrengthMeter.vue'
import { settingsApi } from '@/api/settings'
import { meetsPasswordRequirements } from '@/utils/passwordStrength'

const emit = defineEmits(['changed'])

const currentPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const saving = ref(false)
const error = ref('')

const canSubmit = computed(
  () => Boolean(currentPassword.value) && meetsPasswordRequirements(newPassword.value),
)

function validationError() {
  if (newPassword.value !== confirmPassword.value) return 'New passwords do not match.'
  if (newPassword.value === currentPassword.value)
    return 'New password must differ from the current password.'
  return ''
}

function reset() {
  currentPassword.value = ''
  newPassword.value = ''
  confirmPassword.value = ''
}

async function save() {
  error.value = validationError()
  if (error.value) return

  saving.value = true
  try {
    const result = await settingsApi.changeAdminPassword({
      current_password: currentPassword.value,
      new_password: newPassword.value,
    })
    reset()
    toast.success(signedOutMessage(result.revoked_sessions))
    emit('changed')
  } catch (e) {
    error.value = e.message || 'Could not change the password.'
  } finally {
    saving.value = false
  }
}

function signedOutMessage(revoked) {
  const others = Math.max((revoked || 0) - 1, 0)
  if (!others) return 'Password changed'
  return `Password changed — ${others} other session${others === 1 ? '' : 's'} signed out`
}
</script>
