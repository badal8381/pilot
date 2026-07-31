<template>
  <div class="space-y-3" ref="root">
    <div class="flex justify-between items-start gap-4">
      <div class="min-w-0">
        <p class="font-medium text-ink-gray-8 text-base">Custom rules</p>
        <!-- max-w here and shrink-0 on the button: with neither, this paragraph
             ran to the button's exact left edge and wrapped into it. -->
        <p class="mt-0.5 max-w-md text-ink-gray-5 text-p-sm">
          Checked before the managed rules, top to bottom.
        </p>
      </div>
      <!-- Stays live while a rule is unfinished, and points at the offender
           instead: a disabled button with no target leaves you hunting for which
           card it meant. -->
      <Button class="shrink-0" variant="subtle" icon-left="lucide-plus" @click="addRule">
        Add rule
      </Button>
    </div>

    <EmptyState
      v-if="!rules.length"
      icon="lucide-list-filter"
      title="No custom rules"
      description="Add a rule to block or log requests by path, IP, method, header, and more."
    />

    <!-- Two durations, not one: the flag has to arrive fast enough to read as a
         response to the click, and leave slowly enough to be watched rather than
         blink. Same class toggle, different transition on each side. -->
    <div
      v-for="(rule, ri) in rules"
      :key="keyOf(rule)"
      :data-rule-key="keyOf(rule)"
      class="bg-surface-elevation-1 border rounded-lg transition-colors"
      :class="
        flaggedKey === keyOf(rule)
          ? 'border-outline-red-3 duration-75'
          : 'border-outline-gray-2 duration-1000'
      "
    >
      <!-- Summary: what the rule is, always visible. The builder below is the
           editor for it, which is why it collapses and this does not. -->
      <div class="flex items-start gap-3 p-3">
        <!-- Labelled, then the label is hidden: a bare Switch has no accessible
             name at all (attrs land on the wrapper, not the control), while
             `label` gives the real <label for> association. sr-only keeps it out
             of a header row that has no space for the word, and the gap override
             stops the hidden node from reserving one. -->
        <Switch
          class="shrink-0 mt-0.5 [&_[data-slot='label']]:sr-only [&>div]:!gap-x-0 [&>div]:!py-0"
          label="Rule enabled"
          :model-value="rule.enabled"
          @update:model-value="(v) => (rule.enabled = v)"
        />
        <button
          type="button"
          class="flex-1 min-w-0 text-left"
          :aria-expanded="isOpen(rule)"
          @click="toggleOpen(rule)"
        >
          <p
            class="font-medium text-base truncate"
            :class="rule.enabled ? 'text-ink-gray-8' : 'text-ink-gray-5'"
          >
            {{ rule.name || 'Untitled rule' }}
          </p>
          <!-- The rule in plain English, promoted out of the card's footer. It
               was the smallest, faintest line on the card while being the one
               you actually read when auditing a list of them. -->
          <p class="mt-0.5 text-ink-gray-6 text-p-sm">{{ preview(rule) }}</p>
        </button>
        <Button
          class="shrink-0"
          variant="ghost"
          icon="lucide-chevron-down"
          :label="isOpen(rule) ? 'Collapse rule' : 'Edit rule'"
          :tooltip="isOpen(rule) ? 'Collapse' : 'Edit'"
          :class="isOpen(rule) ? 'rotate-180' : ''"
          @click="toggleOpen(rule)"
        />
        <Button
          class="shrink-0"
          variant="ghost"
          theme="red"
          icon="lucide-trash-2"
          label="Delete rule"
          tooltip="Delete rule"
          @click="promptRemove(ri)"
        />
      </div>

      <!-- No rule between the summary and the builder: only one rule can be open
           at a time, so the card's own border already bounds it and the line was
           just cutting a single object in half. -->
      <div v-if="isOpen(rule)" class="space-y-4 mx-3 mb-3">
        <FormControl
          type="text"
          label="Rule name"
          v-model="rule.name"
          placeholder="Block /admin from outside the office"
        />

        <div class="space-y-2">
          <!-- All/Any only once there is something to combine: with a single
               condition the choice has no meaning. -->
          <div class="flex flex-wrap items-center gap-2 text-ink-gray-7 text-base">
            <span>When</span>
            <Select
              v-if="rule.conditions.length > 1"
              v-model="rule.match"
              :options="MATCH_OPTIONS"
              class="w-24"
            />
            <span>{{ rule.conditions.length > 1 ? 'of the following match:' : 'this matches:' }}</span>
          </div>

          <div
            v-if="rule.conditions.length > 1"
            class="hidden sm:grid grid-cols-[10rem_11rem_minmax(0,1fr)_2rem] gap-2 text-ink-gray-5 text-sm"
          >
            <span>Field</span>
            <span>Condition</span>
            <span>Value</span>
            <span />
          </div>

          <div
            v-for="(cond, ci) in rule.conditions"
            :key="keyOf(cond)"
            class="gap-2 grid grid-cols-1 sm:grid-cols-[10rem_11rem_minmax(0,1fr)_2rem] items-start"
          >
            <!-- The header-name input stacks inside the field column rather than
                 taking a column of its own: as a sibling it shoved this row's
                 operator and value out of line with every other row. -->
            <div class="space-y-1.5 min-w-0">
              <Select v-model="cond.field" :options="fieldOptions" class="w-full" />
              <TextInput
                v-if="cond.field === 'header'"
                v-model="cond.header_name"
                placeholder="Header name"
                class="w-full"
              />
            </div>
            <Select v-model="cond.operator" :options="operatorOptions" class="w-full" />
            <TextInput
              v-model="cond.value"
              :placeholder="placeholder(cond.field)"
              class="w-full"
            />
            <!-- A rule with no conditions is dropped silently by the renderer,
                 so the last one cannot go. -->
            <Button
              variant="ghost"
              icon="lucide-x"
              label="Remove condition"
              tooltip="Remove condition"
              :disabled="rule.conditions.length === 1"
              @click="removeCondition(rule, ci)"
            />
          </div>

          <Button variant="ghost" icon-left="lucide-plus" @click="addCondition(rule)">
            Add condition
          </Button>
        </div>

        <div class="space-y-1.5">
          <div class="flex flex-wrap items-center gap-2 text-ink-gray-7 text-base">
            <span>Then</span>
            <Select v-model="rule.action" :options="actionOptions" class="w-48" />
          </div>
          <!-- Skip is the one action that removes protection rather than adding
               it, and as a plain option it looked like a peer of Block and Log. -->
          <p
            v-if="rule.action === 'skip'"
            class="flex items-start gap-1.5 text-ink-amber-7 text-p-sm"
          >
            <span class="shrink-0 mt-0.5 size-3.5 lucide-triangle-alert" />
            Matching requests bypass the WAF entirely - no managed rules, no inspection.
          </p>
        </div>
      </div>
    </div>

    <Dialog v-model="showRemove" :options="{ title: 'Delete rule', size: 'md' }">
      <template #body-content>
        <p class="text-ink-gray-7 text-p-base">
          Delete <strong>{{ removingLabel }}</strong
          >? Requests it was matching fall through to the managed ruleset.
        </p>
        <div class="flex justify-end gap-2 mt-4">
          <Button variant="ghost" @click="showRemove = false">Cancel</Button>
          <Button variant="solid" theme="red" @click="confirmRemove">Delete</Button>
        </div>
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { computed, onUnmounted, ref } from 'vue'
import { Button, Dialog, FormControl, Select, Switch, TextInput } from 'frappe-ui'
import EmptyState from '@/components/common/EmptyState.vue'
import { ruleProblem } from '@/utils/wafRules'

// Two-way bound so the child owns list edits without mutating a prop.
const rules = defineModel({ type: Array, default: () => [] })
const props = defineProps({
  fields: { type: Array, default: () => [] },
  operators: { type: Array, default: () => [] },
  actions: { type: Array, default: () => [] },
})

const FIELD_LABELS = {
  uri_path: 'URI Path',
  uri_full: 'Full URI',
  query: 'Query String',
  method: 'HTTP Method',
  source_ip: 'Source IP',
  user_agent: 'User Agent',
  header: 'Request Header',
  host: 'Host',
}
const OPERATOR_LABELS = {
  is: 'is',
  is_not: 'is not',
  contains: 'contains',
  not_contains: 'does not contain',
  starts_with: 'starts with',
  matches: 'matches regex',
}
const ACTION_LABELS = { block: 'Block', log: 'Log', skip: 'Skip' }
const PLACEHOLDERS = {
  source_ip: '10.0.0.0/8, 203.0.113.4',
  method: 'POST',
  uri_path: '/admin',
  host: 'example.com',
}
const MATCH_OPTIONS = [
  { label: 'All', value: 'all' },
  { label: 'Any', value: 'any' },
]

const fieldOptions = computed(() =>
  props.fields.map((f) => ({ label: FIELD_LABELS[f] || f, value: f })),
)
const operatorOptions = computed(() =>
  props.operators.map((o) => ({ label: OPERATOR_LABELS[o] || o, value: o })),
)
const actionOptions = computed(() =>
  props.actions.map((a) => ({ label: ACTION_LABELS[a] || a, value: a })),
)

function placeholder(field) {
  return PLACEHOLDERS[field] || 'value'
}

// Stable identity for :key. Rules and conditions arrive from the API with no id
// of their own, and an index key means deleting the first of three re-keys the
// rest - Vue then patches the inputs in place and a focused caret jumps to the
// wrong row. Keyed off object identity so it survives a splice without adding a
// field the API payload would have to carry.
const keys = new WeakMap()
let nextKey = 0
function keyOf(object) {
  if (!keys.has(object)) keys.set(object, `k${(nextKey += 1)}`)
  return keys.get(object)
}

// Collapsed by default: the summary line is the rule, and the builder is the
// editor for it. A rule added here is empty, so there is nothing to summarise
// and it opens straight away.
//
// One key, not a set: opening a rule closes the one before it. Editing is a
// one-at-a-time job here, and a column of open builders is the wall of controls
// collapsing was meant to get rid of.
const openKey = ref('')
const isOpen = (rule) => openKey.value === keyOf(rule)
function toggleOpen(rule) {
  const key = keyOf(rule)
  openKey.value = openKey.value === key ? '' : key
}

// Flashing the unfinished rule rather than blocking the button. Same predicate
// the save path uses, so what stops you adding and what stops you saving can
// never disagree.
const flaggedKey = ref('')
const root = ref(null)
let flagTimer = null

function flagUnfinished() {
  const rule = rules.value.find((candidate) => ruleProblem(candidate))
  if (!rule) return false
  const key = keyOf(rule)
  openKey.value = key
  flaggedKey.value = key
  clearTimeout(flagTimer)
  // Held just under a second, then the class flips and the 1s transition takes
  // the outline back to gray on its own.
  flagTimer = setTimeout(() => (flaggedKey.value = ''), 900)
  // Looked up rather than held in a ref map: this is a one-off nudge, and the
  // card carries its key already.
  root.value?.querySelector(`[data-rule-key="${key}"]`)?.scrollIntoView({
    block: 'nearest',
    behavior: 'smooth',
  })
  return true
}

onUnmounted(() => clearTimeout(flagTimer))

function newCondition() {
  return { field: 'uri_path', operator: 'contains', value: '', header_name: '' }
}
function addRule() {
  if (flagUnfinished()) return
  const rule = {
    name: '',
    action: 'block',
    match: 'all',
    enabled: true,
    conditions: [newCondition()],
  }
  rules.value.push(rule)
  // Read the pushed item back rather than keying off the local: `rules` is a
  // reactive array, so what the template iterates is a proxy of this object, not
  // this object. keyOf() is identity-based, so keying the raw one here would
  // register a key the template never asks for and the card would open closed.
  openKey.value = keyOf(rules.value[rules.value.length - 1])
}
function addCondition(rule) {
  rule.conditions.push(newCondition())
}
function removeCondition(rule, index) {
  rule.conditions.splice(index, 1)
}

// Confirmed, like every other destructive action in Settings - a WAF rule is at
// least as consequential as an SSH key, and this used to delete on one click.
const showRemove = ref(false)
const removingIndex = ref(-1)
const removingLabel = computed(() => rules.value[removingIndex.value]?.name || 'this rule')
function promptRemove(index) {
  removingIndex.value = index
  showRemove.value = true
}
function confirmRemove() {
  rules.value.splice(removingIndex.value, 1)
  showRemove.value = false
}

function preview(rule) {
  const joiner = rule.match === 'any' ? ' OR ' : ' AND '
  const parts = rule.conditions.map((c) => {
    const field =
      c.field === 'header' ? `Header ${c.header_name || '?'}` : FIELD_LABELS[c.field] || c.field
    return `${field} ${OPERATOR_LABELS[c.operator] || c.operator} "${c.value || '…'}"`
  })
  return `When ${parts.join(joiner) || '…'} → ${ACTION_LABELS[rule.action] || rule.action}`
}
</script>
