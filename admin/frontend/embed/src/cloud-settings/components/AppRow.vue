<script setup>
import { computed, inject, ref } from "vue";
import Button from "frappe-ui/src/components/Button/Button.vue";
import Dropdown from "frappe-ui/src/components/Dropdown/Dropdown.vue";
import Tooltip from "frappe-ui/src/components/Tooltip/Tooltip.vue";

const props = defineProps({
  app: { type: Object, required: true },
  // Action verb while this app's task runs: "install" | "uninstall" | "update".
  pending: { type: String, default: "" },
  error: { type: String, default: "" },
});
const emit = defineEmits(["install", "uninstall", "update"]);

const busy = computed(() => Boolean(props.pending));
const imageFailed = ref(false);
// Keep the menu inside the shadow root, where the adopted stylesheet applies.
const overlayTarget = inject("overlayTarget", "body");

// Catalog logos are absolute; a relative path would 404 against the Desk site,
// so fall straight through to the placeholder.
const logoUrl = computed(() => {
  const url = String(props.app.logo_url || "").trim();
  return /^https?:\/\//i.test(url) && !imageFailed.value ? url : "";
});

const requiredVersion = computed(
  () => String(props.app.required_version || "").match(/\d+/)?.[0],
);
const incompatibleLabel = computed(() =>
  requiredVersion.value
    ? __("Needs Version {0}", [requiredVersion.value])
    : __("Incompatible"),
);
const incompatibleReason = computed(() =>
  requiredVersion.value
    ? __("Needs Version {0} — change your server's version to install it", [
        requiredVersion.value,
      ])
    : __("Not available for this version of Frappe"),
);
</script>

<template>
  <div class="border-b border-outline-gray-1 py-3">
    <div class="flex min-h-[48px] items-center gap-2.5">
      <img
        v-if="logoUrl"
        class="size-8 shrink-0 rounded-[9px] object-cover"
        :src="logoUrl"
        :alt="app.title"
        loading="lazy"
        decoding="async"
        @error="imageFailed = true"
      />
      <div
        v-else
        class="flex size-8 shrink-0 items-center justify-center rounded-[9px] bg-surface-gray-2 text-base font-semibold uppercase text-ink-gray-6"
      >
        {{ (app.title || "?").charAt(0) }}
      </div>

      <div class="min-w-0 flex-1">
        <div class="flex items-baseline gap-1.5">
          <span
            class="truncate text-base font-semibold text-ink-gray-9"
            :title="app.title"
          >
            {{ app.title }}
          </span>
          <span class="shrink-0 whitespace-nowrap text-p-sm text-ink-gray-5">
            <template v-if="app.installed && app.has_update">
              v{{ app.installed_version }}
              <span class="text-ink-green-7">→ v{{ app.latest_version }}</span>
            </template>
            <template v-else-if="app.installed && app.installed_version">
              v{{ app.installed_version }}
            </template>
            <template v-else-if="app.latest_version"
              >v{{ app.latest_version }}</template
            >
          </span>
        </div>
        <p class="truncate text-p-sm text-ink-gray-5" :title="app.description">
          {{ app.description }}
        </p>
      </div>

      <div class="flex shrink-0 items-center gap-1">
        <Tooltip v-if="error && !busy" :text="error">
          <span
            class="lucide-triangle-alert size-3.5 text-ink-red-8"
            role="img"
            tabindex="0"
            :aria-label="error"
          />
        </Tooltip>

        <Tooltip
          v-if="!app.installed && !app.installable"
          :text="incompatibleReason"
        >
          <span
            class="rounded-full bg-surface-gray-3 px-2.5 py-1 text-p-sm font-medium text-ink-gray-5"
            tabindex="0"
          >
            {{ incompatibleLabel }}
          </span>
        </Tooltip>

        <Button
          v-else-if="!app.installed"
          :disabled="busy"
          @click="emit('install', app)"
        >
          <template v-if="pending === 'install'" #prefix>
            <span class="cs-spinner" aria-hidden="true" />
          </template>
          {{ pending === "install" ? __("Installing") : __("Install") }}
        </Button>

        <template v-else-if="app.has_update">
          <Button variant="solid" :disabled="busy" @click="emit('update', app)">
            <template v-if="pending === 'update'" #prefix>
              <span class="cs-spinner" aria-hidden="true" />
            </template>
            {{ pending === "update" ? __("Updating") : __("Update") }}
          </Button>
          <Dropdown
            :options="[
              { label: __('Uninstall'), onClick: () => emit('uninstall', app) },
            ]"
            :portal-to="overlayTarget"
            placement="right"
          >
            <Button
              variant="ghost"
              icon="more-vertical"
              :disabled="busy"
              :label="__('More actions for {0}', [app.title])"
            />
          </Dropdown>
        </template>

        <Button v-else :disabled="busy" @click="emit('uninstall', app)">
          <template v-if="pending === 'uninstall'" #prefix>
            <span class="cs-spinner" aria-hidden="true" />
          </template>
          {{ pending === "uninstall" ? __("Uninstalling") : __("Uninstall") }}
        </Button>
      </div>
    </div>
  </div>
</template>

<style>
.cs-spinner {
  width: 1em;
  height: 1em;
  border: 2px solid currentColor;
  border-right-color: transparent;
  border-radius: 9999px;
  animation: cs-spin 0.8s linear infinite;
}

@keyframes cs-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
