<template>
  <div class="top-12 z-10 sticky bg-surface-base">
    <slot />
  </div>
</template>

<style scoped>
div::after {
  content: "";
  background: linear-gradient(to bottom, var(--surface-base), transparent);
  @apply top-full absolute inset-x-0 h-4 pointer-events-none;
}
</style>
