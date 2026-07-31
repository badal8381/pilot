<template>
  <div v-if="loading" class="flex justify-center items-center h-40">
    <Spinner size="lg" class="text-ink-gray-4" />
  </div>
  <div v-else class="space-y-6">
    <div class="space-y-6">
      <SettingsSwitch
        label="Enable WAF"
        description="Inspects request contents for SQLi, XSS and path traversal, across all sites and the admin."
        :model-value="enabled"
        @update:model-value="(v) => (enabled = v)"
      />

      <Alert v-if="!production" title="Not enforced yet" theme="yellow" :dismissible="false">
        <template #description>
          <span class="text-ink-gray-6 text-p-sm"
            >The WAF takes effect only in production (it's applied by nginx). This bench isn't
            deployed, so nothing is enforced until you run
            <span class="font-mono text-xs">pilot setup production</span>.</span
          >
        </template>
      </Alert>

      <Alert
        v-if="production && enabled && !installed"
        title="ModSecurity not installed"
        theme="yellow"
        :dismissible="false"
      >
        <template #description>
          <span class="text-ink-gray-6 text-p-sm"
            >The ModSecurity module isn't installed on this host, so the WAF stays inactive even
            when enabled. Redeploy production (<span class="font-mono text-xs"
              >pilot setup production</span
            >) to install it, then it takes effect.</span
          >
        </template>
      </Alert>

      <div>
        <p class="font-medium text-ink-gray-8 text-base">Managed ruleset (OWASP CRS)</p>
        <div class="gap-4 grid grid-cols-1 sm:grid-cols-2 mt-3">
          <FormControl type="select" label="Action" :options="ACTION_OPTIONS" v-model="mode" />
          <div class="space-y-1.5">
            <FormControl
              type="select"
              label="Sensitivity"
              :options="SENSITIVITY_OPTIONS"
              v-model="paranoia"
            />
            <!-- The consequential knob on this page, and it used to be four bare
                 words. Each step up trades false positives for coverage, which is
                 the whole decision. -->
            <p class="text-ink-gray-5 text-p-sm">{{ sensitivityHint }}</p>
          </div>
        </div>
      </div>

      <Alert
        v-if="enabled && mode === 'DetectionOnly'"
        title="Log only"
        theme="yellow"
        :dismissible="false"
      >
        <template #description>
          <span class="text-ink-gray-6 text-p-sm"
            >Matches (managed <b>and</b> custom rules) are <b>logged, not blocked</b>. Review
            <RouterLink
              class="underline underline-offset-2"
              :to="{ name: 'Analytics', query: { view: 'system', window: '1h' } }"
              >the WAF analytics</RouterLink
            >, then switch Action to <b>Block</b> to enforce.</span
          >
        </template>
      </Alert>
    </div>

    <WafCustomRules
      v-model="customRules"
      :fields="ruleFields"
      :operators="ruleOperators"
      :actions="ruleActions"
    />

    <details class="group">
      <summary class="flex items-center gap-1.5 text-ink-gray-6 text-base cursor-pointer select-none">
        <span
          class="size-4 transition-transform group-open:rotate-90 lucide-chevron-right"
        ></span>Advanced
      </summary>
      <div class="space-y-4 mt-4">
        <div class="gap-4 grid grid-cols-1 sm:grid-cols-2 items-start">
          <div class="space-y-1.5">
            <FormControl
              type="number"
              label="Anomaly threshold"
              min="1"
              v-model="inboundThreshold"
            />
            <!-- These two knobs multiply, and nothing said so: Sensitivity sets
                 how much score a request accrues, this sets how much it takes to
                 act. High sensitivity with a low threshold blocks ordinary
                 traffic. -->
            <p class="text-ink-gray-5 text-p-sm">
              Score needed before Action applies. Sensitivity raises scores, so the two compound.
            </p>
          </div>
          <FormControl
            type="text"
            label="Max inspected body size"
            placeholder="50m"
            v-model="bodyLimit"
          />
        </div>
        <SettingsSwitch
          label="Inspect responses"
          description="Scan outbound responses for leaks. Adds latency."
          :model-value="inspectResponses"
          @update:model-value="(v) => (inspectResponses = v)"
        />
        <FormControl
          type="textarea"
          label="Exclusions"
          :rows="3"
          v-model="exclusionsText"
          placeholder="One SecLang rule per line, e.g. SecRuleRemoveById 942100"
        />
        <FormControl
          type="textarea"
          label="Exempt paths"
          :rows="2"
          v-model="exemptPathsText"
          placeholder="One path prefix per line, e.g. /api/method/frappe.ping"
        />
      </div>
    </details>

    <ErrorMessage v-if="error" :message="error" />

    <div class="flex justify-end">
      <Button variant="solid" :loading="saving" :disabled="!dirty" @click="save">
        Save changes
      </Button>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { RouterLink } from 'vue-router'
import { Alert, Button, ErrorMessage, FormControl, Spinner, toast } from 'frappe-ui'
import SettingsSwitch from '@/components/settings/SettingsSwitch.vue'
import WafCustomRules from '@/components/settings/WafCustomRules.vue'
import { settingsApi } from '@/api/settings'
import { ruleLabel, ruleProblem } from '@/utils/wafRules'
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

function validateRules() {
  for (const [index, rule] of customRules.value.entries()) {
    const problem = ruleProblem(rule)
    if (problem) return `${ruleLabel(rule, index)} ${problem}.`
  }
  return ''
}

function validate() {
  const threshold = Number(inboundThreshold.value)
  if (!Number.isInteger(threshold) || threshold < 1)
    return 'Anomaly threshold must be a positive whole number.'
  if (!bodyLimit.value.trim()) return 'Max inspected body size is required (e.g. 50m).'
  return validateRules()
}

async function save() {
  error.value = validate()
  if (error.value) return

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
    paranoia.value = waf.paranoia || 1
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
