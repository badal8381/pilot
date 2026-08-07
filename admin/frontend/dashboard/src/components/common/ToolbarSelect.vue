<template>
  <Dropdown :options="options" placement="bottom-start">
    <template #default="{ open }">
      <Button v-bind="$attrs" variant="outline" :size="isMobile ? 'md' : 'sm'" :active="open">
        <template v-if="$slots.prefix" #prefix><slot name="prefix" /></template>
        <template #suffix><span class="size-4 lucide-chevron-down" /></template>
        <slot />
      </Button>
    </template>
  </Dropdown>
</template>

<script setup>
import { Button, Dropdown } from 'frappe-ui'
import { useIsMobile } from '@/composables/common/useIsMobile'

// inheritAttrs off so a caller's `class` styles the trigger, not the Dropdown.
defineOptions({ inheritAttrs: false })
defineProps({ options: { type: Array, required: true } })

const isMobile = useIsMobile()
</script>
