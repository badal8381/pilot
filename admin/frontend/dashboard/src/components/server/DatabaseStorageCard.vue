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

const COLORS = {
  binlog: 'amber-7',
  databases: 'violet-7',
  core: 'cyan-7',
  errorLog: 'amber-7',
  slowLog: 'cyan-7',
  binlogIndex: 'blue-7',
}

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

const extraGroupParts = computed(() => [
  {
    label: `${props.data.engine} error log`,
    bytes: props.data.error_log_bytes,
    color: COLORS.errorLog,
  },
  {
    label: `${props.data.engine} slow log`,
    bytes: props.data.slow_log_bytes,
    color: COLORS.slowLog,
  },
  {
    label: `${props.data.engine} binlog indexes`,
    bytes: props.data.binlog_index_bytes,
    color: COLORS.binlogIndex,
  },
])

const showExtraGroups = ref(false)

const visibleGroupParts = computed(() =>
  showExtraGroups.value ? [...groupParts.value, ...extraGroupParts.value] : groupParts.value,
)

const sortedDatabases = computed(() => [...props.data.databases].sort((a, b) => b.bytes - a.bytes))

const showAllDatabases = ref(false)

const VISIBLE_DATABASE_COUNT = 5

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
  <section class="p-5 min-w-0">
    <div class="flex justify-between items-center gap-3 mb-4">
      <h3 class="flex items-center gap-2 font-medium text-ink-gray-8 text-base">
        <lucide-database class="size-4" />
        Database storage
      </h3>

      <div v-if="data.supported" class="text-ink-gray-6 text-sm">
        <span class="font-medium text-ink-gray-8">{{ formatBytes(data.used_bytes) }}</span>
        of {{ formatBytes(diskTotal) }} used
      </div>
    </div>

    <p v-if="!data.supported" class="text-ink-gray-5">
      Storage breakdown is not available for the {{ data.engine }} engine.
    </p>

    <!-- data -->
    <template v-else>
      <UsageMeter :parts="groupParts" :total="diskTotal" :legend="false" />

      <dl class="mt-3">
        <div
          v-for="part in visibleGroupParts"
          :key="part.label"
          class="flex justify-between items-center gap-4 py-2 border-b border-outline-alpha-gray-1 last:border-b-0"
        >
          <dt class="flex items-center gap-2 min-w-0">
            <span
              class="rounded-full size-2 shrink-0"
              :style="{ backgroundColor: `var(--ink-${part.color})` }"
            />
            <span class="text-ink-gray-7 text-sm truncate">{{ part.label }}</span>
          </dt>
          <dd class="text-ink-gray-8 text-sm tabular-nums shrink-0">
            {{ formatBytes(part.bytes) }}
          </dd>
        </div>
      </dl>

      <button
        type="button"
        @click="showExtraGroups = !showExtraGroups"
        class="flex items-center gap-2 text-sm text-ink-gray-6 hover:text-ink-gray-8 mt-2"
      >
        <lucide-chevron-up class="size-3.5" :class="{ 'rotate-180': !showExtraGroups }" />
        <span>{{ showExtraGroups ? 'Show less' : 'Show 3 more' }}</span>
      </button>

      <div class="flex items-center gap-2 mt-4 py-3 border-t border-outline-alpha-gray-1">
        <span class="font-medium text-ink-gray-8 text-sm">Usage per database</span>
        <Badge :label="String(data.databases.length)" />
      </div>

      <dl
        v-for="row in visibleDatabases"
        :key="row.schema"
        class="flex justify-between items-center gap-4 py-2 border-b border-outline-alpha-gray-1 last:border-b-0"
      >
        <dt class="flex items-center gap-2">
          <span class="text-ink-gray-5" :class="row.site ? 'lucide-globe' : 'lucide-database'" />
          <span class="text-ink-gray-7 text-sm truncate">{{ row.site || row.schema }}</span>
          <Badge v-if="row.system" label="system" theme="gray" size="sm" />
        </dt>

        <dd class="text-ink-gray-8 text-sm tabular-nums shrink-0">
          {{ formatBytes(row.bytes) }}
        </dd>
      </dl>

      <button
        type="button"
        @click="showAllDatabases = !showAllDatabases"
        class="flex items-center gap-2 text-sm text-ink-gray-6 hover:text-ink-gray-8 mt-2"
      >
        <lucide-chevron-up class="size-3.5" :class="{ 'rotate-180': !showAllDatabases }" />

        <span>
          {{ showAllDatabases ? 'Show less' : `Show ${hiddenCount} more` }}
        </span>
      </button>
    </template>
  </section>
</template>
