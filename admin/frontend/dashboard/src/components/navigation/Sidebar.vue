<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Sidebar, SidebarHeader, SidebarLabel, SidebarItem, SidebarCollapseToggle } from 'frappe-ui'
import { sidebarSections } from './list'
import { useAppMenu } from './useAppMenu'
import PilotLogo from '@/components/icons/Pilot.vue'
import NotificationsPanel from '@/components/notifications/NotificationsPanel.vue'
import { openSearch } from '@/composables/common/useSearch'

const props = defineProps({
  isMobile: { type: Boolean, default: false },
})

const route = useRoute()
const { menuItems, session } = useAppMenu()

// Items can gate themselves behind a session flag (e.g. `developerMode`);
// sections left with no visible items are dropped entirely.
const visibleSections = computed(() =>
  sidebarSections
    .map((section) => ({
      ...section,
      items: section.items.filter((item) => !item.flag || session[item.flag]),
    }))
    .filter((section) => section.items.length),
)

// Prefix match, not just exact: a site's detail page (/sites/foo/general)
// should still light up the "Sites" item, not just the bare list page.
const isActive = (to) => route.path === to || route.path.startsWith(`${to}/`)
</script>

<template>
  <Sidebar
    :disable-collapse="isMobile"
    class="border-r dark:border-outline-gray-2"
    :class="isMobile ? '!w-full !border-r-0 mobile-sidebar bg-transparent' : ''"
  >
    <SidebarHeader
      v-if="!isMobile"
      title="Pilot"
      :subtitle="session.benchName"
      :menu-items="menuItems"
      :logo="PilotLogo"
    />

    <nav class="flex-1 overflow-y-auto px-2 pt-2">
      <SidebarItem icon="lucide-search" suffix="⌘ K" class="mb-0.5 text-sm" @click="openSearch">
        Search
      </SidebarItem>

      <NotificationsPanel />

      <template v-for="section in visibleSections" :key="section.label || 'main'">
        <!-- `divider`: collapsed, the section name has no room, so the label
             becomes a rule and the groups stay separated instead of running
             into one column of icons. -->
        <SidebarLabel v-if="section.label" divider class="mt-2">
          {{ section.label }}
        </SidebarLabel>
        <SidebarItem
          v-for="item in section.items"
          :key="item.to"
          :icon="item.icon"
          :to="item.to"
          :active="isActive(item.to)"
          class="mb-0.5 text-sm"
        >
          {{ item.label }}

          <lucide-chevron-right v-if="isMobile" class="size-4 text-ink-gray-4 ml-auto mr-1" />
        </SidebarItem>
      </template>
    </nav>

    <SidebarCollapseToggle class="mt-auto mx-2 mb-2" />
  </Sidebar>
</template>

<style scoped>
/* Holds the rail's icons still and on centre while it collapses; frappe-ui
   1.0.0-beta.25 re-aligns them mid-animation instead. Drop once
   frappe/frappe-ui#907 lands. */
[data-slot='sidebar'] :deep([data-slot='sidebar-item'] > :where(a, button)) {
  justify-content: flex-start;
  padding-left: 0.5rem;
}

[data-slot='sidebar']
  :deep([data-slot='sidebar-item'] > :where(a, button) > span:first-child) {
  /* Undo the collapsed `size-7` box - the row is already the hit target. */
  width: auto;
  height: auto;
}

[data-slot='sidebar'] :deep(> div:first-child) {
  justify-content: flex-start;
  padding-left: 0.25rem;
}
</style>
