export type TaskState =
  | 'task_created'
  | 'credit_requested'
  | 'credit_approved'
  | 'funds_locked'
  | 'data_purchased'
  | 'result_generated'
  | 'user_paid'
  | 'lender_repaid'
  | 'task_closed'
  | 'task_failed'

export interface Task {
  id: string
  state: TaskState
  created_at: string
  next_action: string | null
}

export interface CreditOffer {
  task_id: string
  lender_address: string
  credit_amount: number
  repay_amount: number
}

export interface EscrowPosition {
  task_id: string
  contract_address: string
  tx_hash: string
  state: string
}

export interface DataPurchase {
  task_id: string
  provider: string
  amount: number
  result_summary: string
}

export interface RepaymentRecord {
  task_id: string
  lender_paid: number
  remainder_released: number
  settled_at: string
}
