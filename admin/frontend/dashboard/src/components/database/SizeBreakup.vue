<template>
  <div class="p-4">
    <UsageMeter :parts="parts" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import UsageMeter from '@/components/common/UsageMeter.vue'

const props = defineProps({
  size: { type: Object, required: true },
})

const COLORS = {
  data: '#ef4444',
  index: '#06b6d4',
  claimable: '#f59e0b',
  free: '#d1d5db',
}

const parts = computed(() => [
  { label: 'Data Size', bytes: props.size.data_bytes, color: COLORS.data },
  { label: 'Index Size', bytes: props.size.index_bytes, color: COLORS.index },
  { label: 'Claimable Space', bytes: props.size.claimable_bytes, color: COLORS.claimable },
  { label: 'Free Space', bytes: props.size.free_bytes, color: COLORS.free },
])
</script>
