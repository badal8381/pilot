<script setup lang="ts">
import SettingsRow from '@/components/settings/SettingsRow.vue'

interface Props {
  sections: any[]
}

defineProps<Props>()
const emit = defineEmits(['passwordChanged'])
const openSection = defineModel('openSection')

const handlePasswordChanged = () => {
  openSection.value = null
  emit('passwordChanged')
}
</script>

<template>
  <component
    v-if="openSection"
    :is="openSection.component"
    @passwordChanged="handlePasswordChanged"
  />

  <div v-else class="-mx-2.5 divide-y divide-outline-alpha-gray-1 hover-merges-dividers">
    <SettingsRow
      v-for="section in sections"
      :key="section.id"
      as="button"
      interactive
      :label="section.label"
      :description="section.description"
      @click="openSection = section"
    >
      <span class="size-4 text-ink-gray-5 lucide-chevron-right" aria-hidden="true" />
    </SettingsRow>
  </div>
</template>
