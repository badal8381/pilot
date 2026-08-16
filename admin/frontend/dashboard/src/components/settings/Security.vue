<script setup lang="ts">
import { ref } from 'vue'
import { Button, Dialog, toast } from 'frappe-ui'

import SettingsSectionRows from '@/components/settings/SettingsSectionRows.vue'

import { SECURITY_SECTIONS as sections } from '@/components/settings/sections'
import { sessionApi } from '@/api/session'

const openSection = defineModel('openSection')

const showRevokePrompt = ref(false)
const revoking = ref(false)

const revokeOtherSessions = async () => {
  revoking.value = true
  try {
    const result = await sessionApi.revokeAll()
    const others = Math.max((result.revoked_sessions || 0) - 1, 0)
    toast.success(others ? `${others} other session${others === 1 ? '' : 's'} signed out` : 'No other sessions to revoke')
    showRevokePrompt.value = false
  } catch (e) {
    toast.error(e.message || 'Could not revoke other sessions.')
  } finally {
    revoking.value = false
  }
}
</script>

<template>
  <SettingsSectionRows
    :sections="sections"
    v-model:open-section="openSection"
    @passwordChanged="showRevokePrompt = true"
  />

  <Dialog v-model="showRevokePrompt" title="Password changed" size="md">
    <p class="text-ink-gray-7 text-p-base">
      Revoke every other active session? Anyone signed in elsewhere will be signed out
      immediately — this browser stays signed in.
    </p>

    <div class="flex justify-end gap-2 mt-4">
      <Button variant="ghost" :disabled="revoking" @click="showRevokePrompt = false">
        Not now
      </Button>

      <Button variant="solid" theme="red" :loading="revoking" @click="revokeOtherSessions">
        Revoke other sessions
      </Button>
    </div>
  </Dialog>
</template>
