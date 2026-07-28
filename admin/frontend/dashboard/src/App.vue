<template>
  <FrappeUIProvider>
    <ReconnectOverlay :paused="awaitingTerminal" />
    <SignedOutDialog />
    <RouterView v-if="isFullScreen" />
    <MainLayout v-else>
      <RouterView />
    </MainLayout>
  </FrappeUIProvider>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useTheme, FrappeUIProvider } from 'frappe-ui'
import ReconnectOverlay from './components/common/ReconnectOverlay.vue'
import SignedOutDialog from './components/common/SignedOutDialog.vue'
import MainLayout from './layouts/MainLayout.vue'
import { useSetupHandoff } from './composables/setup/useSetupHandoff'

const route = useRoute()
const isFullScreen = computed(() => route.meta.fullScreen === true)
const { awaitingTerminal } = useSetupHandoff()
const { initializeTheme } = useTheme()

initializeTheme()
</script>
