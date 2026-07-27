import { ref } from 'vue'

// Standalone so api/client.js can report without importing useSession (which imports the client).
const signedOut = ref(false)

export function reportSignedOut() {
  signedOut.value = true
}

export function isSignedOut() {
  return signedOut.value
}

export function useSignedOut() {
  return { signedOut }
}
