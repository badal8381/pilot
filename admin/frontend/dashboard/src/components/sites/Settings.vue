<script setup lang="ts">
import SettingsGeneral from '@/components/sites/settings/General.vue'
import SettingsDomains from '@/components/sites/settings/Domains.vue'
import SettingsActions from '@/components/sites/settings/Actions.vue'
import SettingsDanger from '@/components/sites/settings/Danger.vue'

defineProps({ siteName: { type: String, required: true } })
</script>

<template>
  <div class="space-y-9 mt-5">
    <SettingsGeneral :site-name="siteName" />
    <SettingsDomains :site-name="siteName" />
    <SettingsActions :site-name="siteName" />
    <SettingsDanger :site-name="siteName" />
  </div>
</template>
