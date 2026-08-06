<template>
  <Switch v-bind="$attrs" :class="LABEL_CLASSES">
    <template v-for="(_, name) in $slots" #[name]="slotProps">
      <slot :name="name" v-bind="slotProps ?? {}" />
    </template>
  </Switch>
</template>

<script setup>
// Switch's default label (regular ink-gray-5) reads as disabled next to a
// SettingsRow. Styled via data-slot hooks: `labelClasses` is deprecated and
// no longer applied, so passing it only warns.
import { Switch } from 'frappe-ui'

defineOptions({ inheritAttrs: false })

const LABEL_CLASSES =
  "[&_[data-slot='label']]:font-medium [&_[data-slot='label']]:text-ink-gray-8 " +
  "[&_[data-slot='description']]:text-ink-gray-6"
</script>
