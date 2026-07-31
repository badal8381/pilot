<template>
  <div
    class="flex flex-col items-center gap-4 px-6 py-12 text-center"
    :class="bordered ? 'border border-outline-gray-2 border-dashed rounded-xl' : ''"
  >
    <span
      v-if="icon"
      class="place-items-center grid bg-surface-gray-2 rounded-lg size-10 text-ink-gray-5 shrink-0"
    >
      <span class="size-5" :class="icon" />
    </span>
    <div>
      <p class="font-medium text-ink-gray-7 text-base">{{ title }}</p>
      <p v-if="description" class="mt-1 max-w-xs text-ink-gray-5 text-p-sm">{{ description }}</p>
    </div>
    <slot />
  </div>
</template>

<script setup>
// The one empty state for panels and pages: dashed box, icon tile, title,
// optional description and action. Inline "no results" text inside tables and
// charts stays as it is - a box that size reads as a broken layout.
defineProps({
  icon: { type: String, default: '' },
  title: { type: String, required: true },
  description: { type: String, default: '' },
  // Off when the state already sits inside a bordered panel, so the dashed box
  // is not drawn inside another box.
  bordered: { type: Boolean, default: true },
})
</script>
