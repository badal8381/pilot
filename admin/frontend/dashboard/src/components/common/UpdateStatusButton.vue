<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Button, Spinner } from 'frappe-ui'

import UpdateAppsDialog from '@/components/apps/UpdateAppsDialog.vue'

import { useUpdate } from '@/composables/updates/useUpdate'

const router = useRouter()
const { status, start } = useUpdate()
const showDialog = ref(false)

const onClick = () => {
  if (status.value.operationId) {
    router.push({ name: 'UpdateDetail', params: { operationId: status.value.operationId } })
  } else {
    showDialog.value = true
  }
}

onMounted(start)
</script>

<template>
  <template v-if="status">
    <Button
      variant="outline"
      :theme="status.kind === 'failed' ? 'red' : 'gray'"
      class="order-first"
      @click="onClick"
    >
      <template #prefix>
        <Spinner v-if="status.kind === 'active'" size="md" />
        <span v-else class="size-4" :class="status.icon" />
      </template>
      {{ status.label }}
    </Button>
    <UpdateAppsDialog v-model="showDialog" />
  </template>
</template>
