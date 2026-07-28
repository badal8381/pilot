<!-- Mirrors Pilot admin's Update dialog. -->
<script setup>
import { computed, ref, watch } from "vue";
import Dialog from "frappe-ui/src/components/Dialog/Dialog.vue";
import Button from "frappe-ui/src/components/Button/Button.vue";
import Checkbox from "frappe-ui/src/components/Checkbox/Checkbox.vue";
import ErrorMessage from "frappe-ui/src/components/ErrorMessage/ErrorMessage.vue";

const props = defineProps({
  apps: { type: Array, default: () => [] },
  updating: { type: Boolean, default: false },
  error: { type: String, default: "" },
});
const emit = defineEmits(["submit"]);
const open = defineModel({ type: Boolean, default: false });

const selected = ref(new Set());

// Reset per open: keying this on `props.apps` would wipe the user's selection
// whenever the marketplace refreshed underneath them.
watch(
  open,
  (isOpen) => {
    if (!isOpen) return;
    selected.value = new Set(props.apps.map((app) => app.name));
  },
  { immediate: true },
);

const submitLabel = computed(() => {
  if (props.updating) return __("Updating");
  if (!selected.value.size) return __("Update");
  if (selected.value.size === props.apps.length) return __("Update all");
  if (selected.value.size === 1) return __("Update 1 app");
  return __("Update {0} apps", [selected.value.size]);
});

function toggle(name) {
  const next = new Set(selected.value);
  next.has(name) ? next.delete(name) : next.add(name);
  selected.value = next;
}

function submit() {
  if (!selected.value.size || props.updating) return;
  emit("submit", { apps: [...selected.value] });
}
</script>

<template>
  <Dialog
    v-model="open"
    :options="{ title: __('Updates'), size: 'md' }"
    :dismissible="!updating"
  >
    <template #body-content>
      <div class="max-h-60 space-y-1 overflow-y-auto">
        <button
          v-for="app in apps"
          :key="app.name"
          type="button"
          class="flex w-full items-center gap-3 rounded-md p-2 text-left hover:bg-surface-gray-2 disabled:cursor-not-allowed"
          :disabled="updating"
          @click="toggle(app.name)"
        >
          <img
            v-if="/^https?:\/\//i.test(app.logo_url || '')"
            class="size-8 shrink-0 rounded-lg object-cover"
            :src="app.logo_url"
            :alt="app.title"
          />
          <span
            v-else
            class="flex size-8 shrink-0 items-center justify-center rounded-lg bg-surface-gray-3 text-p-sm font-semibold text-ink-gray-7"
          >
            {{ (app.title || "?").charAt(0) }}
          </span>
          <span class="min-w-0 flex-1">
            <span
              class="block truncate text-base font-semibold text-ink-gray-9"
              >{{ app.title }}</span
            >
            <span class="block text-p-sm text-ink-gray-5">
              v{{ app.installed_version }}
              <span class="px-1">→</span>
              <span class="text-ink-green-7">v{{ app.latest_version }}</span>
            </span>
          </span>
          <Checkbox
            :model-value="selected.has(app.name)"
            :disabled="updating"
            class="pointer-events-none shrink-0"
            :aria-label="app.title"
          />
        </button>
      </div>

      <div v-if="updating" class="mt-4 text-p-sm text-ink-gray-6" role="status">
        {{ __("Updating selected apps. This can take a few minutes.") }}
      </div>

      <ErrorMessage :message="error" class="mt-4" />
    </template>

    <template #actions>
      <div class="flex justify-end gap-2">
        <Button
          :disabled="updating || !selected.size"
          @click="selected = new Set()"
        >
          {{ __("Clear") }}
        </Button>
        <Button
          variant="solid"
          :disabled="updating || !selected.size"
          @click="submit"
        >
          {{ submitLabel }}
        </Button>
      </div>
    </template>
  </Dialog>
</template>
