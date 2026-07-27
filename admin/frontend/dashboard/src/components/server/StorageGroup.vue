<script setup lang="ts">
import { computed, ref } from 'vue'
import { logoColor } from '@/composables/apps/useMarketplace'
import type { StorageItem } from '@/types/storage'
import { formatBytes } from '@/utils/format'

interface Props {
  label: string
  icon: string
  color: string
  bytes: number
  items?: StorageItem[]
  badge?: boolean
}

const props = withDefaults(defineProps<Props>(), { items: () => [], badge: false })

const hasItems = computed(() => props.items.length > 0)
const expanded = ref(false)
</script>

<template>
  <div class="py-1">
    <button
      type="button"
      class="flex justify-between items-center gap-4 py-2 w-full text-left"
      :class="{ 'cursor-default': !hasItems }"
      @click="hasItems && (expanded = !expanded)"
    >
      <span class="flex items-center gap-2 min-w-0">
        <span class="rounded-full size-2 shrink-0" :style="{ backgroundColor: color }" />
        <span class="text-ink-gray-7 text-sm truncate">{{ label }}</span>
        <span
          v-if="hasItems"
          class="size-3.5 text-ink-gray-5"
          :class="[expanded ? 'lucide-chevron-up' : 'lucide-chevron-down']"
        />
      </span>
      <span class="text-ink-gray-8 text-sm tabular-nums shrink-0">{{ formatBytes(bytes) }}</span>
    </button>

    <div v-if="hasItems && expanded" class="pl-4">
      <div
        v-for="item in items"
        :key="item.name"
        class="flex justify-between items-center gap-4 py-1.5"
      >
        <span class="flex items-center gap-2 min-w-0">
          <span
            v-if="badge"
            class="grid place-items-center rounded size-4 font-bold text-[9px] text-white shrink-0"
            :style="{ backgroundColor: logoColor(item.name) }"
          >
            {{ item.name[0]?.toUpperCase() }}
          </span>
          <span v-else class="size-3.5 text-ink-gray-4 shrink-0" :class="icon" />
          <span class="text-ink-gray-6 text-sm truncate">{{ item.name }}</span>
        </span>
        <span class="text-ink-gray-7 text-sm tabular-nums shrink-0"
          >{{ formatBytes(item.bytes) }}</span
        >
      </div>
    </div>
  </div>
</template>
