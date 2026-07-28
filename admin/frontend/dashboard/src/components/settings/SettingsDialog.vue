<template>
  <Dialog v-model="open" bare size="4xl">
    <template #default="{ close }">
      <div class="relative flex sm:h-[70vh] max-h-[85vh]">
        <div
          class="flex-col p-4 sm:border-r border-outline-gray-2 w-full sm:w-52 shrink-0"
          :class="activeSection ? 'hidden sm:flex' : 'flex'"
        >
          <h3
            class="mb-1 p-2 pb-3 border-b sm:border-b-0 border-outline-gray-2 font-semibold text-ink-gray-9 text-base"
          >
            Settings
          </h3>
          <Button
            v-if="!activeSection"
            class="sm:hidden top-3 right-3 absolute"
            variant="ghost"
            icon="lucide-x"
            @click="close"
          />
          <div class="flex flex-col gap-2 sm:gap-0.5 pt-2 sm:pt-0">
            <Button
              v-for="section in sections"
              :key="section.id"
              :variant="isMobile ? 'subtle' : 'ghost'"
              :size="isMobile ? 'md' : 'sm'"
              class="!justify-start border sm:border-0 w-full"
              :class="currentSection === section.id ? 'sm:!bg-surface-gray-3 sm:!text-ink-gray-9 !text-ink-gray-6' : '!text-ink-gray-6'"
              @click="activeSection = section.id"
            >
              <template #prefix>
                <span :class="section.icon" class="size-4"></span>
              </template>
              {{ section.label }}
            </Button>
          </div>
        </div>
        <div
          class="flex-col flex-1 p-6 overflow-y-auto"
          :class="activeSection ? 'flex' : 'hidden sm:flex'"
        >
          <div class="flex justify-between items-center pb-4">
            <div class="flex items-center gap-2">
              <Button
                v-if="subSection || sessionJti || activeSection"
                :class="{ 'sm:hidden': !subSection && !sessionJti }"
                class="-ml-2"
                variant="subtle"
                icon="lucide-arrow-left"
                @click="goBack"
              />
              <h3 class="font-semibold text-ink-gray-9 text-lg">{{ headerTitle }}</h3>
            </div>
            <div id="settings-header-actions" class="contents"></div>
          </div>
          <General v-if="currentSection === 'general'" v-model:open-section="subSection" />
          <Security v-else-if="currentSection === 'security'" v-model:open-section="subSection" />
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
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Dialog, Button } from 'frappe-ui'
import General from '@/components/settings/General.vue'
import Security from '@/components/settings/Security.vue'
import Sessions from '@/components/settings/Sessions.vue'
import SystemInfo from '@/components/settings/SystemInfo.vue'
import { useIsMobile } from '@/composables/common/useIsMobile'
import { GENERAL_SECTIONS, SECURITY_SECTIONS } from '@/components/settings/sections'

const open = defineModel()

const isMobile = useIsMobile()
const route = useRoute()
const router = useRouter()

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
  if (sessionJti.value) sessionJti.value = null
  else if (subSection.value) subSection.value = null
  else activeSection.value = null
}
</script>
