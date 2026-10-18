/**
 * SentinelZ AI Frontend API Client
 * Connects directly to the FastAPI Backend services for transaction risk intelligence.
 * Strictly typed against FastAPI Pydantic response models.
 */

export type RiskLevel = 'low' | 'medium' | 'high'
export type ReviewStatus = 'Needs review' | 'In review' | 'Resolved'
export type Channel = 'Wire' | 'Card' | 'ACH' | 'Mobile'

export interface TimeSeriesPoint {
  time: string
  value: number
}

export interface Transaction {
  id: string
  timestamp: string
  amount: number
  channel: Channel
  riskScore: number
  riskLevel: RiskLevel
  recommendedAction: string
  indicators: string[]
  processingTimestamp: string
  processedBy?: string
}

export interface Metrics {
  transactionsProcessed: number
  highRiskTransactions: number
  alertsGenerated: number
  averageLatencyMs: number
  volumeData?: TimeSeriesPoint[]
  latencyData?: TimeSeriesPoint[]
}

export interface Alert {
  id: string
  transactionId: string
  riskScore: number
  reason: string
  nextStep: string
  status: ReviewStatus
}

export interface PredictionRequest {
  amount: number
  channel: Channel
  customerId?: string
  merchantCategory?: string
  customerBaseline?: number
  recentTransactionCount?: number
  timeSincePreviousSeconds?: number
  locationCountry?: string
}

export interface PredictionResponse {
  transactionId?: string
  riskScore: number
  riskLevel: RiskLevel
  modelProbability: number
  recommendedAction: string
  indicators: string[]
  reviewStatus?: ReviewStatus
  inferenceLatencyMs: number
  modelVersion: string
  syntheticDisclosure: string
}

export type ScenarioName =
  | 'normal'
  | 'unusual_amount'
  | 'velocity_burst'
  | 'elevated_device_risk'
  | 'cross_border_wire'

export interface SimulationRequest {
  scenario?: ScenarioName
  seed?: number
}

export interface SimulationResponse {
  transaction: Transaction
  alert?: Alert | null
  inferenceLatencyMs: number
  processingLatencyMs: number
  scenario: string
  syntheticDisclosure: string
  processedBy?: string
}

export interface ModelPerformance {
  status: string
  modelVersion: string
  precision: number | null
  recall: number | null
  f1Score: number | null
  falsePositiveRate: number | null
  prAuc: number | null
  rocAuc?: number | null
  confusionMatrix: Record<string, number> | null
  datasetDisclosures: string
}

export interface AuditRecord {
  id: string
  timestamp: string
  action: string
  details: string
  actor: string
}

export interface IBMZAdapterStatus {
  status: string
  connection: string
  details: string
  mode?: string
  capabilities?: string[]
  targetHost?: string
}

export interface HealthResponse {
  status: string
  version: string
  uptimeSeconds: number
  modelStatus: string
  databaseStatus: string
  ibmZAdapter: IBMZAdapterStatus
}

export interface EngineConfig {
  high_risk_threshold: number
  medium_risk_threshold: number
  amount_anomaly_multiplier: number
  amount_elevated_multiplier: number
  velocity_burst_tx_per_hour: number
  velocity_elevated_tx_per_hour: number
  rapid_cadence_seconds: number
  device_risk_threshold: number
  high_value_channel_amount: number
  high_risk_merchants: string[]
  action_high: string
  action_medium: string
  action_low: string
}

export class ApiError extends Error {
  status: number
  detail?: string

  constructor(message: string, status: number, detail?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

const apiBaseUrl = (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000').replace(/\/+$/, '')

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${apiBaseUrl}${path}`
  let response: Response

  try {
    response = await fetch(url, {
      ...options,
      headers: {
        'Accept': 'application/json',
        ...(options?.body ? { 'Content-Type': 'application/json' } : {}),
        ...options?.headers,
      },
    })
  } catch (err) {
    const errorMsg = err instanceof Error ? err.message : 'Network failure'
    throw new ApiError(
      `SentinelZ AI backend unreachable at ${apiBaseUrl} (${errorMsg}). Ensure the backend service is running on port 8000.`,
      0
    )
  }

  if (!response.ok) {
    let errorDetail = response.statusText
    try {
      const errJson = await response.json()
      if (errJson && typeof errJson.detail === 'string') {
        errorDetail = errJson.detail
      } else if (errJson && Array.isArray(errJson.errors)) {
        errorDetail = errJson.errors.join('; ')
      }
    } catch {
      // response body was not valid JSON
    }
    throw new ApiError(errorDetail || `HTTP error ${response.status}`, response.status, errorDetail)
  }

  return response.json() as Promise<T>
}

// --- API Service Functions ---

export async function getHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>('/api/health')
}

export async function getTransactions(params?: {
  riskLevel?: RiskLevel
  channel?: Channel
  limit?: number
}): Promise<Transaction[]> {
  const queryParams = new URLSearchParams()
  if (params?.riskLevel) queryParams.set('riskLevel', params.riskLevel)
  if (params?.channel) queryParams.set('channel', params.channel)
  if (params?.limit) queryParams.set('limit', params.limit.toString())
  const qs = queryParams.toString()
  return apiFetch<Transaction[]>(`/api/transactions${qs ? `?${qs}` : ''}`)
}

export async function getTransaction(transactionId: string): Promise<Transaction> {
  return apiFetch<Transaction>(`/api/transactions/${encodeURIComponent(transactionId)}`)
}

export async function simulateTransaction(payload?: SimulationRequest): Promise<SimulationResponse> {
  return apiFetch<SimulationResponse>('/api/transactions/simulate', {
    method: 'POST',
    body: JSON.stringify(payload || {}),
  })
}

export async function predictTransaction(payload: PredictionRequest): Promise<PredictionResponse> {
  return apiFetch<PredictionResponse>('/api/predict', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function getMetrics(): Promise<Metrics> {
  return apiFetch<Metrics>('/api/metrics')
}

export async function getAlerts(status?: ReviewStatus): Promise<Alert[]> {
  const queryParams = new URLSearchParams()
  if (status) queryParams.set('status', status)
  const qs = queryParams.toString()
  return apiFetch<Alert[]>(`/api/alerts${qs ? `?${qs}` : ''}`)
}

export async function getAuditTrail(limit?: number): Promise<AuditRecord[]> {
  const qs = limit ? `?limit=${limit}` : ''
  return apiFetch<AuditRecord[]>(`/api/audit${qs}`)
}

export async function getModelPerformance(): Promise<ModelPerformance> {
  return apiFetch<ModelPerformance>('/api/model/performance')
}

export async function updateAlertStatus(alertId: string, status: ReviewStatus): Promise<Alert> {
  return apiFetch<Alert>(`/api/alerts/${encodeURIComponent(alertId)}`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  })
}

export async function getEngineConfig(): Promise<EngineConfig> {
  return apiFetch<EngineConfig>('/api/engine/config')
}
