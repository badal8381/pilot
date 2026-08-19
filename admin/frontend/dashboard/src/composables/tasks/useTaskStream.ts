import { ref, onMounted, onBeforeUnmount } from 'vue'

import { processLine } from '@/utils/ansi.ts'

export const useTaskStream = ({ guardHiddenTab = false } = {}) => {
  const terminal = ref(null)
  const lines = ref([])
  const rawLines = ref([])
  const streaming = ref(false)
  let source = null

  const scrollToBottom = () => {
    if (guardHiddenTab && document.hidden) return
    terminal.value?.scrollToBottom()
  }

  const push = (raw, { overwrite } = {}) => {
    if (overwrite) {
      rawLines.value[rawLines.value.length - 1] = raw
      lines.value[lines.value.length - 1] = processLine(raw)
    } else {
      rawLines.value.push(raw)
      lines.value.push(processLine(raw))
    }
    scrollToBottom()
  }

  const close = () => {
    if (source) {
      source.close()
      source = null
    }
  }

  const start = (url, { onDone, onLine, onStatus, onError } = {}) => {
    close()
    streaming.value = true
    let volatile = false

    source = new EventSource(url)

    source.onmessage = (message) => {
      let event
      try {
        event = JSON.parse(message.data)
      } catch {
        return
      }
      if (event.type === 'line') {
        if (volatile) {
          rawLines.value.pop()
          lines.value.pop()
          volatile = false
        }
        push(event.line)
        onLine?.(event.line)
      } else if (event.type === 'overwrite') {
        push(event.line, { overwrite: volatile })
        volatile = true
      } else if (event.type === 'status') {
        onStatus?.(event)
      } else if (event.type === 'done') {
        streaming.value = false
        close()
        onDone?.(event.exit_code === 0)
      }
    }

    source.onerror = () => {
      if (source?.readyState !== EventSource.CLOSED) return
      streaming.value = false
      onError?.()
    }
  }

  const stop = () => {
    close()
    streaming.value = false
  }

  if (guardHiddenTab) {
    onMounted(() => document.addEventListener('visibilitychange', scrollToBottom))
    onBeforeUnmount(() => document.removeEventListener('visibilitychange', scrollToBottom))
  }
  onBeforeUnmount(stop)

  return { terminal, lines, rawLines, streaming, start, stop, scrollToBottom }
}
