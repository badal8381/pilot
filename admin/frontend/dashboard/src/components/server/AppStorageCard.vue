<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { appsApi } from '@/api/apps'
import UsageMeter from '@/components/common/UsageMeter.vue'
import { logoColor } from '@/composables/apps/useMarketplace'
import type { BenchBreakdown } from '@/types/storage'
import { formatBytes } from '@/utils/format'

interface Props {
  data: BenchBreakdown
  diskTotal: number
}

const props = defineProps<Props>()

const logoByName = ref<Record<string, string>>({})
const failedLogos = reactive(new Set<string>())

onMounted(async () => {
  try {
    const registry = await appsApi.marketplace()
    logoByName.value = Object.fromEntries(
      registry.filter((app) => app.logo_url).map((app) => [app.name, app.logo_url]),
    )
  } catch {
    logoByName.value = {}
  }
})

const COLORS = { apps: 'blue-7', sites: 'violet-7', logs: 'amber-7' }

const bySize = (items: { bytes: number }[]) => [...items].sort((a, b) => b.bytes - a.bytes)

const groups = computed(() => [
  {
    label: 'Apps',
    icon: 'lucide-package',
    badge: true,
    color: COLORS.apps,
    bytes: props.data.apps_bytes,
    items: bySize(props.data.apps),
  },
  {
    label: 'Site files',
    icon: 'lucide-globe',
    badge: false,
    color: COLORS.sites,
    bytes: props.data.sites_bytes,
    items: bySize(props.data.sites),
  },
  {
    label: 'Logs',
    icon: '',
    badge: false,
    color: COLORS.logs,
    bytes: props.data.logs_bytes,
    items: [],
  },
])
</script>

<template>
  <section class="p-5 min-w-0">
    <div class="flex justify-between items-center gap-3 mb-4">
      <h3 class="flex items-center gap-2 font-medium text-ink-gray-8 text-base">
        <lucide-box class="size-4" />
        App storage
      </h3>

      <div class="text-ink-gray-6 text-sm">
        <span class="font-medium text-ink-gray-8">{{ formatBytes(data.used_bytes) }}</span>
        of {{ formatBytes(diskTotal) }} used
      </div>
    </div>

    <UsageMeter :parts="groups" :total="diskTotal" bar-height="h-5">
      <template #row="{ part }">
        <details v-if="part.items.length" class="group">
          <summary class="flex items-center gap-2 py-2 list-none cursor-pointer">
            <span class="rounded-full size-2 shrink-0" :style="{ backgroundColor: part.color }" />
            <span class="text-ink-gray-7 text-sm truncate">{{ part.label }}</span>
            <lucide-chevron-up
              class="transition-all size-3.5 text-ink-gray-5 rotate-180 group-open:rotate-0"
            />
            <span class="ml-auto text-ink-gray-8 text-sm tabular-nums shrink-0">
              {{ part.text }}
            </span>
          </summary>

          <div
            v-for="item in part.items"
            :key="item.name"
            class="flex justify-between items-center gap-4 py-1.5 pl-4"
          >
            <span class="flex items-center gap-2 min-w-0">
              <img
                v-if="part.badge && logoByName[item.name] && !failedLogos.has(item.name)"
                :src="logoByName[item.name]"
                :alt="item.name"
                class="rounded-sm size-4 shrink-0 object-contain"
                @error="failedLogos.add(item.name)"
              />
              <span
                v-else-if="part.badge"
                class="grid place-items-center rounded-sm size-4 font-bold text-[9px] text-white shrink-0"
                :style="{ backgroundColor: logoColor(item.name) }"
              >
                {{ item.name[0]?.toUpperCase() }}
              </span>
              <span v-else class="size-3.5 text-ink-gray-4 shrink-0" :class="part.icon" />
              <span class="text-ink-gray-6 text-sm truncate">{{ item.name }}</span>
            </span>

            <span class="text-ink-gray-7 text-sm tabular-nums shrink-0">
              {{ formatBytes(item.bytes) }}
            </span>
          </div>
        </details>

        <div v-else class="flex items-center gap-2 py-2">
          <span class="rounded-full size-2 shrink-0" :style="{ backgroundColor: part.color }" />
          <span class="text-ink-gray-7 text-sm truncate mr-auto">{{ part.label }}</span>
          <span class="text-ink-gray-8 text-sm tabular-nums shrink-0">{{ part.text }}</span>
        </div>
      </template>
    </UsageMeter>
  </section>
</template>
