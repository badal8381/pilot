<script setup lang="ts">
import { ref } from 'vue'
import { TextInput } from 'frappe-ui'
import LucideEye from '~icons/lucide/eye'
import LucideEyeOff from '~icons/lucide/eye-off'

interface Props {
  label?: string
  placeholder?: string
  autocomplete?: string
}

withDefaults(defineProps<Props>(), {
  label: '',
  placeholder: '',
  autocomplete: 'off',
})

const password = defineModel({ type: String, default: '' })
const visible = ref(false)
</script>

<template>
  <TextInput
    v-model="password"
    :label="label"
    :type="visible ? 'text' : 'password'"
    :placeholder="placeholder"
    :autocomplete="autocomplete"
  >
    <template #suffix>
      <button
        type="button"
        tabindex="-1"
        class="text-ink-gray-5 hover:text-ink-gray-7"
        :aria-label="visible ? 'Hide password' : 'Show password'"
        @click="visible = !visible"
      >
        <LucideEyeOff v-if="visible" class="size-4" />
        <LucideEye v-else class="size-4" />
      </button>
    </template>
  </TextInput>
</template>
