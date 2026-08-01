import { onScopeDispose } from 'vue'

// A dirty panel registers a predicate; whoever swaps it out asks first.
// Module-level: the asking shell is not an ancestor of every panel.
const guards = new Set()

export function useUnsavedChanges(isDirty) {
  const guard = () => Boolean(isDirty.value)
  guards.add(guard)
  onScopeDispose(() => guards.delete(guard))
}

export function hasUnsavedChanges() {
  for (const guard of guards) if (guard()) return true
  return false
}
