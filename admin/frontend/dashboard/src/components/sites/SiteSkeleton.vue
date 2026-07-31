<template>
  <!-- The card's own classes, so the outline and spacing are already in place
       before the sites land and nothing reflows around them. -->
  <div
    class="flex items-center gap-3 bg-surface-base p-2 sm:px-3 sm:py-2 border rounded-lg border-outline-gray-2"
  >
    <Skeleton class="rounded size-8 shrink-0" />
    <div class="flex-1 min-w-0">
      <!-- 24px and 20px line boxes, matching the real card's two rows. -->
      <div class="flex items-center gap-1.5 h-6">
        <Skeleton class="rounded h-3.5" :class="nameWidth" />
        <Skeleton class="rounded-full w-12 h-4 shrink-0" />
      </div>
      <div class="flex items-center h-5">
        <Skeleton class="rounded w-12 h-2.5" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Skeleton } from 'frappe-ui'

const props = defineProps({
  // Cycles the name width so a page of these does not read as a pattern of
  // identical bars. Index-based rather than random, so it stays stable across
  // re-renders.
  index: { type: Number, default: 0 },
})

const NAME_WIDTHS = ['w-32', 'w-24', 'w-40', 'w-28']
const nameWidth = computed(() => NAME_WIDTHS[props.index % NAME_WIDTHS.length])
</script>
