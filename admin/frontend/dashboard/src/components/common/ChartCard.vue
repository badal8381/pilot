<script setup lang="ts">
interface Props {
  title?: string
  subtitle?: string
}

defineProps<Props>()
</script>

<template>
  <div
    class="flex flex-col bg-surface-base pt-3 pb-2 px-4 border rounded-4 border-outline-gray-2 overflow-hidden"
  >
    <div class="flex justify-between items-baseline gap-2">
      <h3 class="font-medium text-ink-gray-8 text-base">{{ title }}</h3>
    </div>

    <slot />
  </div>
</template>
