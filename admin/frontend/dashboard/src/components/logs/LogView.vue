<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'

interface Props {
  lines?: any[]
  streaming?: boolean
  lineNumbers?: boolean
  wrap?: boolean
  rounded?: boolean
  fill?: boolean
  rows?: boolean
  emptyText?: string
}

const props = withDefaults(defineProps<Props>(), {
  lines: () => [],
  streaming: false,
  lineNumbers: false,
  wrap: false,
  rounded: true,
  fill: false,
  rows: false,
  emptyText: 'No output.',
})

const el = ref(null)

const scrollToBottom = () => {
  nextTick(() => {
    if (el.value) el.value.scrollTop = el.value.scrollHeight
  })
}

// Follow the tail while streaming; scrolling up pauses it, returning to the
// bottom resumes it.
const follow = ref(true)

const onScroll = ({ target }) => {
  follow.value = target.scrollHeight - target.scrollTop - target.clientHeight < 8
}

watch(
  () => props.streaming,
  (on) => {
    if (!on) return
    follow.value = true
    scrollToBottom()
  },
  { immediate: true },
)

watch(
  () => props.lines.length,
  () => {
    if (props.streaming && follow.value) scrollToBottom()
  },
)

defineExpose({ scrollToBottom })
</script>

<template>
  <div
    ref="el"
    class="bg-surface-gray-1 overflow-auto font-mono text-ink-gray-8 text-p-sm"
    :class="[wrap ? 'whitespace-pre-wrap' : 'whitespace-pre', rounded ? 'rounded-4' : '', fill ? 'flex-1 h-0' : 'max-h-[50vh]', rows ? '' : 'px-4 py-3']"
    @scroll="onScroll"
  >
    <p v-if="!lines.length" class="text-ink-gray-4" :class="rows ? 'px-4 py-3' : ''">
      {{ emptyText }}
    </p>

    <div
      v-for="(line, index) in lines"
      :key="index"
      class="flex gap-3"
      :class="rows ? 'px-2 py-1.5 sm:px-4 hover:bg-surface-gray-3' : ''"
    >
      <span
        v-if="lineNumbers"
        class="text-ink-gray-4 text-right select-none shrink-0"
        style="min-width: 1.75rem"
      >
        {{ index + 1 }}
      </span>

      <span class="flex-1" :class="wrap ? 'break-words' : ''" v-html="line || '&nbsp;'" />
    </div>

    <span
      v-if="streaming"
      class="inline-block animate-pulse"
      :class="rows ? 'px-3 py-1 sm:px-4' : ''"
      >█</span
    >
  </div>
</template>
