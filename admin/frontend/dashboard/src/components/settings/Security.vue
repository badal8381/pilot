<template>
  <SettingsSectionRows :sections="sections" v-model:open-section="openSection" />
</template>

<script setup>
import SettingsSectionRows from '@/components/settings/SettingsSectionRows.vue'
import { SECURITY_SECTIONS as sections } from '@/components/settings/sections'

const openSection = defineModel('openSection')
</script>
