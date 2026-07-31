<template>
  <div
    class="flex flex-col bg-surface-base pt-3 pb-1 border rounded-lg border-outline-gray-2 overflow-hidden"
  >
    <!-- No rule under the title and no gap of its own: the card's border
         already separates it from the page, and the chart below is
         unmistakably a chart. -->
    <div class="flex justify-between items-baseline gap-2 px-4">
      <h3 class="font-medium text-ink-gray-8 text-base">{{ title }}</h3>
    </div>
    <slot />
  </div>
</template>

<script setup>
defineProps({ title: String, subtitle: String })
</script>
