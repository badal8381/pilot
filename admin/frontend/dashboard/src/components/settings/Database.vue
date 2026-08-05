<template>
  <SettingsSectionRows v-model:open-section="openSection" :sections="sections" />
</template>

<script setup>
import SettingsSectionRows from '@/components/settings/SettingsSectionRows.vue'
import { DATABASE_SECTIONS as sections } from '@/components/settings/sections'

const openSection = defineModel('openSection')
</script>
