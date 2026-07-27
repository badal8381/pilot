<script setup lang="ts">
import { Badge } from 'frappe-ui'
import { computed, ref } from 'vue'
import UsageMeter from '@/components/common/UsageMeter.vue'
import type { DatabaseBreakdown } from '@/types/storage'
import { formatBytes } from '@/utils/format'

interface Props {
  data: DatabaseBreakdown
  diskTotal: number
}

const props = defineProps<Props>()

const COLORS = { binlog: '#f59e0b', databases: '#a855f7', core: '#06b6d4' }
const VISIBLE_DATABASE_COUNT = 5

const groupParts = computed(() => {
  const schemaBytes = props.data.databases.reduce((sum, row) => sum + row.bytes, 0)
  const systemNames = props.data.databases.filter((row) => row.system).map((row) => row.schema)
  const databasesLabel = systemNames.length
    ? `${props.data.databases.length} databases (including ${systemNames.join(', ')})`
    : `${props.data.databases.length} databases`
  return [
    {
      label: `${props.data.engine} binary log`,
      bytes: props.data.binlog_bytes,
      color: COLORS.binlog,
    },
    { label: databasesLabel, bytes: schemaBytes, color: COLORS.databases },
    { label: `${props.data.engine} core files`, bytes: props.data.core_bytes, color: COLORS.core },
  ]
})

const sortedDatabases = computed(() => [...props.data.databases].sort((a, b) => b.bytes - a.bytes))

const showAllDatabases = ref(false)

const visibleDatabases = computed(() =>
  showAllDatabases.value
    ? sortedDatabases.value
    : sortedDatabases.value.slice(0, VISIBLE_DATABASE_COUNT),
)

const hiddenCount = computed(() =>
  showAllDatabases.value ? 0 : Math.max(sortedDatabases.value.length - VISIBLE_DATABASE_COUNT, 0),
)
</script>

<template>
  <section class="bg-surface-white p-5 border rounded-lg border-outline-gray-2 min-w-0">
    <div class="flex justify-between items-center gap-3 mb-4">
      <h3 class="flex items-center gap-2 font-medium text-ink-gray-8 text-base">
        <span class="size-4 lucide-database" />
        Database storage
      </h3>
      <div v-if="data.supported" class="text-ink-gray-6 text-sm">
        <span class="font-medium text-ink-gray-9">{{ formatBytes(data.used_bytes) }}</span>
        of {{ formatBytes(diskTotal) }} used
      </div>
    </div>

    <p v-if="!data.supported" class="text-ink-gray-5 text-sm">
      Storage breakdown is not available for the {{ data.engine }} engine.
    </p>

    <template v-else>
      <UsageMeter :parts="groupParts" :total="diskTotal" />

      <div class="flex items-center gap-2 mt-5 mb-1">
        <span class="font-medium text-ink-gray-8 text-sm">Usage per database</span>
        <Badge :label="String(data.databases.length)" theme="gray" size="sm" />
      </div>
      <dl>
        <div
          v-for="row in visibleDatabases"
          :key="row.schema"
          class="flex justify-between items-center gap-4 py-2 border-b border-outline-gray-1 last:border-b-0"
        >
          <dt class="flex items-center gap-2 min-w-0">
            <span
              class="size-3.5 text-ink-gray-5"
              :class="row.site ? 'lucide-globe' : 'lucide-database'"
            />
            <span class="text-ink-gray-7 text-sm truncate">{{ row.site || row.schema }}</span>
            <Badge v-if="row.system" label="system" theme="gray" size="sm" />
          </dt>
          <dd class="text-ink-gray-8 text-sm tabular-nums shrink-0">
            {{ formatBytes(row.bytes) }}
          </dd>
        </div>
      </dl>
      <button
        v-if="hiddenCount > 0"
        type="button"
        class="flex items-center gap-1 mt-2 text-ink-gray-6 hover:text-ink-gray-8 text-sm"
        @click="showAllDatabases = true"
      >
        <span class="size-3.5 lucide-chevron-down" />
        Show {{ hiddenCount }} more
      </button>
    </template>
  </section>
</template>
