<template>
  <Dialog v-model="open" :options="{ title: 'Which site are you browsing for?', size: 'md' }">
    <template #body-content>
      <p v-if="!sites.length" class="py-6 text-ink-gray-5 text-sm text-center">
        No sites on this bench yet. Create a site to install apps.
      </p>

      <template v-else>
        <p class="mb-4 text-ink-gray-6 text-p-sm">
          Installed apps are marked, and installs target this site.
        </p>

        <div class="gap-2 grid max-h-96 overflow-y-auto">
          <SiteRow
            label="All sites"
            subtitle="Browse every available app"
            icon="lucide-layout-grid"
            :selected="!site"
            @click="choose('')"
          >
            <template #suffix>
              <span v-if="!site" class="size-4 text-ink-gray-8 shrink-0 lucide-check" />
            </template>
          </SiteRow>

          <SiteRow
            v-for="s in sites"
            :key="s.name"
            :label="s.name"
            :subtitle="siteSubtitle(s)"
            :selected="s.name === site"
            @click="choose(s.name)"
          >
            <template #suffix>
              <span v-if="s.name === site" class="size-4 text-ink-gray-8 shrink-0 lucide-check" />
            </template>
          </SiteRow>
        </div>
      </template>
    </template>
  </Dialog>
</template>

<script setup>
import { Dialog } from 'frappe-ui'
import SiteRow from '@/components/sites/SiteRow.vue'

defineProps({
  sites: { type: Array, default: () => [] },
})
const open = defineModel('open')
const site = defineModel('site')

function siteSubtitle(s) {
  const count = s.installed_apps?.length || 0
  const match = /^version-(\d+)/.exec(s.framework_branch || '')
  const version = match ? ` · Version ${match[1]}` : ''
  return `${count} app${count === 1 ? '' : 's'}${version}`
}

function choose(name) {
  site.value = name
  open.value = false
}
</script>
