<template>
  <div
    class="grid size-10 shrink-0 place-items-center overflow-hidden rounded-lg"
    :style="logoUrl ? {} : { background: hashColor(name) }"
  >
    <img
      v-if="logoUrl"
      :src="logoUrl"
      :alt="label || name"
      class="size-full object-contain"
      @error="onError"
    />
    <span v-else class="font-bold text-white leading-none" :class="initialClass">
      {{ initial }}
    </span>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import {
  FRAPPE_LOGO_URL,
  isFrappeFramework,
  useAppRegistry,
} from '@/composables/apps/useAppRegistry'

const props = defineProps({
  name: { type: String, required: true },
  label: { type: String, default: '' },
  logo: { type: String, default: '' },
  initialClass: { type: String, default: 'text-sm' },
})

const { logoMap, hashColor } = useAppRegistry()
const hasError = ref(false)

const isFrappe = computed(() => isFrappeFramework(props.name))

const logoUrl = computed(() => {
  if (isFrappe.value) return FRAPPE_LOGO_URL
  if (hasError.value) return null
  return props.logo || logoMap.value[props.name]
})
const initial = computed(() => (props.label || props.name)[0]?.toUpperCase() || '')

function onError() {
  if (!isFrappe.value) hasError.value = true
}
</script>
