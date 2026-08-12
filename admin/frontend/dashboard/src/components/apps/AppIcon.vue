<template>
  <Avatar
    class="[&_img]:object-contain"
    :image="logoUrl"
    :label="label || name"
    :size="size"
    :theme="hashTheme(name)"
    shape="square"
  />
</template>

<script setup>
import { computed } from 'vue'
import { Avatar } from 'frappe-ui'
import {
  FRAPPE_LOGO_URL,
  hashTheme,
  isFrappeFramework,
  useAppRegistry,
} from '@/composables/apps/useAppRegistry'

const props = defineProps({
  name: { type: String, required: true },
  label: { type: String, default: '' },
  logo: { type: String, default: '' },
  size: { type: String, default: '2xl' },
})

const { logoMap } = useAppRegistry()

const logoUrl = computed(() => {
  if (isFrappeFramework(props.name)) return FRAPPE_LOGO_URL
  return props.logo || logoMap.value[props.name]
})
</script>
