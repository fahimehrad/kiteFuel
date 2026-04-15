<template>
  <div class="flex flex-col gap-4 p-5 h-full overflow-y-auto">

    <!-- ── Heading ─────────────────────────────────────────────────── -->
    <div class="flex items-center justify-between">
      <h2 class="text-sm font-semibold text-gray-300 uppercase tracking-wider">Demo Runner</h2>
      <div class="flex gap-2">
        <button
          @click="handleReset"
          :disabled="running"
          class="text-xs px-3 py-1.5 rounded-md border border-gray-700 text-gray-400 hover:text-gray-200 hover:border-gray-500 disabled:opacity-40 disabled:cursor-not-allowed transition"
        >
          ↺ Reset Demo
        </button>
        <button
          @click="handleRun"
          :disabled="running || complete"
          class="text-xs px-3 py-1.5 rounded-md bg-purple-600 hover:bg-purple-500 text-white font-medium disabled:opacity-40 disabled:cursor-not-allowed transition flex items-center gap-1.5"
        >
          <span v-if="running" class="inline-block w-2.5 h-2.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
          <span v-else>▶</span>
          Run Full Demo
        </button>
      </div>
    </div>

    <!-- ── Progress bar ─────────────────────────────────────────────── -->
    <div class="space-y-1.5">
      <div class="flex justify-between items-center">
        <span class="text-xs text-gray-400">{{ currentLabel }}</span>
        <span class="text-xs text-gray-600">{{ progressPct }}%</span>
      </div>
      <div class="w-full h-1.5 bg-gray-800 rounded-full overflow-hidden">
        <div
          class="h-full bg-purple-500 rounded-full transition-all duration-500"
          :style="{ width: progressPct + '%' }"
        />
      </div>
    </div>

    <!-- ── Step list ─────────────────────────────────────────────────── -->
    <ol class="space-y-1">
      <li
        v-for="(step, i) in STEPS"
        :key="step.label"
        class="flex items-center gap-3 text-xs"
      >
        <!-- icon -->
        <span
          :class="[
            'w-4 h-4 rounded-full flex items-center justify-center flex-shrink-0 text-[10px]',
            i < currentStep  ? 'bg-green-600 text-white'   :
            i === currentStep && running ? 'bg-purple-600 text-white animate-pulse' :
            i === currentStep && !running && !complete ? 'bg-purple-800 text-purple-300' :
                                 'bg-gray-800 text-gray-600',
          ]"
        >
          {{ i < currentStep ? '✓' : String(i + 1) }}
        </span>
        <span
          :class="[
            i < currentStep  ? 'text-green-400'  :
            i === currentStep ? 'text-purple-300' :
                                'text-gray-600',
          ]"
        >{{ step.label }}</span>
      </li>
    </ol>

    <!-- ── Error area ─────────────────────────────────────────────────── -->
    <div
      v-if="error"
      class="bg-red-950 border border-red-800 rounded-lg px-4 py-3 text-xs text-red-300"
    >
      ⚠ {{ error }}
    </div>

    <!-- ── Success banner ─────────────────────────────────────────────── -->
    <div
      v-if="complete"
      class="bg-green-950 border border-green-700 rounded-lg px-4 py-3 space-y-2"
    >
      <p class="text-sm font-semibold text-green-300">✅ Demo Complete</p>
      <a
        v-if="contractAddress"
        :href="`https://testnet.kitescan.ai/address/${contractAddress}`"
        target="_blank"
        rel="noopener noreferrer"
        class="inline-block text-xs text-blue-400 hover:text-blue-300 underline underline-offset-2 font-mono break-all"
      >
        View contract on KiteScan ↗
      </a>
    </div>

  </div>

  <!-- ── X402 Payment Modal ─────────────────────────────────────────── -->
  <X402PaymentModal
    :open="modalOpen"
    :requirements="paymentRequirements"
    :loading="confirmingPayment"
    @confirm="onPaymentConfirm"
    @cancel="onPaymentCancel"
  />
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useTaskStore } from '../stores/taskStore'
import X402PaymentModal from './X402PaymentModal.vue'

// ---------------------------------------------------------------------------
// Local types
// ---------------------------------------------------------------------------

interface BuyDataResponse {
  payment_required?: boolean
  requirements?: PaymentRequirements | null
  // regular MutationResponse fields may also be present
  [key: string]: unknown
}

interface PaymentRequirements {
  accepts?: PaymentAccept[]
  [key: string]: unknown
}

interface PaymentAccept {
  merchantName?: string
  maxAmountRequired?: string | number
  asset?: string
  payTo?: string
  network?: string
  [key: string]: unknown
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string) ?? 'http://localhost:8000'

async function apiFetch<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : {},
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    let detail = res.statusText
    try { const j = await res.json(); detail = j?.detail ?? JSON.stringify(j) } catch { /* ignore */ }
    throw new Error(`[${method} ${path}] HTTP ${res.status}: ${detail}`)
  }
  return res.json() as Promise<T>
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DELAY_MS = 1500

const STEPS = [
  { label: 'Create Task' },
  { label: 'Request Credit' },
  { label: 'Approve Credit' },
  { label: 'Fund Escrow' },
  { label: 'Buy Data (x402)' },
  { label: 'Generate Report' },
  { label: 'User Payment' },
  { label: 'Settle & Repay' },
] as const

// Step indices (matching STEPS array)
const STEP_IDX = {
  CREATE_TASK:      0,
  REQUEST_CREDIT:   1,
  APPROVE_CREDIT:   2,
  FUND_ESCROW:      3,
  BUY_DATA:         4,
  GENERATE_REPORT:  5,
  USER_PAYMENT:     6,
  SETTLE:           7,
} as const

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

const store = useTaskStore()

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

const running             = ref(false)
const currentStep         = ref(0)
const currentLabel        = ref('Ready')
const error               = ref<string | null>(null)
const complete            = ref(false)

const modalOpen           = ref(false)
const paymentRequirements = ref<PaymentRequirements | null>(null)
const pendingTaskId       = ref<string | null>(null)
const confirmingPayment   = ref(false)

// ---------------------------------------------------------------------------
// Emits
// ---------------------------------------------------------------------------

const emit = defineEmits<{
  (e: 'running-change', value: boolean): void
}>()

// Token resolver — set when pausing for payment modal
let resolvePayment: ((token: string | null) => void) | null = null

// Notify parent whenever running state changes
watch(running, (val) => emit('running-change', val))

// ---------------------------------------------------------------------------
// Derived
// ---------------------------------------------------------------------------

const contractAddress = import.meta.env.VITE_CONTRACT_ADDRESS as string | undefined

const progressPct = computed(() => {
  if (complete.value) return 100
  return Math.round((currentStep.value / STEPS.length) * 100)
})

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function delay(ms: number) {
  return new Promise<void>(resolve => setTimeout(resolve, ms))
}

function setStep(idx: number) {
  currentStep.value = idx
  currentLabel.value = STEPS[idx]?.label ?? ''
}

/**
 * Pause the demo and wait for the payment modal to resolve.
 * Returns the pasted token string, or null if cancelled.
 */
function waitForPaymentToken(requirements: any, taskId: string): Promise<string | null> {
  paymentRequirements.value = requirements
  pendingTaskId.value = taskId
  modalOpen.value = true

  return new Promise<string | null>(resolve => {
    resolvePayment = resolve
  })
}

// ---------------------------------------------------------------------------
// Modal event handlers
// ---------------------------------------------------------------------------

async function onPaymentConfirm(token: string) {
  if (!resolvePayment) return
  confirmingPayment.value = true
  error.value = null
  try {
    const taskId = pendingTaskId.value!
    // POST /tasks/{id}/buy-data/confirm  with body { payment_token }
    await apiFetch('POST', `/tasks/${taskId}/buy-data/confirm`, { payment_token: token })
    // Refresh store
    await Promise.all([store.fetchTasks(), store.fetchTask(taskId)])
    // Success — close modal and let the runner proceed
    modalOpen.value = false
    resolvePayment(token)
    resolvePayment = null
  } catch (err: unknown) {
    // Keep modal open so the user can retry with a different token
    error.value = err instanceof Error ? err.message : 'buy-data/confirm failed'
    // Do NOT close modal, do NOT call resolvePayment — demo stays paused
  } finally {
    confirmingPayment.value = false
  }
}

function onPaymentCancel() {
  modalOpen.value = false
  if (resolvePayment) {
    resolvePayment(null)
    resolvePayment = null
  }
}

// ---------------------------------------------------------------------------
// Demo runner
// ---------------------------------------------------------------------------

async function handleRun() {
  if (running.value || complete.value) return

  running.value = true
  error.value   = null
  complete.value = false
  currentStep.value = 0
  currentLabel.value = 'Starting…'

  try {
    // ── Step 1: Create Task ─────────────────────────────────────────
    setStep(STEP_IDX.CREATE_TASK)
    await store.createTask()
    if (store.error) throw new Error(store.error)

    const taskId = store.selectedTaskId
    if (!taskId) throw new Error('No task ID after creation')

    await delay(DELAY_MS)

    // ── Step 2: Request Credit ──────────────────────────────────────
    setStep(STEP_IDX.REQUEST_CREDIT)
    await store.runAction(taskId, 'request-credit')
    if (store.error) throw new Error(store.error)
    await delay(DELAY_MS)

    // ── Step 3: Approve Credit ──────────────────────────────────────
    setStep(STEP_IDX.APPROVE_CREDIT)
    await store.runAction(taskId, 'approve-credit')
    if (store.error) throw new Error(store.error)
    await delay(DELAY_MS)

    // ── Step 4: Fund Escrow ─────────────────────────────────────────
    setStep(STEP_IDX.FUND_ESCROW)
    await store.runAction(taskId, 'fund')
    if (store.error) throw new Error(store.error)
    await delay(DELAY_MS)

    // ── Step 5: Buy Data (x402 two-step) ────────────────────────────
    setStep(STEP_IDX.BUY_DATA)
    currentLabel.value = 'Buy Data — requesting…'

    // Hit the backend buy-data endpoint directly so we can inspect the response
    let buyDataResp: BuyDataResponse
    try {
      buyDataResp = await apiFetch<BuyDataResponse>('POST', `/tasks/${taskId}/buy-data`)
    } catch (err: unknown) {
      throw new Error(err instanceof Error ? err.message : 'buy-data failed')
    }

    // Refresh lists after first call
    await Promise.all([store.fetchTasks(), store.fetchTask(taskId)])

    if (buyDataResp && (buyDataResp as any).payment_required === true) {
      // x402 path — pause and open modal
      currentLabel.value = 'Buy Data — waiting for x402 token…'
      const requirements = (buyDataResp as any).requirements ?? null
      const token = await waitForPaymentToken(requirements, taskId)

      if (token === null) {
        throw new Error('x402 payment cancelled')
      }
      // onPaymentConfirm already called buy-data/confirm and refreshed the store
    } else {
      // Direct success — no payment gate (e.g. mock backend without x402)
      // Nothing extra needed; task state already updated above
    }

    await delay(DELAY_MS)

    // ── Step 6: Generate Report ─────────────────────────────────────
    setStep(STEP_IDX.GENERATE_REPORT)
    await store.runAction(taskId, 'generate-report')
    if (store.error) throw new Error(store.error)
    await delay(DELAY_MS)

    // ── Step 7: User Payment ────────────────────────────────────────
    setStep(STEP_IDX.USER_PAYMENT)
    await store.runAction(taskId, 'user-pay')
    if (store.error) throw new Error(store.error)
    await delay(DELAY_MS)

    // ── Step 8: Settle & Repay ──────────────────────────────────────
    setStep(STEP_IDX.SETTLE)
    await store.runAction(taskId, 'settle')
    if (store.error) throw new Error(store.error)

    // ── Done ─────────────────────────────────────────────────────────
    currentStep.value = STEPS.length // push beyond last index (all dots green)
    currentLabel.value = 'All steps complete'
    complete.value = true

  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : 'Demo failed'
  } finally {
    running.value = false
  }
}

// ---------------------------------------------------------------------------
// Reset
// ---------------------------------------------------------------------------

async function handleReset() {
  if (running.value) return
  error.value    = null
  complete.value = false
  currentStep.value  = 0
  currentLabel.value = 'Ready'
  modalOpen.value    = false
  paymentRequirements.value = null
  pendingTaskId.value = null
  resolvePayment = null

  await store.resetDemo()
}
</script>
