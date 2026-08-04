<template>
  <div class="mt-5">
    <div v-if="appsLoading" class="gap-x-6 gap-y-4 grid grid-cols-1 md:grid-cols-2">
      <MarketplaceAppCardSkeleton v-for="i in 4" :key="i" :index="i - 1" />
    </div>
    <div v-else-if="!installedApps.length" class="py-12 text-ink-gray-5 text-sm text-center">
      No apps installed on this site.
    </div>
    <div v-else class="gap-x-6 gap-y-4 grid grid-cols-1 md:grid-cols-2">
      <MarketplaceAppCard v-for="app in appObjects" :key="app.name" :app="app">
        <template #actions>
          <Dropdown
            v-if="menuOptions(app).length"
            :options="menuOptions(app)"
            placement="bottom-end"
          >
            <template #default="{ open }">
              <Button variant="ghost" size="sm" :active="open">
                <span class="size-4 lucide-ellipsis" />
              </Button>
            </template>
          </Dropdown>
          <span v-else class="size-7 shrink-0" />
        </template>
      </MarketplaceAppCard>
    </div>
  </div>

  <UninstallAppDialog v-model:open="showUninstall" :app="uninstallTarget" :site-name="siteName" />
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { Button, Dropdown } from 'frappe-ui'
import MarketplaceAppCard from '@/components/marketplace/MarketplaceAppCard.vue'
import MarketplaceAppCardSkeleton from '@/components/marketplace/MarketplaceAppCardSkeleton.vue'
import UninstallAppDialog from '@/components/apps/UninstallAppDialog.vue'
import { useSite } from '@/composables/sites/useSite'
import { useAppRegistry } from '@/composables/apps/useAppRegistry'
import { useSession } from '@/composables/auth/useSession'
import { toSentenceCase } from '@/utils/format'

const props = defineProps({
  siteName: { type: String, required: true },
})
const { session } = useSession()

const { apps, installedApps, appsLoading, loadApps } = useSite(props.siteName)
const {
  titleMap,
  descriptionMap,
  logoMap,
  documentationMap,
  websiteMap,
  load: loadRegistry,
} = useAppRegistry()

const appDetailMap = computed(() => Object.fromEntries(apps.value.map((a) => [a.name, a])))

const appObjects = computed(() =>
  installedApps.value.map((name) => ({
    name,
    title: titleMap.value[name] || toSentenceCase(appDetailMap.value[name]?.title) || name,
    label: appDetailMap.value[name]?.version || '',
    description: descriptionMap.value[name] || appDetailMap.value[name]?.description || '',
    logo_url: logoMap.value[name] || null,
    documentation: documentationMap.value[name] || '',
    website: websiteMap.value[name] || '',
  })),
)

const showUninstall = ref(false)
const uninstallTarget = ref(null)

function openLink(url) {
  window.open(url, '_blank', 'noopener,noreferrer')
}

function menuOptions(app) {
  return [
    ...(session.developerMode
      ? [{ label: 'Open in editor', icon: 'lucide-code', onClick: () => openLink(`/editor/${encodeURIComponent(app.name)}`) }]
      : []),
    ...(app.website
      ? [{ label: 'Website', icon: 'lucide-globe', onClick: () => openLink(app.website) }]
      : []),
    ...(app.documentation
      ? [
          {
            label: 'Documentation',
            icon: 'lucide-book-open',
            onClick: () => openLink(app.documentation),
          },
        ]
      : []),
    ...(app.name !== 'frappe'
      ? [
          {
            label: 'Uninstall',
            icon: 'lucide-trash-2',
            theme: 'red',
            onClick: () => {
              uninstallTarget.value = app
              showUninstall.value = true
            },
          },
        ]
      : []),
  ]
}

onMounted(() => {
  loadApps()
  loadRegistry()
})
</script>
