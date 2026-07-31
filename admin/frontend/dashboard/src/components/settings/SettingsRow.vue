<template>
  <div class="flex justify-between items-center gap-x-2.5 py-3 first:pt-0 last:pb-0">
    <div class="flex flex-col gap-1">
      <!-- 14/13, matching frappe-ui's own InputLabel (text-base) and
           InputDescription (text-p-sm): a Switch row rendered by the library sits
           directly above these, so anything else reads as two type scales in one
           list. The description is stacked copy that wraps, hence text-p-sm. -->
      <p class="font-medium text-ink-gray-8 text-base">{{ label }}</p>
      <p v-if="description" class="text-ink-gray-6 text-p-sm">{{ description }}</p>
    </div>
    <div class="ml-4 shrink-0">
      <slot />
    </div>
  </div>
</template>

<script setup>
defineProps({ label: { type: String, required: true }, description: { type: String, default: '' } })
</script>
