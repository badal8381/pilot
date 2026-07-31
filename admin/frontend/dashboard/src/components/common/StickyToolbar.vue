<template>
  <!-- Pins a page's filter/search row under the app header while the list
       scrolls, at both breakpoints - the shell header is `sticky top-0 min-h-12`
       in the mobile and desktop branches alike, so top-12 lands flush under it
       either way and the two opaque bars stack without a seam.

       The negative margin lets the background bleed through the shell's own
       padding (p-3 on mobile, p-4 on desktop) so rows do not show in the gutters
       as they pass underneath. pb keeps the list from touching the bar once it
       starts sliding under; the page's own top margin is on a sibling, so it
       scrolls away and cannot do that job. -->
  <div
    class="top-12 z-10 sticky bg-surface-base -mx-3 sm:-mx-4 px-3 sm:px-4 pt-1 sm:pt-0 pb-2"
  >
    <slot />
  </div>
</template>
