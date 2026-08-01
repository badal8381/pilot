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
