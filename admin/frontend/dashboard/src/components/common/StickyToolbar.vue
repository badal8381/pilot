<template>
  <!-- Pins a page's filter/search row under the app header while the list
       scrolls, at both breakpoints - the shell header is `sticky top-0 min-h-12`
       in the mobile and desktop branches alike, so top-12 lands flush under it
       either way and the two opaque bars stack without a seam.

       The negative margin lets the background bleed through the shell's own
       padding (p-3 on mobile, p-4 on desktop) so rows do not show in the gutters
       as they pass underneath.

       The padding is symmetric because the bar has to carry its own breathing
       room in both directions once it pins: the shell's gutter above it and the
       list's top margin below it are both on siblings, so both scroll away and
       the controls end up flush against the header on one side and the first
       row on the other.

       `disabled` is for the toolbars that get teleported into the header on one
       breakpoint and rendered in place on the other: inside the header there is
       nothing to pin against, and the opaque background plus negative margins
       paint straight over whatever else the header is holding. The root stays
       either way, so a class passed by the caller lands in the same place. -->
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
