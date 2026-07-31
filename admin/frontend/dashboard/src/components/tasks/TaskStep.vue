<template>
  <div>
    <div
      class="flex items-center gap-3 px-2.5 py-2 rounded transition-colors"
      :class="hasOutput ? 'cursor-pointer hover:bg-surface-gray-2' : ''"
      @click="toggle"
    >
      <span class="place-items-center grid rounded size-6 shrink-0" :class="iconBg">
        <span v-if="status === 'done'" class="size-3.5 lucide-check" />
        <span v-else-if="status === 'running'" class="size-3.5 animate-spin lucide-loader-circle" />
        <span v-else-if="status === 'failed'" class="size-3.5 lucide-x" />
        <span v-else class="bg-ink-gray-3 rounded-full size-1.5" />
      </span>
      <span
        class="flex-1 min-w-0 text-base truncate"
        :class="status === 'pending' ? 'text-ink-gray-4' : 'font-medium text-ink-gray-9'"
      >
        {{ label }}
      </span>
      <!-- A fixed-width right-aligned slot, so the durations read as a column
           instead of ending wherever the label happens to leave them. -->
      <span class="w-16 text-ink-gray-5 text-sm text-right tabular-nums shrink-0">
        <template v-if="duration">{{ duration }}</template>
        <span v-else-if="status === 'running'" class="animate-pulse">running</span>
      </span>
      <!-- Hidden, not omitted: a step with no output must still reserve the
           chevron's space or it drags the duration beside it 28px to the right. -->
      <span
        class="size-4 text-ink-gray-4 transition-transform shrink-0 lucide-chevron-down"
        :class="[hasOutput ? '' : 'invisible', expanded ? 'rotate-180' : '']"
      />
    </div>
    <LogView
      v-if="expanded && hasOutput"
      class="mt-1"
      :lines="lines"
      :streaming="streaming"
    />
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import LogView from '../logs/LogView.vue'

const props = defineProps({
  label: { type: String, required: true },
  status: { type: String, default: 'pending' },
  duration: { type: String, default: null },
  lines: { type: Array, default: () => [] },
  hasOutput: { type: Boolean, default: false },
  streaming: { type: Boolean, default: false },
})

// Open while running, and open when it failed - a failed step is the reason
// the page was opened, so it should not need a click to reveal the error.
// Anything else settles closed, unless the user has toggled it by hand.
function shouldExpand(status) {
  return status === 'running' || status === 'failed'
}

const expanded = ref(shouldExpand(props.status))
let userOverridden = false

watch(
  () => props.status,
  (status) => {
    if (!userOverridden) expanded.value = shouldExpand(status)
  },
)

function toggle() {
  if (!props.hasOutput) return
  userOverridden = true
  expanded.value = !expanded.value
}

// Done is gray, not green: in a finished sequence almost every step is done, so
// green here only makes the one that failed harder to find.
const STATUS_ICON_BG = {
  done: 'bg-surface-gray-2 text-ink-gray-6',
  running: 'bg-surface-amber-2 text-ink-amber-8',
  failed: 'bg-surface-red-2 text-ink-red-8',
  pending: 'bg-surface-gray-2',
}

const iconBg = computed(() => STATUS_ICON_BG[props.status] || STATUS_ICON_BG.pending)
</script>
