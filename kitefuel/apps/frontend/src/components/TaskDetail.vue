<template>
  <!-- Empty state -->
  <div v-if="!task" class="flex-1 flex items-center justify-center text-gray-600 text-sm">
    Select a task from the left panel to view details.
  </div>

  <!-- Detail view -->
  <div v-else class="flex flex-1 overflow-hidden gap-0">

    <!-- LEFT: State timeline + action button (65%) -->
    <div class="flex flex-col w-[65%] border-r border-gray-800 overflow-y-auto px-6 py-5 space-y-6">

      <!-- Action button -->
      <div v-if="nextAction" class="flex items-center gap-3">
        <span class="text-sm text-gray-400">Next:</span>
        <button
          @click="handleAction"
          :disabled="store.loading"
          class="text-sm bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white px-5 py-2 rounded-md font-medium transition"
        >
          {{ nextAction }}
        </button>
      </div>
      <div v-else class="text-sm text-green-400 font-medium">✅ Task complete</div>

      <!-- State timeline -->
      <ol class="relative border-l border-gray-700 space-y-0 ml-3">
        <li
          v-for="(step, i) in timeline"
          :key="step.state"
          class="ml-5 pb-7 last:pb-0"
        >
          <!-- Dot -->
          <span
            :class="[
              'absolute -left-[10px] flex items-center justify-center w-5 h-5 rounded-full ring-2 ring-gray-950 text-xs',
              step.status === 'done'    ? 'bg-green-600 text-white'    :
              step.status === 'active'  ? 'bg-purple-600 text-white'   :
                                          'bg-gray-700 text-gray-500',
            ]"
          >
            {{ step.status === 'done' ? '✓' : step.status === 'active' ? '●' : String(i + 1) }}
          </span>

          <!-- Content -->
          <div :class="step.status === 'future' ? 'opacity-40' : ''">
            <div class="flex items-center gap-2">
              <span
                :class="[
                  'text-sm font-medium',
                  step.status === 'done'   ? 'text-green-300' :
                  step.status === 'active' ? 'text-purple-300' :
                                             'text-gray-500',
                ]"
              >{{ step.label }}</span>
              <span v-if="step.timestamp" class="text-xs text-gray-600">{{ step.timestamp }}</span>
            </div>
            <p v-if="step.detail" class="text-xs text-gray-500 mt-0.5">{{ step.detail }}</p>
          </div>
        </li>
      </ol>

    </div>

    <!-- RIGHT: Agent identity + explainers (35%) -->
    <div class="flex flex-col w-[35%] overflow-y-auto px-5 py-5 space-y-4">

      <!-- Agent Identity card -->
      <div class="bg-gray-900 border border-gray-800 rounded-lg p-4 space-y-2">
        <h3 class="text-xs font-semibold text-gray-400 uppercase tracking-wider">Agent Identity (Delegated Authority)</h3>
        <div class="text-xs text-gray-300 space-y-1">
          <div>
            <span class="text-gray-500">DID: </span>
            <span class="font-mono">did:kite:agent:demo</span>
          </div>
          <div>
            <span class="text-gray-500">Max spend: </span>
            <span>{{ agentMaxSpend }}</span>
          </div>
          <div>
            <span class="text-gray-500">Provider scope: </span>
            <span>MockDataProvider</span>
          </div>
          <div>
            <span class="text-gray-500">Session: </span>
            <span class="text-yellow-300">Active for this task only</span>
          </div>
        </div>
      </div>

      <!-- Explainer: Why credit? -->
      <div class="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <h4 class="text-xs font-semibold text-purple-400 mb-1">Why credit?</h4>
        <p class="text-xs text-gray-400 leading-relaxed">
          The agent needed working capital to purchase market data before the user's payment arrived.
          KiteFuel fronts that capital as a programmable credit line, enabling the agent to act immediately.
        </p>
      </div>

      <!-- Explainer: Lender safety -->
      <div class="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <h4 class="text-xs font-semibold text-blue-400 mb-1">Lender safety</h4>
        <p class="text-xs text-gray-400 leading-relaxed">
          Funds are held in the <code class="text-gray-300">KiteFuelEscrow</code> smart contract.
          The lender's repayment is enforced on-chain before any remainder is released to the borrower.
        </p>
      </div>

      <!-- Explainer: Enforcement -->
      <div class="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <h4 class="text-xs font-semibold text-green-400 mb-1">Enforcement</h4>
        <p class="text-xs text-gray-400 leading-relaxed">
          On settlement, <code class="text-gray-300">settle()</code> pays the lender first from available revenue.
          The borrower only receives the remainder if revenue exceeds <code class="text-gray-300">repayAmount</code>.
          If revenue falls short, the borrower receives nothing — the lender is always prioritised.
        </p>
      </div>

      <!-- Transaction summary (optional) -->
      <div v-if="txSummaryLines.length" class="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <h4 class="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Transactions</h4>
        <ul class="space-y-1">
          <li v-for="(line, i) in txSummaryLines" :key="i" class="text-xs text-gray-400 font-mono truncate">
            {{ line }}
          </li>
        </ul>
      </div>

    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useTaskStore } from '../stores/taskStore'
import type { TaskDetail, StateTransitionRecord } from '../composables/useApi'

const store = useTaskStore()

// ---------------------------------------------------------------------------
// Typed convenience refs
// ---------------------------------------------------------------------------

const detail = computed(() => store.selectedTask)
const task   = computed(() => detail.value?.task ?? null)

// ---------------------------------------------------------------------------
// next_action → backend route segment
// ---------------------------------------------------------------------------

const ACTION_ROUTE: Record<string, string> = {
  'Request Credit':  'request-credit',
  'Approve Credit':  'approve-credit',
  'Fund Escrow':     'fund',
  'Buy Data':        'buy-data',
  'Generate Report': 'generate-report',
  'User Payment':    'user-pay',
  'Settle':          'settle',
}

const nextAction = computed<string | null>(() => detail.value?.next_action ?? null)

function handleAction() {
  if (!task.value || !nextAction.value) return
  const route = ACTION_ROUTE[nextAction.value]
  if (!route) return
  store.runAction(task.value.id, route)
}

// ---------------------------------------------------------------------------
// Agent identity helper
// ---------------------------------------------------------------------------

const agentMaxSpend = computed<string>(() => {
  const offer = detail.value?.credit_offers?.[0]
  if (!offer) return '—'
  return `${offer.credit_amount} ETH`
})

// ---------------------------------------------------------------------------
// State timeline
// ---------------------------------------------------------------------------

const ORDERED_STATES = [
  'task_created',
  'credit_requested',
  'credit_approved',
  'funds_locked',
  'data_purchased',
  'result_generated',
  'user_paid',
  'lender_repaid',
  'task_closed',
] as const

const STATE_LABELS: Record<string, string> = {
  task_created:     'Task Created',
  credit_requested: 'Credit Requested',
  credit_approved:  'Credit Approved',
  funds_locked:     'Escrow Funded',
  data_purchased:   'Data Purchased',
  result_generated: 'Report Generated',
  user_paid:        'User Paid',
  lender_repaid:    'Lender Repaid',
  task_closed:      'Task Closed',
}

type StepStatus = 'done' | 'active' | 'future'

interface TimelineStep {
  state: string
  label: string
  status: StepStatus
  timestamp: string | null
  detail: string | null
}

function tsFor(state: string, transitions: StateTransitionRecord[]): string | null {
  const t = transitions.find(tr => tr.to_state === state)
  if (!t?.timestamp) return null
  return new Date(t.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function detailFor(state: string, d: TaskDetail): string | null {
  switch (state) {
    case 'funds_locked': {
      const escrow = d.escrow_positions?.[0]
      if (!escrow?.tx_hash) return null
      return `tx: ${escrow.tx_hash.slice(0, 10)}…`
    }
    case 'data_purchased': {
      const purchase = d.data_purchases?.[0]
      if (!purchase) return null
      return `${purchase.provider} · ${purchase.amount} ETH`
    }
    case 'user_paid': {
      const t = d.state_transitions?.find(tr => tr.to_state === 'user_paid')
      return t?.note ?? null
    }
    case 'lender_repaid': {
      const rep = d.repayment_records?.[0]
      if (!rep) return null
      return `Lender received ${rep.lender_paid} ETH · remainder ${rep.remainder_released} ETH`
    }
    default:
      return null
  }
}

const timeline = computed<TimelineStep[]>(() => {
  const d = detail.value
  if (!d) return []

  const currentState = task.value?.state ?? ''
  const currentIdx = ORDERED_STATES.indexOf(currentState as typeof ORDERED_STATES[number])

  return ORDERED_STATES.map((state, i) => {
    const status: StepStatus =
      i < currentIdx  ? 'done'   :
      i === currentIdx ? 'active' :
                         'future'

    return {
      state,
      label: STATE_LABELS[state] ?? state,
      status,
      timestamp: status !== 'future' ? tsFor(state, d.state_transitions ?? []) : null,
      detail:    status === 'done'   ? detailFor(state, d) : null,
    }
  })
})

// ---------------------------------------------------------------------------
// Transaction summary lines
// ---------------------------------------------------------------------------

const txSummaryLines = computed<string[]>(() => {
  const d = detail.value
  if (!d) return []
  const lines: string[] = []
  const escrow = d.escrow_positions?.[0]
  if (escrow?.tx_hash) lines.push(`Fund:   ${escrow.tx_hash.slice(0, 18)}…`)
  const settle = d.state_transitions?.find(tr => tr.to_state === 'lender_repaid')
  if (settle?.note) {
    const m = settle.note.match(/tx=(\S+)/)
    if (m) lines.push(`Settle: ${m[1].slice(0, 18)}…`)
  }
  return lines
})
</script>
