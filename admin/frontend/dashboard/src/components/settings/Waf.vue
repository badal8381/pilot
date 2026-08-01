<template>
  <div v-if="loading" class="flex justify-center items-center h-40">
    <Spinner size="lg" class="text-ink-gray-4" />
  </div>
  <div v-else class="space-y-12">
    <!-- Two groups - protection, then custom rules - carried by spacing
         (space-y-12 between, space-y-4 within) rather than headings. The 3x
         ratio against the in-group rhythm is what makes a seam read as a
         section break rather than a wide row. -->
    <div class="space-y-4">
      <SettingsSwitch
        label="Enable WAF"
        description="Inspects request contents for SQLi, XSS and path traversal, across all sites and the admin."
        :model-value="enabled"
        @update:model-value="(v) => (enabled = v)"
      />

      <!-- One inline line for the single most urgent deployment gap, replacing
           two stacked Alert boxes. Only shown while the WAF is on - off, there
           is nothing to enforce and nothing to warn about. -->
      <p v-if="setupNote" class="flex items-start gap-1.5 text-ink-amber-7 text-p-sm">
        <span class="shrink-0 mt-0.5 size-3.5 lucide-triangle-alert" />
        <span>{{ setupNote }}</span>
      </p>

      <div class="items-start gap-4 grid grid-cols-1 sm:grid-cols-2">
        <div class="space-y-1.5">
          <FormControl type="select" label="Action" :options="ACTION_OPTIONS" v-model="mode" />
          <!-- Each mode's consequence as a field hint, where the choice is made -
               the Log-only case used to be a full Alert further down the page. -->
          <p v-if="mode === 'DetectionOnly'" class="text-ink-gray-5 text-p-sm">
            Matches are logged, not blocked. Review
            <RouterLink
              class="text-ink-gray-7 hover:text-ink-gray-8"
              :to="{ name: 'Analytics', query: { view: 'system', window: '1h' } }"
              >the WAF analytics</RouterLink
            >, then switch to Block.
          </p>
          <p v-else class="text-ink-gray-5 text-p-sm">{{ ACTION_HINTS[mode] }}</p>
        </div>
        <div class="space-y-1.5">
          <!-- Four fixed, ordered options: a segmented control shows the scale a
               select was hiding. Label markup matches frappe-ui's InputLabel. -->
          <span class="block text-ink-gray-5 text-base">Sensitivity</span>
          <TabButtons :options="SENSITIVITY_OPTIONS" v-model="paranoia" />
          <!-- Each step up trades false positives for coverage, which is the
               whole decision. -->
          <p class="text-ink-gray-5 text-p-sm">{{ sensitivityHint }}</p>
        </div>
      </div>
    </div>

    <!-- Stays visible with the WAF off: staging rules first and flipping the
         switch last is the safe rollout order, and rules save independently of
         `enabled`. The switch and the absent setup note carry the off state. -->
    <WafCustomRules
      v-model="customRules"
      :fields="ruleFields"
      :operators="ruleOperators"
      :actions="ruleActions"
    />

    <details class="group">
      <!-- Chrome marks a *clicked* summary :focus-visible, so the tab-focus ring
           was appearing on every pointer toggle - blur drops it for mouse users
           while tabbing still shows the global ring. w-fit + rounded so that
           ring hugs the word instead of drawing a panel-wide rectangle. -->
      <summary
        class="flex items-center gap-1.5 pr-1.5 rounded-sm w-fit text-ink-gray-6 text-base cursor-pointer select-none"
        @click="(e) => e.currentTarget.blur()"
      >
        <span
          class="size-4 transition-transform group-open:rotate-90 lucide-chevron-right"
        ></span>Advanced
      </summary>
      <!-- Ordered tuning -> scope -> responses; the one thing that adds
           inspection goes last. Examples live in hints, not placeholders -
           a placeholder is gone at the first keystroke. -->
      <div class="space-y-4 mt-4">
        <div class="gap-4 grid grid-cols-1 sm:grid-cols-2 items-start">
          <div class="space-y-1.5">
            <FormControl
              type="number"
              label="Anomaly threshold"
              min="1"
              v-model="inboundThreshold"
            />
            <p v-if="thresholdError" class="text-ink-red-6 text-p-sm">{{ thresholdError }}</p>
            <!-- These two knobs multiply, and nothing said so: Sensitivity sets
                 how much score a request accrues, this sets how much it takes to
                 act. High sensitivity with a low threshold blocks ordinary
                 traffic. -->
            <p v-else class="text-ink-gray-5 text-p-sm">
              Score needed before Action applies. Sensitivity raises scores, so the two compound.
            </p>
          </div>
          <div class="space-y-1.5">
            <FormControl type="text" label="Max inspected body size" v-model="bodyLimit" />
            <p class="text-ink-gray-5 text-p-sm">Number with a k, m or g suffix, e.g. 50m.</p>
          </div>
        </div>
        <!-- Path-level scope before rule-level: plain English before SecLang.
             Each hint names its level, since both fields read as "don't
             inspect X" until you know the difference. -->
        <div class="space-y-1.5">
          <FormControl
            type="textarea"
            label="Exempt paths"
            :rows="3"
            placeholder="/api/method/frappe.ping"
            v-model="exemptPathsText"
          />
          <p class="text-ink-gray-5 text-p-sm">
            One path prefix per line. Requests under these skip the WAF entirely.
          </p>
        </div>
        <div class="space-y-1.5">
          <FormControl
            type="textarea"
            label="Rule exclusions (SecLang)"
            :rows="3"
            placeholder="SecRuleRemoveById 942100"
            v-model="exclusionsText"
          />
          <p class="text-ink-gray-5 text-p-sm">
            One SecLang directive per line. Turns a managed rule off everywhere.
          </p>
        </div>
        <SettingsSwitch
          label="Inspect responses"
          description="Scan outbound responses for leaks. Adds latency."
          :model-value="inspectResponses"
          @update:model-value="(v) => (inspectResponses = v)"
        />
      </div>
    </details>

    <!-- Server failures only - field problems show at their fields (threshold
         hint, Incomplete badges) and disable the button instead. -->
    <ErrorMessage v-if="error" :message="error" />

    <!-- Surfaces only once something changed: a permanently visible disabled
         button is chrome with nothing to say. -->
    <div v-if="dirty" class="flex justify-end">
      <Button variant="solid" :loading="saving" :disabled="!canSave" @click="save">
        Save changes
      </Button>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { RouterLink } from 'vue-router'
import { Button, ErrorMessage, FormControl, Spinner, TabButtons, toast } from 'frappe-ui'
import SettingsSwitch from '@/components/settings/SettingsSwitch.vue'
import WafCustomRules from '@/components/settings/WafCustomRules.vue'
import { settingsApi } from '@/api/settings'
import { ruleProblem } from '@/utils/wafRules'
import { useUnsavedChanges } from '@/composables/common/useUnsavedChanges'

// "Paused", not "Off": this and the Enable switch both read as off but do
// different things. The switch drops the module from the server config and
// coming back costs a rebuild; this leaves it loaded with the engine idle, which
// is the state you want when checking whether the WAF is behind a broken site.
// The stored value stays "Off" - only the word the user reads changes.
const ACTION_OPTIONS = [
  { label: 'Paused', value: 'Off' },
  { label: 'Log only', value: 'DetectionOnly' },
  { label: 'Block', value: 'On' },
]
const SENSITIVITY_OPTIONS = [
  { label: 'Low', value: 1 },
  { label: 'Medium', value: 2 },
  { label: 'High', value: 3 },
  { label: 'Very High', value: 4 },
]
// CRS paranoia levels. Every step up widens coverage and widens false positives
// with it - the tradeoff is the whole decision, so it is stated per level.
const SENSITIVITY_HINTS = {
  1: 'Very few false positives. Start here.',
  2: 'Admin tooling may start tripping it.',
  3: 'Expect to add exclusions.',
  4: 'Most coverage, most false positives.',
}
// DetectionOnly's hint lives in the template - it carries a link.
const ACTION_HINTS = {
  Off: 'Loaded but idle. Nothing is inspected.',
  On: 'Matching requests are rejected.',
}

const loading = ref(true)
const saving = ref(false)
const error = ref('')

const enabled = ref(false)
const installed = ref(false)
const production = ref(true)
const mode = ref('DetectionOnly')
const paranoia = ref(1)
const inboundThreshold = ref(5)
const bodyLimit = ref('50m')
const inspectResponses = ref(false)
const exclusionsText = ref('')
const exemptPathsText = ref('')
const customRules = ref([])
const ruleFields = ref([])
const ruleOperators = ref([])
const ruleActions = ref([])

const sensitivityHint = computed(() => SENSITIVITY_HINTS[Number(paranoia.value)] || '')

// The single most urgent deployment gap, or nothing. `installed` only means
// anything in production, so these can't both apply at once.
const setupNote = computed(() => {
  if (!enabled.value) return ''
  if (!production.value)
    return "Enforced in production only. This bench isn't deployed - run pilot setup production first."
  if (!installed.value)
    return 'ModSecurity is not installed on this host. Redeploy production to install it.'
  return ''
})

function linesToArray(text) {
  return text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
}

function buildPayload() {
  return {
    enabled: enabled.value,
    mode: mode.value,
    paranoia: Number(paranoia.value),
    inbound_threshold: Number(inboundThreshold.value),
    body_limit: bodyLimit.value.trim(),
    inspect_responses: inspectResponses.value,
    exclusions: linesToArray(exclusionsText.value),
    exempt_paths: linesToArray(exemptPathsText.value),
    custom_rules: customRules.value,
  }
}

// Compared against what the server last gave us, so Save is dead until something
// actually changed - and so leaving with unsaved rules is something we can warn
// about rather than discard silently.
const savedPayload = ref('')
const dirty = computed(() => JSON.stringify(buildPayload()) !== savedPayload.value)

// Both of these read `dirty`, so they have to be declared after it - a const is
// in its temporal dead zone until then, and useUnsavedChanges() evaluates its
// argument straight away.
//
// A half-built ruleset is real work. The Settings shell asks this before it
// swaps the panel out: moving between panels is a route param change on the one
// Settings record, so a component-level route guard here would never see it.
useUnsavedChanges(dirty)

// Leaving the tab entirely is the browser's to warn about, not the shell's.
function warnIfDirty(event) {
  if (!dirty.value) return
  event.preventDefault()
  event.returnValue = ''
}
onMounted(() => window.addEventListener('beforeunload', warnIfDirty))
onUnmounted(() => window.removeEventListener('beforeunload', warnIfDirty))

// A wrong fill gets a red hint at the field; an empty required field or an
// incomplete rule (already badged on its card) just holds the button.
const thresholdError = computed(() => {
  const threshold = Number(inboundThreshold.value)
  if (Number.isInteger(threshold) && threshold >= 1) return ''
  return 'Must be a positive whole number.'
})
const canSave = computed(
  () =>
    !thresholdError.value &&
    Boolean(bodyLimit.value.trim()) &&
    !customRules.value.some((rule) => ruleProblem(rule)),
)

async function save() {
  saving.value = true
  try {
    const payload = buildPayload()
    const result = await settingsApi.update({ waf: payload })
    if (!result.ok) {
      error.value = result.error || 'Failed to save.'
      return
    }
    savedPayload.value = JSON.stringify(payload)
    toast.success('WAF updated')
    if (result.nginx_error) toast.error(result.nginx_error)
  } catch (e) {
    error.value = e.message || 'Failed to save.'
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  try {
    const data = await settingsApi.get()
    production.value = !!data.production?.enabled
    const waf = data.waf || {}
    enabled.value = !!waf.enabled
    installed.value = !!waf.installed
    mode.value = waf.mode || 'DetectionOnly'
    // Cast: TabButtons matches by Object.is, so a stringy "2" would silently
    // fall back to Low and emit a change - making the form dirty on open.
    paranoia.value = Number(waf.paranoia) || 1
    inboundThreshold.value = waf.inbound_threshold ?? 5
    bodyLimit.value = waf.body_limit || '50m'
    inspectResponses.value = !!waf.inspect_responses
    exclusionsText.value = (waf.exclusions || []).join('\n')
    exemptPathsText.value = (waf.exempt_paths || []).join('\n')
    customRules.value = waf.custom_rules || []
    ruleFields.value = waf.rule_fields || []
    ruleOperators.value = waf.rule_operators || []
    ruleActions.value = waf.rule_actions || []
    // The baseline `dirty` measures against. Built from the same function as the
    // save payload so a normalisation (trimmed body limit, blank lines dropped
    // from the textareas) does not read as an edit the moment the page loads.
    savedPayload.value = JSON.stringify(buildPayload())
  } catch (e) {
    error.value = e.message || 'Could not load settings.'
  } finally {
    loading.value = false
  }
})
</script>
