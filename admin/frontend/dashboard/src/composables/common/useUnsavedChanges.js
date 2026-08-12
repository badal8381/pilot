import { getCurrentScope, onScopeDispose } from 'vue'

// A dirty panel registers a predicate; whoever swaps it out asks first.
// Module-level: the asking shell is not an ancestor of every panel.
const guards = new Set()

export function useUnsavedChanges(isDirty) {
  // Without an active scope, onScopeDispose no-ops and the guard leaks
  // forever, permanently blocking navigation. Fail loudly instead.
  if (!getCurrentScope()) {
    throw new Error('useUnsavedChanges must be called during component setup')
  }
  const guard = () => Boolean(isDirty.value)
  guards.add(guard)
  onScopeDispose(() => guards.delete(guard))
}

export function hasUnsavedChanges() {
  for (const guard of guards) {
    try {
      if (guard()) return true
    } catch {
      // The panel behind this guard is gone; stop trusting its verdict.
      guards.delete(guard)
    }
  }
  return false
}
