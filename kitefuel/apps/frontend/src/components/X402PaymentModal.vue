<template>
  <!-- Modal overlay -->
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-50 flex items-center justify-center"
      role="dialog"
      aria-modal="true"
      aria-labelledby="x402-modal-title"
    >
      <!-- Backdrop -->
      <div class="absolute inset-0 bg-black/70 backdrop-blur-sm" />

      <!-- Panel -->
      <div class="relative z-10 w-full max-w-md mx-4 bg-gray-950 border border-gray-800 rounded-xl shadow-2xl flex flex-col">

        <!-- Header -->
        <div class="flex items-center justify-between px-6 py-4 border-b border-gray-800">
          <h2
            id="x402-modal-title"
            class="text-base font-semibold text-purple-300 flex items-center gap-2"
          >
            <span class="text-purple-400">⚡</span>
            x402 Payment Required
          </h2>
          <button
            @click="$emit('cancel')"
            class="text-gray-500 hover:text-gray-300 transition text-xl leading-none"
            aria-label="Close"
          >×</button>
        </div>

        <!-- Body -->
        <div class="px-6 py-5 space-y-5 overflow-y-auto max-h-[70vh]">

          <!-- Payment details -->
          <div class="bg-gray-900 border border-gray-800 rounded-lg p-4 space-y-2">
            <h3 class="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
              Payment Details
            </h3>

            <div v-if="paymentInfo" class="space-y-2">
              <!-- Merchant Name -->
              <div v-if="paymentInfo.merchantName" class="flex justify-between items-center">
                <span class="text-xs text-gray-500">Merchant</span>
                <span class="text-xs text-gray-200 font-medium">{{ paymentInfo.merchantName }}</span>
              </div>

              <!-- Max Amount -->
              <div v-if="paymentInfo.maxAmountRequired != null" class="flex justify-between items-center">
                <span class="text-xs text-gray-500">Max Amount</span>
                <span class="text-xs text-yellow-300 font-semibold font-mono">{{ paymentInfo.maxAmountRequired }}</span>
              </div>

              <!-- Asset -->
              <div v-if="paymentInfo.asset" class="flex justify-between items-center">
                <span class="text-xs text-gray-500">Asset</span>
                <span class="text-xs text-gray-300 font-mono">{{ shortenAddress(paymentInfo.asset) }}</span>
              </div>

              <!-- Pay To -->
              <div v-if="paymentInfo.payTo" class="flex justify-between items-center">
                <span class="text-xs text-gray-500">Pay To</span>
                <span class="text-xs text-gray-300 font-mono">{{ shortenAddress(paymentInfo.payTo) }}</span>
              </div>

              <!-- Network -->
              <div v-if="paymentInfo.network" class="flex justify-between items-center">
                <span class="text-xs text-gray-500">Network</span>
                <span class="text-xs text-blue-300">{{ paymentInfo.network }}</span>
              </div>
            </div>

            <!-- Fallback when requirements not available -->
            <p v-else class="text-xs text-gray-500 italic">Payment requirements not available.</p>
          </div>

          <!-- Token textarea -->
          <div class="space-y-2">
            <label for="payment-token" class="block text-xs font-medium text-gray-300">
              X-PAYMENT Token
            </label>
            <textarea
              id="payment-token"
              v-model="tokenInput"
              rows="4"
              placeholder="Paste your X-PAYMENT token here…"
              class="w-full bg-gray-900 border border-gray-700 focus:border-purple-500 focus:ring-1 focus:ring-purple-500 rounded-md px-3 py-2 text-xs text-gray-200 placeholder-gray-600 font-mono resize-none outline-none transition"
            />
            <p class="text-xs text-gray-600">
              Obtain this token from Kite Passport via MCP, then paste it above.
            </p>
          </div>

          <!-- Collapsible help section -->
          <div class="border border-gray-800 rounded-lg overflow-hidden">
            <button
              @click="helpOpen = !helpOpen"
              class="w-full flex items-center justify-between px-4 py-3 text-left bg-gray-900 hover:bg-gray-800 transition"
              :aria-expanded="helpOpen"
            >
              <span class="text-xs font-medium text-gray-400">How to get this token</span>
              <span class="text-gray-500 text-xs transition-transform duration-200" :class="helpOpen ? 'rotate-180' : ''">▼</span>
            </button>
            <div v-if="helpOpen" class="px-4 py-3 bg-gray-950 border-t border-gray-800">
              <p class="text-xs text-gray-400 leading-relaxed">
                Connect your Kite Passport via MCP in Claude Desktop or Cursor.<br />
                Your agent will call <code class="text-purple-300">approve_payment()</code> and return an X-PAYMENT token.<br />
                Paste it here to complete the purchase.
              </p>
            </div>
          </div>

        </div>

        <!-- Footer -->
        <div class="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-800">
          <button
            @click="$emit('cancel')"
            class="text-sm text-gray-400 hover:text-gray-200 px-4 py-2 rounded-md transition"
          >
            Cancel
          </button>
          <button
            @click="handleConfirm"
            :disabled="isConfirmDisabled"
            class="text-sm bg-purple-600 hover:bg-purple-500 disabled:opacity-40 disabled:cursor-not-allowed text-white px-5 py-2 rounded-md font-medium transition flex items-center gap-2"
          >
            <span v-if="loading" class="inline-block w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            Confirm Payment
          </button>
        </div>

      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'

// ---------------------------------------------------------------------------
// Props & Emits
// ---------------------------------------------------------------------------

const props = defineProps<{
  open: boolean
  requirements: any | null
  loading?: boolean
}>()

const emit = defineEmits<{
  (e: 'confirm', paymentToken: string): void
  (e: 'cancel'): void
}>()

// ---------------------------------------------------------------------------
// Local state
// ---------------------------------------------------------------------------

const tokenInput = ref('')
const helpOpen   = ref(false)

// ---------------------------------------------------------------------------
// Derived payment info (safe access from requirements.accepts[0])
// ---------------------------------------------------------------------------

const paymentInfo = computed(() => {
  try {
    const accepts = props.requirements?.accepts
    if (Array.isArray(accepts) && accepts.length > 0) return accepts[0]
    return null
  } catch {
    return null
  }
})

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Shorten an address or hex string: 0x1234...abcd */
function shortenAddress(value: string): string {
  if (!value || typeof value !== 'string') return value
  if (value.length <= 12) return value
  return `${value.slice(0, 6)}...${value.slice(-4)}`
}

const isConfirmDisabled = computed(() =>
  !tokenInput.value.trim() || !!props.loading
)

// ---------------------------------------------------------------------------
// Reset textarea when modal opens
// ---------------------------------------------------------------------------

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      tokenInput.value = ''
      helpOpen.value   = false
    }
  }
)

// ---------------------------------------------------------------------------
// Escape key → cancel
// ---------------------------------------------------------------------------

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && props.open) {
    emit('cancel')
  }
}

onMounted(()  => document.addEventListener('keydown', onKeydown))
onUnmounted(() => document.removeEventListener('keydown', onKeydown))

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------

function handleConfirm() {
  const token = tokenInput.value.trim()
  if (!token || props.loading) return
  emit('confirm', token)
}
</script>
