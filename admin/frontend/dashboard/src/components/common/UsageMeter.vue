<script setup lang="ts">
import { computed } from 'vue'
import { formatBytes } from '@/utils/format'

interface UsagePart {
  label: string
  bytes: number | null
  color: string
}

interface Props {
  parts: UsagePart[]
  total?: number | null
  legend?: boolean
}

const props = withDefaults(defineProps<Props>(), { total: null, legend: true })

const formattedParts = computed(() =>
  props.parts.map((part) => ({
    ...part,
    text: part.bytes == null ? '—' : formatBytes(part.bytes),
  })),
)

const parts = computed(() => formattedParts.value)

const barParts = computed(() => {
  const known = formattedParts.value.filter((part) => (part.bytes ?? 0) > 0)
  const denominator = props.total ?? known.reduce((sum, part) => sum + (part.bytes ?? 0), 0)
  if (!denominator) return []
  return known.map((part) => ({ ...part, percent: ((part.bytes ?? 0) / denominator) * 100 }))
})
</script>

<template>
  <div>
    <div class="flex bg-surface-gray-2 rounded-md w-full h-7 overflow-hidden">
      <div
        v-for="part in barParts"
        :key="part.label"
        :style="{ width: `${part.percent}%`, backgroundColor: part.color }"
        :title="`${part.label}: ${part.text}`"
      />
    </div>

    <dl v-if="legend" class="mt-3">
      <div
        v-for="part in parts"
        :key="part.label"
        class="flex justify-between items-center gap-4 py-2.5 border-b border-outline-gray-1 last:border-b-0"
      >
        <dt class="flex items-center gap-2 min-w-0">
          <span class="rounded-full size-2 shrink-0" :style="{ backgroundColor: part.color }" />
          <span class="text-ink-gray-7 text-sm truncate">{{ part.label }}</span>
        </dt>
        <dd class="text-ink-gray-8 text-sm tabular-nums">{{ part.text }}</dd>
      </div>
    </dl>
  </div>
</template>
