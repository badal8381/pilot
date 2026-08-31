<script setup lang="ts">
import DatabaseQuickActions from '@/components/settings/DatabaseQuickActions.vue'
import SettingsRow from '@/components/settings/SettingsRow.vue'

import { DATABASE_SECTIONS } from '@/components/settings/sections'

const openSection = defineModel('openSection')
const configurationSection = DATABASE_SECTIONS.find((section) => section.id === 'configurations')
</script>

<template>
  <component v-if="openSection" :is="openSection.component" />

  <template v-else>
    <section>
      <h4 class="mb-1 font-medium text-ink-gray-6">Database actions</h4>
      <DatabaseQuickActions />
    </section>

    <div class="-mx-2.5 mt-2 border-t rounded border-outline-alpha-gray-1">
      <SettingsRow
        as="button"
        interactive
        :label="configurationSection.label"
        :description="configurationSection.description"
        @click="openSection = configurationSection"
      >
        <span class="size-4 text-ink-gray-5 lucide-chevron-right" aria-hidden="true" />
      </SettingsRow>
    </div>
  </template>
</template>
