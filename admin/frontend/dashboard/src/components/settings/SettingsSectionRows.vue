<template>
  <div v-if="openSection">
    <component :is="openSection.component" @passwordChanged="handlePasswordChanged" />
  </div>

  <div v-else class="divide-y divide-outline-alpha-gray-1">
    <SettingsRow
      v-for="section in sections"
      :key="section.id"
      :label="section.label"
      :description="section.description"
    >
      <Button size="sm" variant="subtle" @click="openSection = section">
        {{ section.action || 'Manage' }}
      </Button>
    </SettingsRow>
  </div>
</template>

<script setup>
import { Button } from 'frappe-ui'
import SettingsRow from '@/components/settings/SettingsRow.vue'

defineProps({ sections: { type: Array, required: true } })
const emit = defineEmits(['passwordChanged'])
const openSection = defineModel('openSection')

function handlePasswordChanged() {
  openSection.value = null
  emit('passwordChanged')
}
</script>
