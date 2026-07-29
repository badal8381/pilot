<template>
  <component
    :is="interactive ? 'button' : 'div'"
    :type="interactive ? 'button' : null"
    class="flex items-center gap-3 p-3 border rounded-lg min-w-0 text-left"
    :class="[stateClass, interactive && 'transition duration-150 ease-[var(--ease-out)] active:scale-[0.98]']"
    :disabled="interactive && disabled ? true : null"
  >
    <span class="place-items-center grid bg-surface-gray-2 rounded-md size-8 shrink-0">
      <span class="size-4" :class="[icon, checked ? 'text-ink-green-6' : 'text-ink-gray-6']" />
    </span>
    <div class="flex-1 min-w-0">
      <p class="font-medium text-ink-gray-8 text-sm truncate">{{ label }}</p>
      <p v-if="subtitle" class="text-ink-gray-5 text-p-sm truncate">{{ subtitle }}</p>
    </div>
    <slot name="suffix" />
  </component>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  label: { type: String, required: true },
  subtitle: { type: String, default: '' },
  icon: { type: String, default: 'lucide-globe' },
  checked: { type: Boolean, default: false },
  selected: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  interactive: { type: Boolean, default: true },
})

const stateClass = computed(() => {
  if (props.disabled) return 'border-outline-gray-2 opacity-60 cursor-not-allowed'
  if (props.selected) return 'border-outline-gray-4 bg-surface-gray-1'
  return props.interactive ? 'border-outline-gray-2 hover:bg-surface-gray-1' : 'border-outline-gray-2'
})
</script>
