// One definition of "this rule would not do what you meant", shared by the two
// places that need it: the rules editor, which refuses to stack another rule on
// top of an unfinished one, and the save path, which has to explain why. Two
// call sites, one rule - they must not drift apart.
//
// An empty condition value is the dangerous case, not the inert one: it matches
// every request for that field, so a half-built Block rule blocks everything.
// A rule with no conditions is dropped by the nginx renderer without a word.
export function ruleProblem(rule) {
  if (!rule.conditions?.length) return 'has no conditions, so it would never apply'
  for (const [index, condition] of rule.conditions.entries()) {
    if (!String(condition.value ?? '').trim())
      return `is missing a value in condition ${index + 1}, which would match every request`
    if (condition.field === 'header' && !condition.header_name?.trim())
      return `does not name the request header in condition ${index + 1}`
  }
  return ''
}

export function ruleLabel(rule, index) {
  return rule.name?.trim() || `Rule ${index + 1}`
}
