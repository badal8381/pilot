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
      <!-- Icon-only, so the row's action still needs an accessible name. -->
      <Button
        size="sm"
        variant="ghost"
        icon="lucide-chevron-right"
        :aria-label="`${section.action || 'Manage'} ${section.label}`"
        @click="openSection = section"
      />
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
