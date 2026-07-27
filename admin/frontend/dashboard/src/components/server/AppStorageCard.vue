<script setup lang="ts">
import { computed } from 'vue'
import UsageMeter from '@/components/common/UsageMeter.vue'
import StorageGroup from '@/components/server/StorageGroup.vue'
import type { BenchBreakdown } from '@/types/storage'
import { formatBytes } from '@/utils/format'

interface Props {
  data: BenchBreakdown
  diskTotal: number
}

const props = defineProps<Props>()

const COLORS = { apps: '#3b82f6', sites: '#a855f7', logs: '#eab308' }

const groupParts = computed(() => [
  { label: 'Apps', bytes: props.data.apps_bytes, color: COLORS.apps },
  { label: 'Site files', bytes: props.data.sites_bytes, color: COLORS.sites },
  { label: 'Logs', bytes: props.data.logs_bytes, color: COLORS.logs },
])
</script>

<template>
  <section class="bg-surface-white p-5 border rounded-lg border-outline-gray-2 min-w-0">
    <div class="flex justify-between items-center gap-3 mb-4">
      <h3 class="flex items-center gap-2 font-medium text-ink-gray-8 text-base">
        <span class="size-4 lucide-box" />
        App storage
      </h3>
      <div class="text-ink-gray-6 text-sm">
        <span class="font-medium text-ink-gray-9">{{ formatBytes(data.used_bytes) }}</span>
        of {{ formatBytes(diskTotal) }} used
      </div>
    </div>

    <UsageMeter :parts="groupParts" :total="diskTotal" :legend="false" />

    <div class="mt-3">
      <StorageGroup
        label="Apps"
        icon="lucide-package"
        badge
        :color="COLORS.apps"
        :bytes="data.apps_bytes"
        :items="data.apps"
      />
      <StorageGroup
        label="Site files"
        icon="lucide-globe"
        :color="COLORS.sites"
        :bytes="data.sites_bytes"
        :items="data.sites"
      />
      <StorageGroup
        label="Logs"
        icon="lucide-file-text"
        :color="COLORS.logs"
        :bytes="data.logs_bytes"
      />
    </div>
  </section>
</template>
