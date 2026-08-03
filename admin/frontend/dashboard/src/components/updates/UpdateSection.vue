<template>
  <details
    :open="open"
    class="group/section rounded-lg border border-outline-gray-2 p-1"
    @toggle="$emit('update:open', $event.target.open)"
  >
    <summary
      class="flex items-center justify-between px-2.5 py-2 rounded transition-colors cursor-pointer select-none hover:bg-surface-gray-1"
    >
      <div class="flex items-center gap-2">
        <span class="size-4 text-ink-gray-5 shrink-0" :class="icon" />
        <h2 class="text-base font-medium text-ink-gray-8">{{ title }}</h2>
      </div>
      <span
        class="size-4 text-ink-gray-5 transition-transform group-open/section:rotate-180 lucide-chevron-down"
      />
    </summary>

    <div><slot /></div>
  </details>
</template>

<script setup>
defineProps({
  icon: { type: String, required: true },
  title: { type: String, required: true },
  open: { type: Boolean, default: true },
})

defineEmits(['update:open'])
</script>
