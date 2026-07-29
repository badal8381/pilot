<template>
  <Dialog v-model:open="open" size="xs">
    <div class="flex flex-col items-center p-6 text-center">
      <div
        v-if="isLoading"
        class="bg-surface-gray-2 rounded-2xl size-20 shrink-0 animate-pulse"
      />
      <AppIcon
        v-else
        :name="appName"
        :label="title"
        class="rounded-2xl size-20 ring-1 ring-outline-gray-2"
        initial-class="text-3xl"
      />

      <div v-if="isLoading" class="flex flex-col items-center gap-2 mt-5">
        <div class="bg-surface-gray-2 rounded w-32 h-5 animate-pulse" />
        <div class="bg-surface-gray-2 rounded w-44 h-3.5 animate-pulse" />
      </div>
      <div v-else class="mt-5">
        <p class="font-semibold text-ink-gray-9 text-xl leading-tight">{{ title }}</p>
        <p v-if="description" class="mt-1 text-ink-gray-5 text-p-sm">{{ description }}</p>
      </div>

      <template v-if="!isLoading">
        <div class="w-full border-outline-gray-2 border-t mt-5" />
        <p class="mt-4 text-ink-gray-6 text-p-base font-medium">{{ statusText }}</p>
        <Button v-if="isInstall" class="mt-4 w-full" variant="subtle" :loading="loggingIn" @click="loginToSite">
          Login to site
        </Button>
      </template>
    </div>
  </Dialog>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { Button, Dialog, toast } from 'frappe-ui'
import AppIcon from '@/components/apps/AppIcon.vue'
import { useAppRegistry } from '@/composables/apps/useAppRegistry'
import { useSite } from '@/composables/sites/useSite'

const DESCRIPTION_MAX_LENGTH = 50

const props = defineProps({
  appName: { type: String, required: true },
  action: { type: String, required: true },
  siteName: { type: String, required: true },
})
const open = defineModel('open')

const { titleMap, descriptionMap, loaded, load } = useAppRegistry()
const { login } = useSite(props.siteName)
const loggingIn = ref(false)

const isLoading = computed(() => !loaded.value)
const title = computed(() => titleMap.value[props.appName] || props.appName)
const description = computed(() => {
  const text = descriptionMap.value[props.appName] || ''
  if (text.length <= DESCRIPTION_MAX_LENGTH) return text
  return `${text.slice(0, DESCRIPTION_MAX_LENGTH)}…`
})
const isInstall = computed(() => props.action === 'install-app')
const statusText = computed(() =>
  isInstall.value ? 'Installed successfully' : 'Uninstalled successfully',
)

async function loginToSite() {
  loggingIn.value = true
  try {
    await login()
  } catch (caught) {
    toast.error(caught.message || 'Could not log in to the site')
  } finally {
    loggingIn.value = false
  }
}

onMounted(load)
</script>
