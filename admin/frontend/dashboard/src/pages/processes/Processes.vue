<template>
  <div class="mx-auto max-w-3xl">
    <div class="flex justify-between items-center gap-3">
      <div>
        <h1 class="font-semibold text-ink-gray-9 text-xl">Processes</h1>
        <p class="mt-1 text-ink-gray-5 text-p-base hidden sm:block">
          Bench and app services, with per-process control.
        </p>
      </div>
      <Button
        variant="subtle"
        size="sm"
        :loading="loading"
        icon-left="lucide-refresh-cw"
        @click="load"
      >
        Refresh
      </Button>
    </div>

    <div v-if="loading && !processes.length" class="flex justify-center mt-16">
      <LoadingText />
    </div>
    <div v-else-if="error" class="mt-4">
      <ErrorMessage :message="error" />
    </div>

    <div
      v-else-if="processes.length"
      class="bg-surface-elevation-1 mt-4 divide-outline-gray-1 divide-y overflow-hidden"
    >
      <div v-for="proc in processes" :key="proc.name" class="flex items-center gap-3 py-3">
        <span
          class="rounded-full size-2.5 shrink-0"
          :class="proc.status === 'running' ? 'bg-surface-green-3' : 'bg-surface-gray-5'"
        />
        <div class="flex-1 min-w-0">
          <span class="font-medium text-ink-gray-9 text-base truncate">{{ proc.name }}</span>
          <p class="mt-0.5 text-ink-gray-5 text-p-sm truncate">{{ subtitle(proc) }}</p>
        </div>
        <Button
          size="sm"
          variant="subtle"
          :loading="busy === `${proc.name}:restart`"
          :disabled="!controllable || !!busy"
          @click="act(proc.name, 'restart')"
        >
          Restart
        </Button>
        <Button
          size="sm"
          variant="subtle"
          :loading="busy === `${proc.name}:stop`"
          :disabled="!controllable || !!busy || proc.status !== 'running'"
          @click="act(proc.name, 'stop')"
        >
          Stop
        </Button>
      </div>
    </div>

    <p v-else class="mt-16 text-ink-gray-5 text-sm text-center">No processes found.</p>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { Button, ErrorMessage, LoadingText } from 'frappe-ui'
import { processesApi } from '@/api/processes'

const processes = ref([])
const controllable = ref(false)
const loading = ref(false)
const busy = ref('')
const error = ref('')

function subtitle(proc) {
  const parts = [proc.status]
  if (proc.uptime) parts.push(`up ${proc.uptime}`)
  if (proc.cpu_percent != null) parts.push(`${proc.cpu_percent}% cpu`)
  if (proc.rss_mb != null) parts.push(`${proc.rss_mb} MB`)
  return parts.join(' · ')
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await processesApi.list()
    processes.value = data.processes || []
    controllable.value = !!data.controllable
  } catch (e) {
    error.value = e?.message || 'Could not load processes.'
  } finally {
    loading.value = false
  }
}

async function act(name, action) {
  busy.value = `${name}:${action}`
  error.value = ''
  try {
    const data = await processesApi.control(name, action)
    processes.value = data.processes || processes.value
  } catch (e) {
    error.value = e?.message || `Could not ${action} ${name}.`
  } finally {
    busy.value = ''
  }
}

onMounted(load)
</script>
