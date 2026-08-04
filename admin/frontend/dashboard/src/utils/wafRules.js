export const FIELD_LABELS = {
  uri_path: 'URI Path',
  uri_full: 'Full URI',
  query: 'Query String',
  method: 'HTTP Method',
  source_ip: 'Source IP',
  user_agent: 'User Agent',
  header: 'Request Header',
  host: 'Host',
}

export const OPERATOR_LABELS = {
  is: 'is',
  is_not: 'is not',
  contains: 'contains',
  not_contains: 'does not contain',
  starts_with: 'starts with',
  matches: 'matches regex',
}

export const ACTION_LABELS = { block: 'Block', log: 'Log', skip: 'Skip' }

export function ruleProblem(rule) {
  // Shared by the editor (Incomplete badge, Add refusal) and the save gate.
  // An empty value matches every request for its field; a conditionless rule
  // is dropped by the nginx renderer without a word.
  if (!rule.conditions?.length) return 'has no conditions, so it would never apply'
  for (const [index, condition] of rule.conditions.entries()) {
    if (!String(condition.value ?? '').trim())
      return `is missing a value in condition ${index + 1}, which would match every request`
    if (condition.field === 'header' && !condition.header_name?.trim())
      return `does not name the request header in condition ${index + 1}`
  }
  return ''
}

/**
 * The collapsed row's description, without the action - the row pins that
 * separately so it never clips. Spelling out every condition outgrows the row at
 * three of them, so past one the count is what a glance gets.
 */
export function ruleSummary(rule) {
  const count = rule.conditions?.length || 0
  if (count !== 1) return `When ${rule.match === 'any' ? 'any' : 'all'} of ${count} conditions match`
  const [condition] = rule.conditions
  const field =
    condition.field === 'header'
      ? `Header ${condition.header_name || '?'}`
      : FIELD_LABELS[condition.field] || condition.field
  const operator = OPERATOR_LABELS[condition.operator] || condition.operator
  return `When ${field} ${operator} "${condition.value || '…'}"`
}

export function actionLabel(rule) {
  return ACTION_LABELS[rule.action] || rule.action
}
