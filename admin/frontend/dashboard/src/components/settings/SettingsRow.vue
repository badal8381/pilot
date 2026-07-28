<template>
  <div class="flex justify-between items-center gap-x-2.5 py-3 first:pt-0 last:pb-0">
    <div class="flex flex-col gap-1">
      <p class="font-medium text-ink-gray-8 text-sm leading-normal">{{ label }}</p>
      <p v-if="description" class="text-ink-gray-6 text-sm">{{ description }}</p>
    </div>
    <div class="ml-4 shrink-0">
      <slot />
    </div>
  </div>
</template>

<script setup>
defineProps({ label: { type: String, required: true }, description: { type: String, default: '' } })
</script>
