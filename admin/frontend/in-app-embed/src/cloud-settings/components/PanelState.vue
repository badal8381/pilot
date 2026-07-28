<!-- Loading/error gate for the data-backed panels: a failed load must stay
     recoverable, so it shows the server's message plus a Retry. -->
<script setup>
import Button from "frappe-ui/src/components/Button/Button.vue";

defineProps({
  loading: { type: Boolean, default: false },
  error: { type: String, default: "" },
  // Shown above the retry button; the server message goes underneath.
  title: { type: String, default: "" },
});
defineEmits(["retry"]);
</script>

<!-- Single root so a parent can pass spacing/layout classes down. -->
<template>
  <div>
    <div
      v-if="error"
      class="flex flex-col items-center gap-2 rounded-lg border border-outline-gray-2 px-6 py-10 text-center"
    >
      <span
        class="lucide-triangle-alert size-5 text-ink-amber-8"
        aria-hidden="true"
      />
      <p class="text-base font-medium text-ink-gray-8">
        {{ title || __("Couldn't load this section") }}
      </p>
      <p class="max-w-md text-p-sm text-ink-gray-6">{{ error }}</p>
      <Button class="mt-2" @click="$emit('retry')">{{
        __("Try again")
      }}</Button>
    </div>

    <div
      v-else-if="loading"
      class="space-y-3"
      role="status"
      :aria-label="__('Loading')"
    >
      <div v-for="n in 3" :key="n" class="h-16 rounded-lg bg-surface-gray-2" />
    </div>

    <slot v-else />
  </div>
</template>
