<script setup lang="ts">
import { Button, ErrorMessage, LoadingText } from 'frappe-ui'
import { onMounted, ref } from 'vue'
import { apiErrorMessage } from '@/api/client'
import { monitorApi } from '@/api/monitor'
import AppStorageCard from '@/components/server/AppStorageCard.vue'
import DatabaseStorageCard from '@/components/server/DatabaseStorageCard.vue'
import type { StorageBreakdown } from '@/types/storage'
import { formatBytes } from '@/utils/format'

const storage = ref<StorageBreakdown | null>(null)
const loading = ref(false)
const error = ref('')

const load = async () => {
  loading.value = true
  error.value = ''
  try {
    storage.value = await monitorApi.storage()
  } catch (e) {
    error.value = apiErrorMessage(e, 'Could not load storage breakdown.')
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="mx-auto max-w-5xl">
    <h1 class="mb-6 font-semibold text-ink-gray-9 text-xl">Server</h1>

    <div class="flex justify-between items-center gap-3 mb-4">
      <h2 class="flex items-center gap-2 font-medium text-ink-gray-8 text-base">
        <span class="size-4 lucide-hard-drive" />
        Storage
        <span v-if="storage" class="font-normal text-ink-gray-6 text-sm">
          {{ formatBytes(storage.disk_used) }}
          of {{ formatBytes(storage.disk_total) }} used
        </span>
      </h2>
      <Button variant="ghost" size="sm" :loading="loading" @click="load">
        <template #icon><span class="size-4 lucide-refresh-cw" /></template>
      </Button>
    </div>

    <LoadingText v-if="loading && !storage" />
    <ErrorMessage v-else-if="error" :message="error" />

    <div v-else-if="storage" class="gap-4 grid grid-cols-1 lg:grid-cols-2">
      <DatabaseStorageCard :data="storage.database" :disk-total="storage.disk_total" />
      <AppStorageCard :data="storage.bench" :disk-total="storage.disk_total" />
    </div>
  </div>
</template>
