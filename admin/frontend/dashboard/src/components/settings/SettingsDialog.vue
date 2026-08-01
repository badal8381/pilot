<template>
  <Dialog v-model="open" bare size="5xl">
    <template #default="{ close }">
      <!-- Full viewport height, less the chrome the Dialog puts around the panel
           itself: the overlay's scroll wrapper adds py-4 and DialogContent adds
           my-8, so a literal 100vh overflows by exactly 96px and makes the
           overlay scroll with the bottom corners off-screen. -->
      <div class="relative flex sm:h-[calc(100vh-6rem)] max-h-[calc(100vh-6rem)]">
        <!-- Sizing, padding and tokens taken from frappe-ui's own SettingsDialog
             (SettingsSidebar: bg-surface-sidebar, p-2, 220px, outline-gray-1).
             surface-sidebar is theme-aware by design - a light gray against the
             panel in light mode, transparent in dark, where the panel is already
             raised off the backdrop. -->
        <div
          class="flex-col bg-surface-sidebar p-2 sm:border-r border-outline-gray-1 w-full sm:w-[220px] shrink-0"
          :class="activeSection ? 'hidden sm:flex' : 'flex'"
        >
          <h3
            class="mb-1 p-2 pb-3 border-b sm:border-b-0 border-outline-gray-1 font-semibold text-ink-gray-9 text-base"
          >
            Settings
          </h3>
          <Button
            v-if="!activeSection"
            class="sm:hidden top-3 right-3 absolute"
            variant="ghost"
            icon="lucide-x"
            label="Close settings"
            tooltip="Close"
            @click="close"
          />
          <div class="flex flex-col gap-2 sm:gap-0.5 pt-2 sm:pt-0">
            <Button
              v-for="section in sections"
              :key="section.id"
              :variant="isMobile ? 'subtle' : 'ghost'"
              :size="isMobile ? 'md' : 'sm'"
              class="!justify-start border sm:border-0 w-full"
              :class="
                currentSection === section.id
                  ? 'sm:!bg-surface-elevation-3 sm:!shadow-sm sm:!text-ink-gray-9 !text-ink-gray-6'
                  : '!text-ink-gray-6'
              "
              @click="guarded(() => (activeSection = section.id))"
            >
              <template #prefix>
                <span :class="section.icon" class="size-4"></span>
              </template>
              {{ section.label }}
            </Button>
          </div>
        </div>
        <!-- px-[4.4rem] pt-10 pb-16 is frappe-ui's SettingsHeader/SettingsBody
             padding. Kept off below sm, where 70px a side would leave a column
             barely wider than the words in it. -->
        <div
          class="flex-col flex-1 px-6 sm:px-[4.4rem] pt-6 sm:pt-10 pb-10 sm:pb-16 overflow-y-auto"
          :class="activeSection ? 'flex' : 'hidden sm:flex'"
        >
          <div class="flex justify-between items-center pb-4">
            <div class="flex items-center gap-2">
              <Button
                v-if="subSection || sessionJti || activeSection"
                :class="{ 'sm:hidden': !subSection && !sessionJti }"
                class="-ml-2"
                variant="ghost"
                icon="lucide-arrow-left"
                label="Back"
                tooltip="Back"
                @click="goBack"
              />
              <h3 class="font-semibold text-ink-gray-9 text-lg">{{ headerTitle }}</h3>
            </div>
            <div id="settings-header-actions" class="contents"></div>
          </div>
          <General v-if="currentSection === 'general'" v-model:open-section="guardedSubSection" />
          <Security
            v-else-if="currentSection === 'security'"
            v-model:open-section="guardedSubSection"
          />
          <Sessions
            v-else-if="currentSection === 'sessions'"
            v-model:nested-view="nestedView"
            v-model:jti="sessionJti"
          />
          <SystemInfo v-else-if="currentSection === 'system-info'" />
        </div>
      </div>
    </template>
  </Dialog>

  <Dialog v-model="showDiscard" :options="{ title: 'Unsaved changes', size: 'sm' }">
    <template #body-content>
      <p class="text-ink-gray-7 text-p-base">
        You have changes here that have not been saved. Leaving loses them.
      </p>
      <div class="flex justify-end gap-2 mt-4">
        <Button variant="subtle" @click="showDiscard = false">Keep editing</Button>
        <Button variant="solid" theme="red" @click="discardAndGo">Discard</Button>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Dialog, Button } from 'frappe-ui'
import { hasUnsavedChanges } from '@/composables/common/useUnsavedChanges'
import General from '@/components/settings/General.vue'
import Security from '@/components/settings/Security.vue'
import Sessions from '@/components/settings/Sessions.vue'
import SystemInfo from '@/components/settings/SystemInfo.vue'
import { useIsMobile } from '@/composables/common/useIsMobile'
import { GENERAL_SECTIONS, SECURITY_SECTIONS } from '@/components/settings/sections'

const openModel = defineModel()

const isMobile = useIsMobile()
const route = useRoute()
const router = useRouter()

// Every way out of a panel funnels through here: the sidebar, the back arrow,
// opening a sub-section, and dismissing the dialog. Moving between panels is a
// route *param* change on the one Settings record, so a component-level
// onBeforeRouteLeave never sees it - the gate has to sit at the call sites.
//
// When nothing is dirty this runs the action straight through, so the ordinary
// case is unchanged.
const showDiscard = ref(false)
let pendingNav = null
function guarded(action) {
  if (!hasUnsavedChanges()) return action()
  pendingNav = action
  showDiscard.value = true
}
function discardAndGo() {
  // Taken before the dialog closes: closing trips the watcher below, and relying
  // on that landing after this line would make the whole thing depend on watcher
  // flush timing.
  const action = pendingNav
  pendingNav = null
  showDiscard.value = false
  action?.()
}
watch(showDiscard, (shown) => {
  if (!shown) pendingNav = null
})

// Closing is guarded; opening never is.
const open = computed({
  get: () => openModel.value,
  set: (value) => {
    if (value) openModel.value = true
    else guarded(() => (openModel.value = false))
  },
})

const sections = computed(() => [
  { id: 'general', label: 'General', icon: 'lucide-settings' },
  { id: 'security', label: 'Security', icon: 'lucide-shield' },
  { id: 'sessions', label: 'Sessions', icon: 'lucide-monitor' },
  { id: 'system-info', label: 'System Info', icon: 'lucide-info' },
])
// Both section and sub-section are routed (deep-linkable, back button
// closes/steps back). Sub-section options come from a shared registry so
// this dialog can resolve a route id without General/Security exposing one.
const activeSection = computed({
  get: () => route.params.section || null,
  set: (id) => router.push(id ? { name: 'Settings', params: { section: id } } : { name: 'Settings' }),
})
const currentSection = computed(() => activeSection.value ?? sections.value[0].id)
const activeSectionLabel = computed(
  () => sections.value.find((s) => s.id === currentSection.value)?.label,
)

const subSectionOptions = computed(() => {
  if (currentSection.value === 'general') return GENERAL_SECTIONS
  if (currentSection.value === 'security') return SECURITY_SECTIONS
  return []
})
const subSection = computed({
  get: () => subSectionOptions.value.find((s) => s.id === route.params.subSection) ?? null,
  set: (section) =>
    router.push({
      name: 'Settings',
      params: { section: currentSection.value, subSection: section?.id },
    }),
})
// What General and Security bind to. Guarded here rather than in `subSection`
// itself so goBack() and discardAndGo() can still move without re-asking.
const guardedSubSection = computed({
  get: () => subSection.value,
  set: (section) => guarded(() => (subSection.value = section)),
})

// Sessions doesn't use the sub-section registry (its "sub-pages" are individual,
// dynamically-fetched sessions, not a fixed list) - the same :subSection route slot
// carries a jti instead, so a specific session's activity view is a real deep link.
const sessionJti = computed({
  get: () => (currentSection.value === 'sessions' ? route.params.subSection || null : null),
  set: (jti) =>
    router.push({ name: 'Settings', params: { section: 'sessions', subSection: jti || undefined } }),
})

// Sessions reports the human title (an IP, once it resolves the jti) since the route
// only carries the raw id - reset whenever the visible section changes so re-entering
// the tab later never inherits a stale title.
const nestedView = ref(null)
watch(currentSection, () => (nestedView.value = null))

const headerTitle = computed(() => {
  if (sessionJti.value) return nestedView.value?.title ?? sessionJti.value
  return subSection.value?.label ?? activeSectionLabel.value
})

function goBack() {
  guarded(() => {
    if (sessionJti.value) sessionJti.value = null
    else if (subSection.value) subSection.value = null
    else activeSection.value = null
  })
}
</script>
