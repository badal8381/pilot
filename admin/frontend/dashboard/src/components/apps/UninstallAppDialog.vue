<template>
  <Dialog v-model="open" title="Uninstall App" size="md">
    <template #default>
      <div class="space-y-4">
        <div class="flex items-center gap-3">
          <AppIcon
            :name="app?.name || ''"
            :label="appLabel"
            :logo="app?.logo_url || ''"
            class="rounded-[10px] size-11"
            initial-class="text-lg"
          />
          <div class="min-w-0">
            <div class="flex items-center gap-1.5">
              <p class="font-medium text-ink-gray-8 text-base truncate">{{ appLabel }}</p>
              <span v-if="app?.label" class="text-ink-gray-5 text-p-xs shrink-0">
                {{ app.label }}
              </span>
            </div>
            <p v-if="app?.description" class="text-ink-gray-5 text-p-sm line-clamp-2">
              {{ app.description }}
            </p>
          </div>
        </div>

        <div class="border-outline-gray-2 border-t" />

        <div class="space-y-2">
          <p class="font-medium text-ink-gray-5 text-p-xs uppercase tracking-wide">Uninstall from</p>
          <SiteRow :label="siteName" icon="lucide-globe" :interactive="false" />
        </div>

        <div class="flex items-start gap-3 bg-surface-red-1 p-3 border border-outline-red-2 rounded-lg">
          <span class="mt-0.5 size-4 text-ink-red-6 lucide-alert-triangle shrink-0" />
          <div class="min-w-0 text-p-sm text-ink-red-8">
            <p class="font-medium">This can't be undone.</p>
            <p class="mt-0.5 leading-5">
              Every doctype {{ appLabel }} owns is dropped from {{ siteName }}, along with the
              records in it. Back the site up first if you need the data.
            </p>
          </div>
        </div>

        <ErrorMessage v-if="error" :message="error" />

        <div class="flex justify-end gap-2">
          <Button variant="subtle" @click="open = false">Cancel</Button>
          <Button variant="solid" theme="red" :loading="uninstalling" @click="confirmUninstall">
            Uninstall
          </Button>
        </div>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Button, Dialog, ErrorMessage } from 'frappe-ui'
import AppIcon from '@/components/apps/AppIcon.vue'
import SiteRow from '@/components/sites/SiteRow.vue'
import { apiErrorMessage } from '@/api/client'
import { sitesApi } from '@/api/sites'
import { openTaskDetailPage } from '@/utils/taskRoute'

const props = defineProps({
  app: { type: Object, default: null },
  siteName: { type: String, required: true },
})
const open = defineModel('open')
const router = useRouter()

const uninstalling = ref(false)
const error = ref('')

const appLabel = computed(() => props.app?.title || props.app?.name || '')

watch(open, (isOpen) => {
  if (isOpen) error.value = ''
})

async function confirmUninstall() {
  if (!props.app || uninstalling.value) return
  error.value = ''
  uninstalling.value = true
  try {
    const result = await sitesApi.apps.remove(props.siteName, props.app.name)
    if (!result.task_id) throw new Error(apiErrorMessage(result, 'Uninstall failed.'))
    open.value = false
    openTaskDetailPage(router, result.task_id)
  } catch (caught) {
    error.value = caught.message || 'Could not start uninstall.'
  } finally {
    uninstalling.value = false
  }
}
</script>
