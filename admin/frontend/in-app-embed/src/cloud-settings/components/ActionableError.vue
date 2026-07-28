<!-- An error the user can act on: the reason, plus the one link that resolves it. -->
<script setup>
import Button from "frappe-ui/src/components/Button/Button.vue";
import { openExternal } from "../external";

defineProps({
  message: { type: String, default: "" },
  actionLabel: { type: String, default: "" },
  actionUrl: { type: String, default: "" },
});
</script>

<template>
  <div
    v-if="message"
    class="flex items-start gap-2 rounded-lg border border-outline-red-2 bg-surface-red-1 p-3"
    role="alert"
  >
    <!-- red-8 not the low tints: those are fill colours and unreadable as text. -->
    <span class="lucide-triangle-alert mt-0.5 size-4 shrink-0 text-ink-red-8" aria-hidden="true" />
    <div class="min-w-0 flex-1">
      <p class="text-p-sm text-ink-red-8">{{ message }}</p>
      <Button
        v-if="actionLabel && actionUrl"
        class="mt-2"
        icon-right="arrow-up-right"
        @click="openExternal(actionUrl)"
      >
        {{ actionLabel }}
      </Button>
    </div>
  </div>
</template>
