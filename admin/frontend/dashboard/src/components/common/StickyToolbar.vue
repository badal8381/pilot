<template>
  <!-- Pins under the shell header (`sticky top-0 min-h-12`, hence top-12).
       Negative margins bleed the background through the shell's p-3/p-4
       gutters; padding is its own since sibling gaps scroll away. `disabled`
       is for toolbars teleported into the header, where a sticky opaque bar
       would paint over the header's own actions. -->
  <div
    :class="
      disabled
        ? ''
        : 'top-12 z-10 sticky bg-surface-base -mx-3 sm:-mx-4 px-3 sm:px-4 py-2 sm:py-3'
    "
  >
    <slot />
  </div>
</template>

<script setup>
defineProps({ disabled: { type: Boolean, default: false } })
</script>
