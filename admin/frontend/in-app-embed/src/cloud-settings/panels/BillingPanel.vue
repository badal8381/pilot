<script setup>
import { computed, ref, watch } from "vue";
import SettingsHeader from "frappe-ui/src/components/SettingsDialog/SettingsHeader.vue";
import SettingsBody from "frappe-ui/src/components/SettingsDialog/SettingsBody.vue";
import Button from "frappe-ui/src/components/Button/Button.vue";
import ErrorMessage from "frappe-ui/src/components/ErrorMessage/ErrorMessage.vue";
import PanelState from "../components/PanelState.vue";
import BillingProfileCard from "../components/BillingProfileCard.vue";
import AddPaymentCard from "../components/AddPaymentCard.vue";
import { openExternal } from "../external";

const props = defineProps({
  store: { type: Object, required: true },
  active: { type: Boolean, default: false },
});
const store = props.store;

// One inline flow at a time: "" | "profile" | "payment".
const flow = ref("");
const removing = ref(false);
const removeError = ref("");
const openingChangePlan = ref(false);
const changePlanError = ref("");

watch(
  () => props.active,
  (active) => {
    if (active) load();
  },
  { immediate: true },
);

async function load() {
  // A card added on a gateway's hosted page activates on return; no webhook.
  try {
    await store.api.reconcilePaymentSetup();
  } catch {
    // ignore — the summary below still loads and reports its own errors
  }
  await store.loadBilling(true);
}

const billing = computed(() => store.state.billing);
const error = computed(() => store.state.billingError);
// Only a first load replaces the panel; a failed refresh keeps what we have and
// reports inline, so the user never loses context over a blip.
const loadFailed = computed(() => Boolean(error.value) && !billing.value);
const plan = computed(() => billing.value?.plan);

const planSubtitle = computed(() => {
  if (plan.value?.subtitle) return plan.value.subtitle;
  return Object.values(plan.value?.specs || {})
    .filter(Boolean)
    .join(" · ");
});

// Central may report no usage; show specs at 0% rather than invent numbers.
const meters = computed(() => {
  const usage = billing.value?.usage;
  if (Array.isArray(usage) && usage.length) {
    return usage.map((m) => ({ ...m, percent: clamp(m.percent) }));
  }
  const specs = plan.value?.specs || {};
  return [
    { name: __("CPU"), percent: 0, detail: specs.cpu || __("Not reported") },
    {
      name: __("Memory"),
      percent: 0,
      detail: specs.memory || __("Not reported"),
    },
    {
      name: __("Storage"),
      percent: 0,
      detail: specs.storage || __("Not reported"),
    },
  ];
});

function clamp(percent) {
  return Math.max(0, Math.min(100, Math.round(Number(percent) || 0)));
}

// Billing details must exist before a payment method; route the button accordingly.
function startPayment() {
  removeError.value = "";
  flow.value = billing.value?.profile_complete ? "payment" : "profile";
}

async function removeCard() {
  if (removing.value) return;
  removing.value = true;
  removeError.value = "";
  try {
    await store.api.removePaymentMethod(billing.value.payment_method.name);
    await store.loadBilling(true);
  } catch (exception) {
    removeError.value = store.api.getErrorMessage(exception);
  } finally {
    removing.value = false;
  }
}

// Temporary: in-embed change plan is not ready; send users to Central.
async function openChangePlan() {
  if (openingChangePlan.value) return;
  openingChangePlan.value = true;
  changePlanError.value = "";
  try {
    const response = store.state.context?.account_url
      ? { url: store.state.context.account_url }
      : await store.api.getAccountUrl();
    if (!response?.url) throw new Error(__("Central is not configured."));
    openExternal(response.url);
  } catch (exception) {
    changePlanError.value = store.api.getErrorMessage(exception);
  } finally {
    openingChangePlan.value = false;
  }
}
</script>

<template>
  <SettingsHeader
    :title="__('Billing')"
    :description="__('Your plan, usage, credit and payment method.')"
  />
  <SettingsBody>
    <PanelState
      class="pt-8"
      :loading="!billing && !error"
      :error="loadFailed ? error : ''"
      :title="__(`Couldn't load billing`)"
      @retry="load"
    >
      <!-- Site with no billing account attached: explain, don't show empty cards. -->
      <div
        v-if="!plan"
        class="flex items-start gap-3 rounded-xl border border-dashed border-outline-gray-3 p-4"
      >
        <span
          class="lucide-wallet mt-0.5 size-4 shrink-0 text-ink-gray-5"
          aria-hidden="true"
        />
        <div>
          <p class="text-base font-medium text-ink-gray-9">
            {{ __("Billing isn't available for this site yet") }}
          </p>
          <p class="mt-1 text-p-sm text-ink-gray-6">
            {{
              __(
                "This site isn't connected to a billing account, or the connection isn't ready.",
              )
            }}
          </p>
          <Button
            class="mt-3"
            icon-right="arrow-up-right"
            :disabled="openingChangePlan"
            @click="openChangePlan"
          >
            {{ openingChangePlan ? __("Opening…") : __("View plans") }}
          </Button>
          <ErrorMessage :message="changePlanError" class="mt-2" />
        </div>
      </div>

      <div v-else class="space-y-4">
        <ErrorMessage :message="loadFailed ? '' : error" />
        <section class="rounded-xl border border-outline-gray-2 p-4">
          <div class="flex items-start justify-between gap-4">
            <div>
              <p class="text-p-sm text-ink-gray-5">{{ __("Plan") }}</p>
              <p class="text-lg font-semibold text-ink-gray-9">
                {{ plan.name || __("Current plan") }}
              </p>
              <p class="text-p-sm text-ink-gray-6">{{ planSubtitle }}</p>
            </div>
            <Button
              icon-right="arrow-up-right"
              :disabled="openingChangePlan"
              @click="openChangePlan"
            >
              {{ openingChangePlan ? __("Opening…") : __("Change plan") }}
            </Button>
          </div>
          <ErrorMessage :message="changePlanError" class="mt-2" />

          <div class="mt-3 grid grid-cols-3 gap-5">
            <div v-for="meter in meters" :key="meter.name">
              <div class="flex items-center justify-between text-p-sm">
                <span class="text-ink-gray-7">{{ meter.name }}</span>
                <span class="font-medium text-ink-gray-9"
                  >{{ meter.percent }}%</span
                >
              </div>
              <div
                class="my-1 h-1.5 overflow-hidden rounded-full bg-surface-gray-3"
                role="progressbar"
                :aria-label="meter.name"
                aria-valuemin="0"
                aria-valuemax="100"
                :aria-valuenow="meter.percent"
              >
                <div
                  class="h-full rounded-full bg-surface-gray-7"
                  :style="{ width: `${meter.percent}%` }"
                />
              </div>
              <p class="text-p-xs text-ink-gray-5">{{ meter.detail }}</p>
            </div>
          </div>
        </section>

        <div class="grid grid-cols-2 gap-3">
          <section class="rounded-xl border border-outline-gray-2 p-4">
            <p class="text-p-sm text-ink-gray-5">
              {{ __("Estimated this cycle") }}
            </p>
            <p class="mt-1 text-2xl font-semibold text-ink-gray-9">
              {{ billing.estimate?.amount ?? "—" }}
            </p>
            <p class="mt-1 text-p-sm text-ink-gray-6">
              {{ billing.estimate?.note }}
            </p>
          </section>
          <section class="rounded-xl border border-outline-gray-2 p-4">
            <p class="text-p-sm text-ink-gray-5">{{ __("Trial credit") }}</p>
            <p class="mt-1 text-2xl font-semibold text-ink-gray-9">
              {{ billing.credit?.amount ?? "—" }}
            </p>
            <p
              class="mt-1 flex items-center gap-1.5 text-p-sm"
              :class="
                billing.credit?.warning ? 'text-ink-amber-8' : 'text-ink-gray-6'
              "
            >
              <span
                v-if="billing.credit?.warning"
                class="lucide-triangle-alert size-3.5"
                aria-hidden="true"
              />
              {{ billing.credit?.note }}
            </p>
          </section>
        </div>

        <BillingProfileCard
          v-if="flow === 'profile'"
          :store="store"
          @close="flow = ''"
          @saved="flow = 'payment'"
        />
        <AddPaymentCard
          v-else-if="flow === 'payment'"
          :store="store"
          @close="flow = ''"
        />

        <section
          v-else
          class="rounded-xl border border-dashed border-outline-gray-3 p-4"
          :class="
            billing.payment_method
              ? 'flex items-center justify-between gap-4'
              : ''
          "
        >
          <div class="flex items-start gap-3">
            <span
              class="lucide-credit-card mt-0.5 size-4 shrink-0 text-ink-gray-5"
              aria-hidden="true"
            />
            <div>
              <p class="text-base font-medium text-ink-gray-9">
                {{
                  billing.payment_method
                    ? billing.payment_method.label
                    : __("No payment method yet")
                }}
              </p>
              <p class="mt-1 text-p-sm text-ink-gray-6">
                {{
                  billing.payment_method
                    ? __("Used for your monthly bill.")
                    : __(
                        "You're on trial credit. Add a payment method to keep this site running after it.",
                      )
                }}
              </p>
              <ErrorMessage :message="removeError" class="mt-2" />
            </div>
          </div>
          <Button
            v-if="billing.payment_method"
            :loading="removing"
            @click="removeCard"
          >
            {{ __("Remove") }}
          </Button>
          <Button
            v-else
            class="mt-3"
            variant="solid"
            icon-left="plus"
            @click="startPayment"
          >
            {{ __("Add payment method") }}
          </Button>
        </section>
      </div>
    </PanelState>
  </SettingsBody>
</template>
