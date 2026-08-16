<script setup lang="ts">
import { Badge } from 'frappe-ui'

import { stateLabel, stateTone } from '@/utils/updateFormat'

defineProps({ state: { type: String, required: true } })
</script>

<template>
  <Badge :theme="stateTone(state)" variant="subtle" size="md" :label="stateLabel(state)" />
</template>
