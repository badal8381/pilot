import { onScopeDispose } from 'vue'

// A panel holding unsaved work registers a predicate here; whoever is about to
// swap that panel out asks it first.
//
// Module-level rather than provide/inject: the Settings shell doing the asking
// is not an ancestor of every panel that could be dirty, and only one panel is
// mounted at a time anyway. The guard removes itself when its owner's scope
// dies, so an unmounted panel can never block navigation.
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
