<template>
  <div v-if="openSection">
    <component :is="openSection.component" @passwordChanged="handlePasswordChanged" />
  </div>

  <!-- -mx cancels the rows' own padding, so their text still lines up with the
       section heading while a hovered row reads as inset. -->
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

<script setup>
import SettingsRow from '@/components/settings/SettingsRow.vue'

defineProps({ sections: { type: Array, required: true } })
const emit = defineEmits(['passwordChanged'])
const openSection = defineModel('openSection')

function handlePasswordChanged() {
  openSection.value = null
  emit('passwordChanged')
}
</script>
