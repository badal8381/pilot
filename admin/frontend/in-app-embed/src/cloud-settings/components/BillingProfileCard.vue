<!-- Billing details must exist before a payment method. Required fields mirror
     Central's validation, so Save gates locally instead of round-tripping. -->
<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import Button from "frappe-ui/src/components/Button/Button.vue";
import FormControl from "frappe-ui/src/components/FormControl/FormControl.vue";
import ErrorMessage from "frappe-ui/src/components/ErrorMessage/ErrorMessage.vue";

const props = defineProps({ store: { type: Object, required: true } });
const emit = defineEmits(["close", "saved"]);
const store = props.store;

// Mirrors Central's _REQUIRED_PROFILE_FIELDS (currency + legal identity +
// address). Email and GSTIN are optional; GSTIN is validated server-side.
const REQUIRED = [
  "currency",
  "legal_name",
  "address_line1",
  "city",
  "state",
  "country",
  "pincode",
];

const FIELDS = [
  { key: "legal_name", label: __("Legal name") },
  {
    key: "email",
    label: __("Billing email"),
    type: "email",
    placeholder: "billing@company.com",
  },
  {
    key: "address_line1",
    label: __("Billing address"),
    placeholder: __("Street address"),
    full: true,
  },
  { key: "city", label: __("City") },
  { key: "state", label: __("State") },
  { key: "country", label: __("Country") },
  { key: "pincode", label: __("PIN / ZIP") },
  { key: "gstin", label: __("GSTIN"), placeholder: "29ABCDE1234F1Z5" },
];

const form = reactive({
  currency: "",
  legal_name: "",
  email: "",
  address_line1: "",
  city: "",
  state: "",
  country: "",
  pincode: "",
  gstin: "",
});
const currencies = ref([]);
const loaded = ref(false);
const working = ref(false);
const error = ref("");

onMounted(load);

const canSave = computed(
  () =>
    !working.value && REQUIRED.every((key) => String(form[key] || "").trim()),
);
// Without a currency list the form can never satisfy `canSave`; say so.
const noCurrencies = computed(() => loaded.value && !currencies.value.length);

async function load() {
  error.value = "";
  try {
    const profile = await store.api.getBillingProfile();
    currencies.value = (profile.supported_currencies || []).map((c) =>
      typeof c === "string" ? { label: c, value: c } : c,
    );
    for (const key of Object.keys(form)) form[key] = profile[key] || "";
    loaded.value = true;
  } catch (exception) {
    error.value = store.api.getErrorMessage(exception);
  }
}

async function save() {
  if (!canSave.value) return;
  working.value = true;
  error.value = "";
  try {
    await store.api.saveBillingProfile({ ...form });
    await store.loadBilling(true);
    emit("saved");
  } catch (exception) {
    error.value = store.api.getErrorMessage(exception);
  } finally {
    working.value = false;
  }
}
</script>

<template>
  <section class="space-y-4 rounded-xl border border-outline-gray-2 p-4">
    <div>
      <p class="text-base font-semibold text-ink-gray-9">
        {{ __("Add billing details") }}
      </p>
      <p class="mt-1 text-p-sm text-ink-gray-6">
        {{
          __(
            "These go on every invoice — we'll need them before adding a payment method.",
          )
        }}
      </p>
    </div>

    <ErrorMessage :message="error" />

    <div v-if="!loaded && !error" class="h-20 rounded-lg bg-surface-gray-2" />

    <!-- Without this the load-failure state has neither a retry nor a way out. -->
    <div v-else-if="!loaded" class="flex gap-2">
      <Button @click="emit('close')">{{ __("Cancel") }}</Button>
      <Button variant="solid" @click="load">{{ __("Try again") }}</Button>
    </div>

    <template v-else>
      <div class="grid grid-cols-2 gap-3.5">
        <FormControl
          v-for="field in FIELDS"
          :key="field.key"
          v-model="form[field.key]"
          :type="field.type || 'text'"
          :label="
            REQUIRED.includes(field.key) ? `${field.label} *` : field.label
          "
          :placeholder="field.placeholder"
          :disabled="working"
          :class="field.full ? 'col-span-2' : ''"
        />
        <FormControl
          v-model="form.currency"
          type="select"
          :label="`${__('Currency')} *`"
          :options="currencies"
          :disabled="working"
        />
      </div>

      <p v-if="noCurrencies" class="text-p-sm text-ink-amber-8">
        {{
          __(
            "No billing currencies are configured, so this form can't be saved yet.",
          )
        }}
      </p>

      <div class="flex justify-end gap-2">
        <Button :disabled="working" @click="emit('close')">{{
          __("Cancel")
        }}</Button>
        <Button
          variant="solid"
          :loading="working"
          :disabled="!canSave"
          @click="save"
        >
          {{ __("Save") }}
        </Button>
      </div>
    </template>
  </section>
</template>
