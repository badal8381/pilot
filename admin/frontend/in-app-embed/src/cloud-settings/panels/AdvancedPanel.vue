<script setup>
import { computed, ref } from "vue";
import SettingsHeader from "frappe-ui/src/components/SettingsDialog/SettingsHeader.vue";
import SettingsBody from "frappe-ui/src/components/SettingsDialog/SettingsBody.vue";
import Button from "frappe-ui/src/components/Button/Button.vue";
import ErrorMessage from "frappe-ui/src/components/ErrorMessage/ErrorMessage.vue";
import { openExternal } from "../external";

const props = defineProps({ store: { type: Object, required: true } });

const context = computed(() => props.store.state.context || {});
const openingBilling = ref(false);
const billingError = ref("");

// Server controls leave the site. Billing stays in this dialog, so local and dev
// sites never depend on a configured Central account URL.
const links = computed(() => [
  {
    title: __("Open your server"),
    description: __(
      "Deploys, scaling, SSH, backups, sites — the full server controls.",
    ),
    label: __("Open server"),
    url: context.value.server_url,
  },
]);

async function openBilling() {
  if (openingBilling.value) return;
  openingBilling.value = true;
  billingError.value = "";
  try {
    const response = context.value.account_url
      ? { url: context.value.account_url }
      : await props.store.api.getAccountUrl();
    if (!response?.url) throw new Error(__("Central is not configured."));
    openExternal(response.url);
  } catch (exception) {
    billingError.value = props.store.api.getErrorMessage(exception);
  } finally {
    openingBilling.value = false;
  }
}
</script>

<template>
  <SettingsHeader
    :title="__('Advanced')"
    :description="__('Deeper controls for your server.')"
  />
  <SettingsBody>
    <div class="divide-y divide-outline-gray-1 pt-4">
      <div
        v-for="link in links"
        :key="link.title"
        class="flex items-center justify-between gap-4 py-5"
      >
        <div>
          <p class="text-base font-semibold text-ink-gray-9">
            {{ link.title }}
          </p>
          <p class="mt-1 text-p-sm text-ink-gray-5">{{ link.description }}</p>
        </div>
        <Button
          v-if="link.url"
          class="shrink-0"
          icon-right="arrow-up-right"
          @click="openExternal(link.url)"
        >
          {{ link.label }}
        </Button>
        <p v-else class="shrink-0 text-p-sm text-ink-gray-4">
          {{ __("Not configured") }}
        </p>
      </div>
      <div class="py-5">
        <div class="flex items-center justify-between gap-4">
          <div>
            <p class="text-base font-semibold text-ink-gray-9">
              {{ __("Account & billing") }}
            </p>
            <p class="mt-1 text-p-sm text-ink-gray-5">
              {{
                __(
                  "Payment methods, invoices, billing email and account settings.",
                )
              }}
            </p>
          </div>
          <Button
            class="shrink-0"
            icon-right="arrow-up-right"
            :disabled="openingBilling"
            @click="openBilling"
          >
            {{ openingBilling ? __("Opening billing") : __("Manage billing") }}
          </Button>
        </div>
        <ErrorMessage :message="billingError" class="mt-2" />
      </div>
    </div>
  </SettingsBody>
</template>
