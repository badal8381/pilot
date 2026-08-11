<template>
  <StickyToolbar>
    <div class="flex sm:flex-row flex-col gap-2">
      <FormControl
        v-model="searchModel"
        class="flex-1"
        type="text"
        placeholder="Search for any app"
        :size="isMobile ? 'md' : 'sm'"
      >
        <template #prefix>
          <LucideSearch class="size-4 text-ink-gray-5" />
        </template>
      </FormControl>

      <!-- Width-bound row: flex-1 must resolve against the row, not content. -->
      <div class="flex gap-2 w-full sm:w-auto">
        <div class="flex-1 sm:flex-none min-w-0">
          <Dropdown :options="worksWithMenu" placement="bottom-end">
            <template #default="{ open }">
              <Button
                class="[&>.truncate]:flex-1 [&>.truncate]:text-left text-base w-full sm:w-auto"
                :size="isMobile ? 'md' : 'sm'"
                :active="open"
              >
                <template #suffix><span class="size-4 shrink-0 lucide-chevron-down" /></template>
                {{ worksWithLabel }}
              </Button>
            </template>
          </Dropdown>
        </div>

        <Button
          variant="subtle"
          class="text-base"
          :size="isMobile ? 'md' : 'sm'"
          @click="$emit('add-from-github')"
        >
          <template #prefix><GithubMark class="size-4" /></template>
          Import app
        </Button>
      </div>
    </div>

    <!-- Scrolls rather than clips: TabButtons' rail is overflow-hidden and does not wrap. -->
    <div class="mt-3 overflow-x-auto">
      <TabButtons
        v-model="pillModel"
        :options="pillOptions"
        variant="ghost"
        :size="isMobile ? 'md' : 'sm'"
      />
    </div>
  </StickyToolbar>
</template>

<script setup>
import { computed, h } from 'vue'
import { Button, Dropdown, FormControl, TabButtons } from 'frappe-ui'
import AppIcon from '@/components/apps/AppIcon.vue'
import StickyToolbar from '@/components/common/StickyToolbar.vue'
import LucideSearch from '~icons/lucide/search'
import GithubMark from '@/components/icons/GithubMark.vue'
import { useIsMobile } from '@/composables/common/useIsMobile'
import { PILLS } from '@/utils/marketplaceCategories'

const isMobile = useIsMobile()

const props = defineProps({
  worksWithOptions: { type: Array, default: () => [] },
})
defineEmits(['add-from-github'])

const searchModel = defineModel('search', { type: String })
const pillModel = defineModel('pill', { type: String })
const worksWithModel = defineModel('worksWith', { type: String })

const pillOptions = PILLS.map((pill) => ({ label: pill, value: pill }))

const worksWithMenu = computed(() => [
  {
    label: 'Any app',
    icon: () => h('span', { class: 'size-4 text-ink-gray-6 lucide-layout-grid' }),
    onClick: () => (worksWithModel.value = ''),
  },
  ...props.worksWithOptions.map((option) => ({
    label: option.title,
    icon: () =>
      h(AppIcon, { name: option.name, label: option.title, logo: option.logo_url, size: 'xs' }),
    onClick: () => (worksWithModel.value = option.name),
  })),
])

const worksWithLabel = computed(() => {
  const selected = props.worksWithOptions.find((option) => option.name === worksWithModel.value)
  return selected ? selected.title : 'Works with'
})
</script>
