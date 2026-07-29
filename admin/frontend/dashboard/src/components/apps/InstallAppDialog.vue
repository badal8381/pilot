<template>
  <Dialog v-model="open" :title="`Install ${appLabel}`" size="md">
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
          <p class="font-medium text-ink-gray-5 text-p-xs uppercase tracking-wide">Install on</p>

          <SiteRow
            v-if="presetSite"
            :label="presetSite.name"
            :subtitle="presetInstalled ? 'Already installed' : siteVersion(presetSite)"
            :icon="presetInstalled ? 'lucide-check' : 'lucide-globe'"
            :checked="presetInstalled"
            :interactive="false"
          />

          <div v-else class="gap-2 grid max-h-80 overflow-y-auto">
            <SiteRow
              v-if="showAllSitesOption"
              label="All sites"
              :subtitle="`Installs on ${installableSites.length} sites`"
              icon="lucide-layout-grid"
              :selected="selection === 'all'"
              @click="selection = 'all'"
            />

            <SiteRow
              v-for="s in sites"
              :key="s.name"
              :label="s.name"
              :subtitle="isInstalled(s) ? 'Already installed' : siteVersion(s)"
              :icon="isInstalled(s) ? 'lucide-check' : 'lucide-globe'"
              :checked="isInstalled(s)"
              :disabled="isInstalled(s)"
              :selected="selection === s.name"
              @click="selection = s.name"
            />

            <p v-if="!sites.length" class="py-6 text-ink-gray-5 text-sm text-center">
              No sites available on this bench.
            </p>
          </div>
        </div>

        <ErrorMessage v-if="error" :message="error" />

        <div class="flex justify-end gap-2">
          <Button variant="subtle" @click="open = false">Cancel</Button>
          <Button
            variant="solid"
            :disabled="!selection || presetInstalled"
            :loading="installing"
            @click="confirmInstall"
          >
            Install
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
  sites: { type: Array, default: () => [] },
  siteName: { type: String, default: '' },
})
const open = defineModel('open')
const router = useRouter()

const selection = ref(null)
const installing = ref(false)
const error = ref('')

const appLabel = computed(() => props.app?.title || props.app?.name || '')

const presetSite = computed(() => props.sites.find((s) => s.name === props.siteName) || null)
const presetInstalled = computed(() => Boolean(presetSite.value && isInstalled(presetSite.value)))

watch(open, (isOpen) => {
  if (!isOpen) return
  selection.value = props.siteName || null
  error.value = ''
})

const installableSites = computed(() => props.sites.filter((s) => !isInstalled(s)))
// Hide "All sites" when there's only one site on the bench, or only one site left to install on.
const showAllSitesOption = computed(() => props.sites.length > 1 && installableSites.value.length > 1)

function isInstalled(site) {
  return Boolean(props.app && site.installed_apps?.includes(props.app.name))
}

function siteVersion(site) {
  const match = /^version-(\d+)/.exec(site.framework_branch || '')
  return match ? `Version ${match[1]}` : ''
}

async function startInstall(site) {
  const result = await sitesApi.apps.install(site.name, {
    app: props.app.name,
  })
  if (!result.task_id)
    throw new Error(apiErrorMessage(result, `Could not install on ${site.name}.`))
  return result.task_id
}

async function installOnSite(name) {
  const site = props.sites.find((s) => s.name === name)
  if (!site) return
  const taskId = await startInstall(site)
  open.value = false
  openTaskDetailPage(router, taskId)
}

async function installOnAllSites() {
  const targets = installableSites.value
  if (!targets.length) return
  await Promise.all(targets.map((site) => startInstall(site)))
  open.value = false
  router.push({ name: 'Tasks' })
}

async function confirmInstall() {
  if (!selection.value || installing.value) return
  error.value = ''
  installing.value = true
  try {
    if (selection.value === 'all') await installOnAllSites()
    else await installOnSite(selection.value)
  } catch (caught) {
    error.value = caught.message || 'Could not start install.'
  } finally {
    installing.value = false
  }
}
</script>
