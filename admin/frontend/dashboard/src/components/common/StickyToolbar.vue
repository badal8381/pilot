<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'

// Mirrors `top-12` above.
const STUCK_TOP = 48

const bar = ref(null)
const stuck = ref(false)
let observer

// Cropping the root to just below the pinned position means the bar stops being
// fully visible exactly when it sticks. Avoids a scroll handler, which would
// force a layout read every frame on every mounted toolbar.
onMounted(() => {
  observer = new IntersectionObserver(
    ([entry]) => (stuck.value = entry.intersectionRatio < 1),
    { rootMargin: `-${STUCK_TOP + 1}px 0px 0px 0px`, threshold: [1] },
  )
  observer.observe(bar.value)
})

onBeforeUnmount(() => observer?.disconnect())
</script>

<template>
  <!-- Pins under the shell header (`sticky top-0 min-h-12`, hence top-12).
       Negative margins bleed the background through the shell's p-3/p-4
       gutters; padding is its own since sibling gaps scroll away. -->
  <div
    ref="bar"
    :data-stuck="stuck || undefined"
    class="top-12 z-10 sticky bg-surface-base -mx-3 sm:-mx-4 px-3 sm:px-4 py-2 sm:py-3 sticky-toolbar"
  >
    <slot />
  </div>
</template>



<style scoped>
/* Lets content dissolve under the bar instead of being cut at its edge. Only
   once pinned, or it washes out the top border of whatever sits below. */
.sticky-toolbar::after {
  content: '';
  position: absolute;
  inset-inline: 0;
  top: 100%;
  height: 1rem;
  background: linear-gradient(to bottom, var(--surface-base), transparent);
  opacity: 0;
  transition: opacity 150ms var(--ease-out);
  pointer-events: none;
}

.sticky-toolbar[data-stuck]::after {
  opacity: 1;
}
</style>
