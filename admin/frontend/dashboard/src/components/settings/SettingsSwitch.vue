<template>
  <Switch v-bind="$attrs" :class="LABEL_CLASSES">
    <template v-for="(_, name) in $slots" #[name]="slotProps">
      <slot :name="name" v-bind="slotProps ?? {}" />
    </template>
  </Switch>
</template>

<script setup>
// frappe-ui's Switch renders its label through InputLabel, which is regular
// weight in ink-gray-5. That is right for a form field, but in this dialog a
// Switch sits in the same list as SettingsRow, whose label is medium ink-gray-8
// - side by side the library default reads as disabled text. The size is
// already right (InputLabel is text-base), so only colour and weight move.
//
// Styled through the data-slot hooks the library documents rather than
// `labelClasses`, which is deprecated and no longer applied.
import { Switch } from 'frappe-ui'

defineOptions({ inheritAttrs: false })

const LABEL_CLASSES =
  "[&_[data-slot='label']]:font-medium [&_[data-slot='label']]:text-ink-gray-8 " +
  "[&_[data-slot='description']]:text-ink-gray-6"
</script>
