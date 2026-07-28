<script setup>
import { computed, ref, watch } from "vue";
import SettingsHeader from "frappe-ui/src/components/SettingsDialog/SettingsHeader.vue";
import SettingsBody from "frappe-ui/src/components/SettingsDialog/SettingsBody.vue";
import Button from "frappe-ui/src/components/Button/Button.vue";
import Badge from "frappe-ui/src/components/Badge/Badge.vue";
import FormControl from "frappe-ui/src/components/FormControl/FormControl.vue";
import ErrorMessage from "frappe-ui/src/components/ErrorMessage/ErrorMessage.vue";
import Tooltip from "frappe-ui/src/components/Tooltip/Tooltip.vue";
import PanelState from "../components/PanelState.vue";

const props = defineProps({
  store: { type: Object, required: true },
  active: { type: Boolean, default: false },
});
const store = props.store;

const input = ref("");
const pendingDomain = ref("");
const dnsRecords = ref([]);
const working = ref(false);

watch(
  () => props.active,
  (active) => {
    if (active) store.loadDomains();
  },
  { immediate: true },
);

const domains = computed(() => store.state.domains?.domains);
const error = computed(() => store.state.domainsError);
// A load failure blanks the panel and needs a retry; an action failure is inline.
const loadFailed = computed(() => Boolean(error.value) && !domains.value);
const canAdd = computed(() => Boolean(input.value.trim()) && !working.value);

// Show the DNS records the customer must add before we attach the domain. Some
// domains need none, in which case attach immediately.
async function previewDomain() {
  const domain = input.value.trim();
  if (!domain) return;
  await run(async () => {
    const response = await store.api.getDomainDnsRecords(domain);
    dnsRecords.value = response.records || [];
    pendingDomain.value = domain;
    if (!dnsRecords.value.length) await confirmAdd();
  });
}

async function confirmAdd() {
  const domain = pendingDomain.value || input.value.trim();
  if (!domain) return;
  await run(async () => {
    await store.api.addDomain(domain);
    clearPreview();
    await store.loadDomains(true);
  });
}

const makePrimary = (domain) =>
  run(async () => {
    await store.api.setPrimaryDomain(domain);
    await store.loadDomains(true);
  });

const remove = (domain) =>
  run(async () => {
    await store.api.removeDomain(domain);
    await store.loadDomains(true);
  });

async function run(action) {
  working.value = true;
  store.state.domainsError = "";
  try {
    await action();
  } catch (exception) {
    store.state.domainsError = store.api.getErrorMessage(exception);
  } finally {
    working.value = false;
  }
}

function clearPreview() {
  dnsRecords.value = [];
  pendingDomain.value = "";
  input.value = "";
}
</script>

<template>
  <SettingsHeader
    :title="__('Domains')"
    :description="__('The addresses this site answers on.')"
  />
  <SettingsBody>
    <PanelState
      class="pt-8"
      :loading="!domains && !error"
      :error="loadFailed ? error : ''"
      :title="__(`Couldn't load domains`)"
      @retry="store.loadDomains(true)"
    >
      <div class="space-y-4">
        <div class="flex items-center gap-2">
          <FormControl
            v-model="input"
            type="text"
            class="flex-1"
            :placeholder="__('shop.mycompany.in')"
            :disabled="working"
            @keyup.enter="previewDomain"
          />
          <Button :disabled="!canAdd" :loading="working && !pendingDomain" @click="previewDomain">
            {{ __("Add") }}
          </Button>
        </div>

        <ErrorMessage :message="error" />

        <section v-if="dnsRecords.length" class="rounded-xl border border-outline-gray-2 p-4">
          <p class="text-base font-medium text-ink-gray-9">{{ pendingDomain }}</p>
          <p class="mt-1 text-p-sm text-ink-gray-6">
            {{ __("Add these DNS records at your provider, then continue.") }}
          </p>
          <div class="my-3 space-y-2">
            <div
              v-for="(record, index) in dnsRecords"
              :key="index"
              class="grid grid-cols-[70px_minmax(0,1fr)_minmax(0,1.4fr)] items-center gap-3 rounded-lg bg-surface-gray-1 px-3 py-2.5 text-p-sm text-ink-gray-7"
            >
              <span>{{ record.type }}</span>
              <code class="truncate text-ink-gray-9">{{ record.host }}</code>
              <code class="truncate text-ink-gray-9">{{ record.value }}</code>
            </div>
          </div>
          <div class="flex justify-end gap-2">
            <Button :disabled="working" @click="clearPreview">{{ __("Cancel") }}</Button>
            <Button variant="solid" :loading="working" @click="confirmAdd">
              {{ __("Add domain") }}
            </Button>
          </div>
        </section>

        <div
          v-for="domain in domains"
          :key="domain.domain"
          class="flex items-center justify-between gap-2 rounded-lg border border-outline-gray-2 p-3"
        >
          <div>
            <p class="flex items-center gap-1.5 text-base font-semibold text-ink-gray-9">
              {{ domain.domain }}
              <Tooltip :text="__('Managed SSL certificate')">
                <span class="lucide-lock size-3.5 text-ink-green-7" aria-hidden="true" />
              </Tooltip>
            </p>
            <p class="mt-1 text-p-sm text-ink-gray-6">
              {{ domain.is_default ? __("Default address · managed SSL") : __("Managed SSL") }}
            </p>
          </div>
          <div class="flex shrink-0 items-center gap-2">
            <Badge v-if="domain.is_primary" theme="green" :label="__('Primary')" />
            <Button v-else :disabled="working" @click="makePrimary(domain.domain)">
              {{ __("Make primary") }}
            </Button>
            <Button v-if="!domain.is_default" :disabled="working" @click="remove(domain.domain)">
              {{ __("Remove") }}
            </Button>
          </div>
        </div>

        <p v-if="(domains || []).length <= 1" class="text-p-sm text-ink-gray-5">
          {{ __("No custom domains yet. Add one above and we'll handle SSL once DNS checks out.") }}
        </p>
      </div>
    </PanelState>
  </SettingsBody>
</template>
