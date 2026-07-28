<script setup lang="ts">
import { Badge, Button, ErrorMessage, LoadingText } from 'frappe-ui'

import { h, onMounted, ref } from 'vue'
import { apiErrorMessage } from '@/api/client'
import { monitorApi } from '@/api/monitor'

import FCLogo from '@/components/icons/FC.vue'
import AppStorageCard from '@/components/server/AppStorageCard.vue'
import DBStorageCard from '@/components/server/DatabaseStorageCard.vue'

import type { StorageBreakdown } from '@/types/storage'
import { formatBytes } from '@/utils/format'

const storageData = ref<StorageBreakdown | null>(null)
const loading = ref(false)
const error = ref('')

const load = async () => {
  loading.value = true
  error.value = ''

  try {
    storageData.value = await monitorApi.storage()
  } catch (e) {
    error.value = apiErrorMessage(e, 'Could not load storage breakdown.')
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <section class="mx-auto max-w-5xl">
    <h2 class="text-lg mb-10">
      Server
      <Badge theme="amber">WIP</Badge>
    </h2>
  </section>

  <!-- storgae -->
  <section class="mx-auto max-w-5xl">
    <!-- header -->
    <div class="flex flex-wrap justify-between items-center gap-2 mb-4">
      <h2 class="flex items-center gap-2 font-medium text-ink-gray-8 text-lg">
        <span class="size-4 lucide-hard-drive" />
        Storage
      </h2>

      <span v-if="storageData" class="-mr-0.5"> {{ formatBytes(storageData.disk_used) }} </span>

      <span v-if="storageData" class="text-ink-gray-6">
        of {{ formatBytes(storageData.disk_total) }} used
      </span>

      <Button class="ml-auto" variant="ghost" size="sm" :loading="loading" @click="load">
        <template #icon><span class="size-4 lucide-refresh-cw" /></template>
      </Button>

      <Button :iconLeft="h(FCLogo, { class: 'size-4' })"> Manage Storage </Button>
    </div>

    <LoadingText v-if="loading && !storageData" />
    <ErrorMessage v-else-if="error" :message="error" />

    <div
      v-else-if="storageData"
      class="bg-surface-elevation-1 border border-outline-gray-2 rounded-xl overflow-hidden"
    >
      <div
        class="divide-y lg:divide-x lg:divide-y-0 grid grid-cols-1 divide-outline-gray-2 lg:grid-cols-2"
      >
        <DBStorageCard :data="storageData.database" :disk-total="storageData.disk_total" />
        <AppStorageCard :data="storageData.bench" :disk-total="storageData.disk_total" />
      </div>
    </div>
  </section>
</template>
