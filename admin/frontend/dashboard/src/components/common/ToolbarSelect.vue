<script setup lang="ts">
import { Button, Dropdown } from 'frappe-ui'

import { useIsMobile } from '@/composables/common/useIsMobile'

// inheritAttrs off so a caller's `class` styles the trigger, not the Dropdown.
defineOptions({ inheritAttrs: false })
interface Props {
  options: any[]
}

defineProps<Props>()

const isMobile = useIsMobile()
</script>

<template>
  <Dropdown :options="options">
    <template #default="{ open }">
      <Button v-bind="$attrs" variant="outline" :size="isMobile ? 'md' : 'sm'" :active="open">
        <template v-if="$slots.prefix" #prefix><slot name="prefix" /></template>
        <template #suffix><span class="size-4 lucide-chevron-down" /></template>
        <slot />
      </Button>
    </template>
  </Dropdown>
</template>
