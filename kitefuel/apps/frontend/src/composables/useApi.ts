// ---------------------------------------------------------------------------
// Types matching the backend response shapes
// ---------------------------------------------------------------------------

export interface TaskSummary {
  id: string
  state: string
  created_at: string | null
  next_action: string | null
}

export interface StateTransitionRecord {
  id: number
  from_state: string
  to_state: string
  timestamp: string | null
  note: string | null
}

export interface CreditOfferRecord {
  id: number
  lender_address: string
  credit_amount: number
  repay_amount: number
}

export interface EscrowPositionRecord {
  id: number
  contract_address: string
  tx_hash: string
  state: string
}

export interface DataPurchaseRecord {
  id: number
  provider: string
  amount: number
  result_summary: string
  purchased_at: string | null
}

export interface RepaymentRecord {
  id: number
  lender_paid: number
  remainder_released: number
  settled_at: string | null
}

export interface TaskDetail {
  task: TaskSummary & { updated_at: string | null }
  next_action: string | null
  message: string
  credit_offers: CreditOfferRecord[]
  escrow_positions: EscrowPositionRecord[]
  data_purchases: DataPurchaseRecord[]
  repayment_records: RepaymentRecord[]
  state_transitions: StateTransitionRecord[]
}

export interface TaskListResponse {
  tasks: TaskSummary[]
  count: number
}

export interface MutationResponse {
  task: TaskSummary & { updated_at: string | null }
  next_action: string | null
  message: string
}

export interface DeleteResponse {
  message: string
  deleted: number
}

// ---------------------------------------------------------------------------
// Internal fetch helper
// ---------------------------------------------------------------------------

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string) ?? 'http://localhost:8000'

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : {},
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (!res.ok) {
    let detail = res.statusText
    try {
      const json = await res.json()
      detail = json?.detail ?? JSON.stringify(json)
    } catch {
      // ignore parse errors — use statusText
    }
    throw new Error(`[${method} ${path}] HTTP ${res.status}: ${detail}`)
  }

  return res.json() as Promise<T>
}

// ---------------------------------------------------------------------------
// Composable
// ---------------------------------------------------------------------------

export function useApi() {
  return {
    getTasks: ()                           => request<TaskListResponse>('GET',    '/tasks'),
    getTask:  (id: string)                 => request<TaskDetail>('GET',          `/tasks/${id}`),
    postAction:(id: string, action: string)=> request<MutationResponse>('POST',   `/tasks/${id}/${action}`),
    createTask: ()                         => request<MutationResponse>('POST',   '/tasks'),
    resetDemo:  ()                         => request<DeleteResponse>('DELETE',   '/tasks/all'),
  }
}
