<template>
  <div class="flex items-center gap-3">
    <Skeleton class="rounded-[10px] size-9 shrink-0" />

    <div class="flex-1 py-2 min-w-0">
      <!-- The wrappers carry the real card's line-box heights (title 16px,
           description 20px) so swapping in the loaded card shifts nothing; the
           bars inside stay thinner than the box, the way text does. -->
      <div class="flex items-center h-4">
        <Skeleton class="rounded h-3" :class="titleWidth" />
      </div>
      <div class="flex items-center mt-0.5 h-5">
        <Skeleton class="rounded h-2.5" :class="descriptionWidth" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Skeleton } from 'frappe-ui'

const props = defineProps({
  // Cycles the bar widths so a grid of these does not read as a pattern of
  // identical bars. Index-based rather than random, so it stays stable across
  // re-renders.
  index: { type: Number, default: 0 },
})

const TITLE_WIDTHS = ['w-24', 'w-32', 'w-20', 'w-28']
const DESCRIPTION_WIDTHS = ['w-48', 'w-36', 'w-52', 'w-44']

const titleWidth = computed(() => TITLE_WIDTHS[props.index % TITLE_WIDTHS.length])
const descriptionWidth = computed(
  () => DESCRIPTION_WIDTHS[props.index % DESCRIPTION_WIDTHS.length],
)
</script>
