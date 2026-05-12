<template>
  <div class="bg-gray-900 border border-gray-800 rounded-lg flex flex-col overflow-hidden">

    <!-- Header -->
    <div class="px-5 py-4 border-b border-gray-800">
      <div class="flex items-center justify-between gap-3">
        <div>
          <h2 class="text-sm font-semibold text-gray-200">KiteFuel AI Agent</h2>
          <p class="text-xs text-gray-500 mt-0.5">
            Ask the agent to research markets — it borrows credit, buys data, and repays the lender autonomously
          </p>
        </div>
        <button
          @click="clearChat"
          :disabled="loading"
          class="text-xs px-3 py-1.5 rounded-md border border-gray-700 text-gray-400 hover:text-gray-200 hover:border-gray-500 disabled:opacity-40 disabled:cursor-not-allowed transition flex-shrink-0"
        >
          Clear
        </button>
      </div>
    </div>

    <!-- Message area -->
    <div
      ref="messageArea"
      class="flex-1 overflow-y-auto px-4 py-4 space-y-3"
      style="min-height: 400px; max-height: 600px;"
    >
      <!-- Empty state -->
      <div v-if="messages.length === 0" class="flex flex-col items-center justify-center h-full py-12 space-y-3">
        <div class="text-3xl">🤖</div>
        <p class="text-sm text-gray-500 text-center max-w-xs">
          Ask me about market conditions, DeFi opportunities, or crypto research.
          I'll borrow credit, fetch data, and repay the lender — all on-chain.
        </p>
        <div class="flex flex-wrap gap-2 justify-center mt-2">
          <button
            v-for="suggestion in SUGGESTIONS"
            :key="suggestion"
            @click="sendSuggestion(suggestion)"
            :disabled="loading"
            class="text-xs px-3 py-1.5 rounded-full border border-gray-700 text-gray-400 hover:border-purple-600 hover:text-purple-300 disabled:opacity-40 transition"
          >
            {{ suggestion }}
          </button>
        </div>
      </div>

      <!-- Messages -->
      <template v-for="(msg, i) in messages" :key="i">

        <!-- User message -->
        <div v-if="msg.type === 'user'" class="flex justify-end">
          <div class="max-w-[80%] bg-purple-700 text-white text-sm px-4 py-2.5 rounded-2xl rounded-tr-sm leading-relaxed">
            {{ msg.content }}
          </div>
        </div>

        <!-- Claude text -->
        <div v-else-if="msg.type === 'text'" class="flex justify-start">
          <div class="max-w-[85%] bg-gray-800 border border-gray-700 text-gray-200 text-sm px-4 py-2.5 rounded-2xl rounded-tl-sm">
            <pre class="whitespace-pre-wrap font-sans leading-relaxed">{{ msg.content }}</pre>
          </div>
        </div>

        <!-- Tool call -->
        <div v-else-if="msg.type === 'tool_call'" class="w-full">
          <div class="border border-yellow-800/60 bg-yellow-950/30 rounded-lg px-4 py-3">
            <div class="flex items-center gap-2 mb-2">
              <span class="text-yellow-400 text-xs font-semibold">⚡ {{ msg.name }}</span>
              <span class="text-[10px] text-yellow-700 uppercase tracking-wider">tool call</span>
            </div>
            <pre v-if="hasInput(msg.input)" class="text-xs text-yellow-300/70 font-mono overflow-x-auto whitespace-pre-wrap">{{ JSON.stringify(msg.input, null, 2) }}</pre>
            <span v-else class="text-xs text-yellow-700 italic">no input</span>
          </div>
        </div>

        <!-- Tool result -->
        <div v-else-if="msg.type === 'tool_result'" class="w-full">
          <div
            :class="[
              'border rounded-lg px-4 py-3',
              msg.result?.error
                ? 'border-red-800/60 bg-red-950/30'
                : 'border-green-800/60 bg-green-950/30',
            ]"
          >
            <div class="flex items-center gap-2 mb-2">
              <span
                :class="[
                  'text-xs font-semibold',
                  msg.result?.error ? 'text-red-400' : 'text-green-400',
                ]"
              >
                {{ msg.result?.error ? '✗' : '✓' }} {{ msg.name }} result
              </span>
            </div>
            <pre
              :class="[
                'text-xs font-mono overflow-x-auto whitespace-pre-wrap',
                msg.result?.error ? 'text-red-300/70' : 'text-green-300/70',
              ]"
            >{{ truncate(JSON.stringify(msg.result, null, 2), 500) }}</pre>
          </div>
        </div>

        <!-- Error -->
        <div v-else-if="msg.type === 'error'" class="w-full">
          <div class="border border-red-800 bg-red-950/40 rounded-lg px-4 py-3">
            <span class="text-xs text-red-300">⚠ {{ msg.content }}</span>
          </div>
        </div>

      </template>

      <!-- Thinking indicator -->
      <div v-if="loading" class="flex justify-start">
        <div class="bg-gray-800 border border-gray-700 rounded-2xl rounded-tl-sm px-4 py-2.5 flex items-center gap-2">
          <span class="inline-flex gap-1">
            <span class="w-1.5 h-1.5 bg-purple-400 rounded-full animate-bounce" style="animation-delay: 0ms" />
            <span class="w-1.5 h-1.5 bg-purple-400 rounded-full animate-bounce" style="animation-delay: 150ms" />
            <span class="w-1.5 h-1.5 bg-purple-400 rounded-full animate-bounce" style="animation-delay: 300ms" />
          </span>
          <span class="text-xs text-gray-400">Agent is thinking…</span>
        </div>
      </div>
    </div>

    <!-- Input bar -->
    <div class="border-t border-gray-800 px-4 py-3 flex gap-2">
      <input
        v-model="inputText"
        @keydown.enter.prevent="submit"
        :disabled="loading"
        type="text"
        placeholder="Ask the agent… e.g. 'Find the best DeFi opportunity on Kite Chain'"
        class="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-purple-600 disabled:opacity-50 transition"
      />
      <button
        @click="submit"
        :disabled="loading || !inputText.trim()"
        class="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-sm font-medium rounded-lg disabled:opacity-40 disabled:cursor-not-allowed transition flex items-center gap-1.5"
      >
        <span v-if="loading" class="inline-block w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
        <span v-else>Run Agent</span>
      </button>
    </div>

  </div>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ChatMessage {
  type: 'user' | 'text' | 'tool_call' | 'tool_result' | 'error'
  content?: string
  name?: string
  input?: Record<string, unknown>
  result?: Record<string, unknown>
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string) ?? 'http://localhost:8000'

const SUGGESTIONS = [
  'Research BTC market conditions',
  'Find the best DeFi opportunity on Kite Chain',
  'What is KiteFuel?',
  'Should I buy ETH right now?',
]

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

const messages   = ref<ChatMessage[]>([])
const inputText  = ref('')
const loading    = ref(false)
const messageArea = ref<HTMLElement | null>(null)

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function truncate(text: string, max: number): string {
  if (text.length <= max) return text
  return text.slice(0, max) + '\n… (truncated)'
}

function hasInput(input: Record<string, unknown> | undefined): boolean {
  return !!input && Object.keys(input).length > 0
}

async function scrollToBottom() {
  await nextTick()
  if (messageArea.value) {
    messageArea.value.scrollTop = messageArea.value.scrollHeight
  }
}

function pushMessage(msg: ChatMessage) {
  messages.value.push(msg)
  scrollToBottom()
}

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------

function clearChat() {
  messages.value = []
  inputText.value = ''
}

function sendSuggestion(text: string) {
  inputText.value = text
  submit()
}

async function submit() {
  const text = inputText.value.trim()
  if (!text || loading.value) return

  inputText.value = ''
  loading.value = true

  pushMessage({ type: 'user', content: text })

  try {
    const response = await fetch(`${API_BASE}/agent/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text }),
    })

    if (!response.ok) {
      pushMessage({ type: 'error', content: `HTTP ${response.status}: ${response.statusText}` })
      return
    }

    const reader  = response.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop() ?? ''

      for (const part of parts) {
        const line = part.trim()
        if (!line.startsWith('data: ')) continue
        let event: Record<string, unknown>
        try {
          event = JSON.parse(line.slice(6))
        } catch {
          continue
        }

        const type = event.type as string
        if (type === 'done') break
        if (type === 'text') {
          // Accumulate consecutive text blocks into the last text message
          const last = messages.value[messages.value.length - 1]
          if (last?.type === 'text') {
            last.content = (last.content ?? '') + (event.content as string)
            await scrollToBottom()
          } else {
            pushMessage({ type: 'text', content: event.content as string })
          }
        } else if (type === 'tool_call') {
          pushMessage({
            type: 'tool_call',
            name: event.name as string,
            input: event.input as Record<string, unknown>,
          })
        } else if (type === 'tool_result') {
          pushMessage({
            type: 'tool_result',
            name: event.name as string,
            result: event.result as Record<string, unknown>,
          })
        } else if (type === 'error') {
          pushMessage({ type: 'error', content: event.content as string })
        }
      }
    }
  } catch (err: unknown) {
    pushMessage({ type: 'error', content: err instanceof Error ? err.message : 'Request failed' })
  } finally {
    loading.value = false
    scrollToBottom()
  }
}
</script>
