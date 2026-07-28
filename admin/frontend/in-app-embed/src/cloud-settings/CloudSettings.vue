<!-- The Cloud Settings dialog: frappe-ui's SettingsDialog, one panel per tab.
     ConfigProvider's `teleportTo` keeps reka-ui overlays inside the shadow root,
     where the adopted stylesheet applies; without it they render unstyled. -->
<script setup>
import { computed, onBeforeUnmount, onMounted, provide, ref, watch } from "vue";
import { ConfigProvider } from "reka-ui";
import SettingsDialog from "frappe-ui/src/components/SettingsDialog/SettingsDialog.vue";
import SettingsSidebar from "frappe-ui/src/components/SettingsDialog/SettingsSidebar.vue";
import SettingsNavGroup from "frappe-ui/src/components/SettingsDialog/SettingsNavGroup.vue";
import SettingsNavItem from "frappe-ui/src/components/SettingsDialog/SettingsNavItem.vue";
import SettingsContent from "frappe-ui/src/components/SettingsDialog/SettingsContent.vue";
import SettingsPanel from "frappe-ui/src/components/SettingsDialog/SettingsPanel.vue";
import Badge from "frappe-ui/src/components/Badge/Badge.vue";
import Button from "frappe-ui/src/components/Button/Button.vue";
import { createStore } from "./store";
import BillingPanel from "./panels/BillingPanel.vue";
import MarketplacePanel from "./panels/MarketplacePanel.vue";
import DomainsPanel from "./panels/DomainsPanel.vue";
import AdvancedPanel from "./panels/AdvancedPanel.vue";

const props = defineProps({
  context: { type: Object, default: () => ({}) },
  open: { type: Boolean, default: false },
});
const emit = defineEmits(["close"]);

const TABS = [
  {
    value: "billing",
    label: __("Billing"),
    icon: "lucide-wallet",
    component: BillingPanel,
  },
  {
    value: "marketplace",
    label: __("Marketplace"),
    icon: "lucide-layout-grid",
    component: MarketplacePanel,
  },
  {
    value: "domains",
    label: __("Domains"),
    icon: "lucide-globe",
    component: DomainsPanel,
  },
  {
    value: "advanced",
    label: __("Advanced"),
    icon: "lucide-sliders-horizontal",
    component: AdvancedPanel,
  },
];

const overlays = ref(null);
// Dropdown defaults `portalTo` to 'body', which beats ConfigProvider, so it has
// to bind this explicitly.
provide("overlayTarget", overlays);

const isOpen = ref(props.open);
const tab = ref(TABS[0].value);
// Rebuilt on every open so a reopened dialog never shows stale data or errors.
const store = ref(createStore(props.context));

watch(
  () => props.open,
  (open) => {
    if (open) {
      store.value = createStore(props.context);
      tab.value = TABS[0].value;
    }
    isOpen.value = open;
  },
);
watch(isOpen, (open) => !open && emit("close"));

const isDark = ref(document.documentElement.dataset.theme === "dark");
let themeWatcher;
onMounted(() => {
  themeWatcher = new MutationObserver(() => {
    isDark.value = document.documentElement.dataset.theme === "dark";
  });
  themeWatcher.observe(document.documentElement, {
    attributeFilter: ["data-theme"],
  });
});
onBeforeUnmount(() => themeWatcher?.disconnect());
const updateCount = computed(
  () => store.value.state.marketplace?.update_count || 0,
);
const needsBilling = computed(() =>
  Boolean(store.value.state.billing?.credit?.warning),
);
</script>

<template>
  <ConfigProvider :teleport-to="overlays">
    <div>
      <!-- 5xl = 1024px, the width the design is drawn at (default 4xl is 896px).
           unmount-on-hide=false keeps a panel's in-flight task alive across tab
           switches; unmounting it silently abandons the poller. -->
      <SettingsDialog
        v-model="isOpen"
        v-model:tab="tab"
        size="5xl"
        :shortcut="false"
        :unmount-on-hide="false"
      >
        <template #title>{{ __("Cloud settings") }}</template>

        <SettingsSidebar>
          <SettingsNavGroup :label="__('Cloud settings')">
            <SettingsNavItem
              v-for="item in TABS"
              :key="item.value"
              :value="item.value"
            >
              <template #prefix>
                <span :class="[item.icon, 'size-4 shrink-0 text-ink-gray-6']" />
              </template>
              {{ item.label }}
              <template #suffix>
                <span
                  v-if="item.value === 'billing' && needsBilling"
                  class="size-1.5 rounded-full bg-surface-amber-3"
                  :aria-label="__('Billing needs attention')"
                />
                <Badge
                  v-else-if="item.value === 'marketplace' && updateCount"
                  theme="gray"
                  :label="String(updateCount)"
                />
              </template>
            </SettingsNavItem>
          </SettingsNavGroup>
        </SettingsSidebar>

        <!-- `relative` makes this the containing block for the close button;
             SettingsDialog ships no dismiss affordance besides Escape. -->
        <SettingsContent class="relative">
          <!-- frappe-ui sets inheritAttrs:false: `label` is the accessible name. -->
          <Button
            variant="ghost"
            icon="x"
            :label="__('Close')"
            class="absolute right-4 top-3.5 z-10"
            @click="isOpen = false"
          />
          <SettingsPanel
            v-for="item in TABS"
            :key="item.value"
            :value="item.value"
          >
            <component
              :is="item.component"
              :store="store"
              :active="tab === item.value"
            />
          </SettingsPanel>
        </SettingsContent>
      </SettingsDialog>
    </div>
    <!-- The dialog is teleported in here, so this is the node the dark variants
         must key off. -->
    <div ref="overlays" :class="{ dark: isDark }" />
  </ConfigProvider>
</template>
