export type RiskLevel = 'low' | 'medium' | 'high'
export type ReviewStatus = 'Needs review' | 'In review' | 'Resolved'

export interface Transaction {
  id: string
  timestamp: string
  amount: number
  channel: 'Wire' | 'Card' | 'ACH' | 'Mobile'
  riskScore: number
  riskLevel: RiskLevel
  recommendedAction: string
  indicators: string[]
  processingTimestamp: string
}

export interface Metrics {
  transactionsProcessed: number
  highRiskTransactions: number
  alertsGenerated: number
  averageLatencyMs: number
}

export interface Alert {
  id: string
  transactionId: string
  riskScore: number
  reason: string
  nextStep: string
  status: ReviewStatus
}

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? ''

export async function getTransactions(): Promise<Transaction[]> {
  const response = await fetch(`${apiBaseUrl}/api/transactions`)
  if (!response.ok) throw new Error('Transactions unavailable')
  return response.json()
}

export async function predictTransaction(payload: unknown): Promise<unknown> {
  const response = await fetch(`${apiBaseUrl}/api/predict`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) throw new Error('Prediction request failed')
  return response.json()
}

export async function getMetrics(): Promise<Metrics> {
  const response = await fetch(`${apiBaseUrl}/api/metrics`)
  if (!response.ok) throw new Error('Metrics unavailable')
  return response.json()
}

export async function getAlerts(): Promise<Alert[]> {
  const response = await fetch(`${apiBaseUrl}/api/alerts`)
  if (!response.ok) throw new Error('Alerts unavailable')
  return response.json()
}
