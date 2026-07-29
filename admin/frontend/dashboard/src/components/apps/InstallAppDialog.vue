<template>
  <ActionDialog
    v-model:open="open"
    title="Install App"
    :subject="{ name: app?.name, label: appLabel, badge: app?.label, description: app?.description, logo: app?.logo_url }"
    :error="error"
    confirm-label="Install"
    :loading="installing"
    :disabled="!selection || presetInstalled"
    @confirm="confirmInstall"
  >
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
  </ActionDialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import ActionDialog from '@/components/common/ActionDialog.vue'
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
