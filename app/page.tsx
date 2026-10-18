'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  Bell,
  Check,
  CheckCircle2,
  ChevronDown,
  Clock3,
  Cpu,
  Database,
  ExternalLink,
  FileText,
  Filter,
  HelpCircle,
  Info,
  LayoutDashboard,
  Menu,
  MoreHorizontal,
  RefreshCw,
  Search,
  Server,
  Settings as SettingsIcon,
  ShieldAlert,
  ShieldCheck,
  Sliders,
  Sparkles,
  Target,
  TrendingUp,
  Wifi,
  WifiOff,
  X,
} from 'lucide-react'
import {
  Area,
  AreaChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import {
  getAlerts,
  getAuditTrail,
  getEngineConfig,
  getHealth,
  getMetrics,
  getModelPerformance,
  getTransactions,
  simulateTransaction,
  updateAlertStatus,
  type Alert,
  type AuditRecord,
  type Channel,
  type EngineConfig,
  type HealthResponse,
  type Metrics,
  type ModelPerformance,
  type ReviewStatus,
  type RiskLevel,
  type ScenarioName,
  type Transaction,
} from '@/lib/api'

function RiskBadge({ level }: { level: RiskLevel }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${
        level === 'high'
          ? 'border-red-400/20 bg-red-400/10 text-red-300'
          : level === 'medium'
            ? 'border-amber-400/20 bg-amber-400/10 text-amber-300'
            : 'border-emerald-400/20 bg-emerald-400/10 text-emerald-300'
      }`}
    >
      <span className="size-1.5 rounded-full bg-current" />
      {level}
    </span>
  )
}

function StatusBadge({ status }: { status: ReviewStatus }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-[11px] font-semibold ${
        status === 'In review'
          ? 'border-amber-400/20 bg-amber-400/10 text-amber-300'
          : status === 'Resolved'
            ? 'border-emerald-400/20 bg-emerald-400/10 text-emerald-300'
            : 'border-red-400/20 bg-red-400/10 text-red-300'
      }`}
    >
      <span className="size-1.5 rounded-full bg-current" />
      {status}
    </span>
  )
}

function Panel({
  title,
  eyebrow,
  children,
  className = '',
}: {
  title: string
  eyebrow?: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <section
      className={`rounded-xl border border-white/[0.08] bg-[#111b2b] shadow-[0_12px_30px_rgba(0,0,0,0.18)] ${className}`}
    >
      <div className="flex items-start justify-between border-b border-white/[0.07] px-5 py-4">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-sky-400">
            {eyebrow ?? 'Monitoring'}
          </p>
          <h2 className="mt-1 text-sm font-semibold text-slate-100">{title}</h2>
        </div>
        <MoreHorizontal className="size-4 text-slate-500" />
      </div>
      {children}
    </section>
  )
}

const SCENARIOS: { id: ScenarioName; label: string; description: string }[] = [
  {
    id: 'normal',
    label: 'Normal Activity',
    description: 'Routine customer spending matching historical baseline with known device.',
  },
  {
    id: 'unusual_amount',
    label: 'Unusual Amount',
    description: 'Transaction monetary value significantly deviates from historical average.',
  },
  {
    id: 'velocity_burst',
    label: 'Velocity Burst',
    description: 'Multiple rapid transactions initiated within a tight 10–45s cadence window.',
  },
  {
    id: 'elevated_device_risk',
    label: 'Elevated Device Risk',
    description: 'Transaction initiated from an unrecognized proxy profile or risky device score.',
  },
  {
    id: 'cross_border_wire',
    label: 'Cross-Border Wire',
    description: 'High-value wire transfer into foreign destination or high-risk merchant.',
  },
]

type ActiveTab =
  | 'overview'
  | 'transactions'
  | 'risk-analysis'
  | 'alerts'
  | 'performance'
  | 'audit'
  | 'health'
  | 'settings'

export default function Page() {
  // Live State
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [selected, setSelected] = useState<Transaction | null>(null)
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [performance, setPerformance] = useState<ModelPerformance | null>(null)
  const [auditLogs, setAuditLogs] = useState<AuditRecord[]>([])
  const [engineConfig, setEngineConfig] = useState<EngineConfig | null>(null)

  // UI Control State
  const [activeTab, setActiveTab] = useState<ActiveTab>('overview')
  const [riskFilter, setRiskFilter] = useState<'all' | RiskLevel>('all')
  const [channelFilter, setChannelFilter] = useState<'all' | Channel>('all')
  const [alertStatusFilter, setAlertStatusFilter] = useState<'all' | ReviewStatus>('all')
  const [query, setQuery] = useState('')
  const [mobileOpen, setMobileOpen] = useState(false)
  const [selectedScenario, setSelectedScenario] = useState<ScenarioName>('normal')

  // Telemetry & Network State
  const [isSimulating, setIsSimulating] = useState(false)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [initialLoading, setInitialLoading] = useState(true)
  const [backendConnected, setBackendConnected] = useState<boolean | null>(null)
  const [lastUpdated, setLastUpdated] = useState<string>('Syncing...')
  const [statusMessage, setStatusMessage] = useState<{
    type: 'success' | 'error' | 'info'
    title: string
    detail: string
  } | null>(null)

  const isFetchingRef = useRef(false)

  // Filtered transactions for search, risk level, and channel
  const filtered = useMemo(() => {
    return transactions.filter(
      (tx) =>
        (riskFilter === 'all' || tx.riskLevel === riskFilter) &&
        (channelFilter === 'all' || tx.channel === channelFilter) &&
        (tx.id.toLowerCase().includes(query.toLowerCase()) ||
          tx.channel.toLowerCase().includes(query.toLowerCase()) ||
          tx.recommendedAction.toLowerCase().includes(query.toLowerCase()))
    )
  }, [transactions, riskFilter, channelFilter, query])

  // Filtered alerts
  const filteredAlerts = useMemo(() => {
    return alerts.filter(
      (a) => alertStatusFilter === 'all' || a.status === alertStatusFilter
    )
  }, [alerts, alertStatusFilter])

  // Dynamic Risk Distribution derived strictly from stored records
  const riskDistribution = useMemo(() => {
    const total = transactions.length
    if (total === 0) {
      return {
        data: [
          { name: 'Low', value: 0 },
          { name: 'Medium', value: 0 },
          { name: 'High', value: 0 },
        ],
        lowPct: '0%',
        medPct: '0%',
        highPct: '0%',
      }
    }
    const low = transactions.filter((t) => t.riskLevel === 'low').length
    const med = transactions.filter((t) => t.riskLevel === 'medium').length
    const high = transactions.filter((t) => t.riskLevel === 'high').length

    return {
      data: [
        { name: 'Low', value: low },
        { name: 'Medium', value: med },
        { name: 'High', value: high },
      ],
      lowPct: `${Math.round((low / total) * 100)}%`,
      medPct: `${Math.round((med / total) * 100)}%`,
      highPct: `${Math.round((high / total) * 100)}%`,
    }
  }, [transactions])

  // Centralized Data Fetcher
  const fetchDashboardData = async (isManual = false) => {
    if (isFetchingRef.current) return
    isFetchingRef.current = true

    if (isManual) setIsRefreshing(true)

    try {
      const [hRes, txRes, mRes, aRes, pRes, audRes, cfgRes] = await Promise.all([
        getHealth(),
        getTransactions({ limit: 100 }),
        getMetrics(),
        getAlerts(),
        getModelPerformance(),
        getAuditTrail(40),
        getEngineConfig().catch(() => null),
      ])

      setHealth(hRes)
      setTransactions(txRes)
      setMetrics(mRes)
      setAlerts(aRes)
      setPerformance(pRes)
      setAuditLogs(audRes)
      if (cfgRes) setEngineConfig(cfgRes)
      setBackendConnected(true)

      // Ensure a selected transaction exists
      setSelected((prev) => {
        if (!prev && txRes.length > 0) return txRes[0]
        const match = txRes.find((t) => t.id === prev?.id)
        return match || (txRes.length > 0 ? txRes[0] : null)
      })

      const now = new Date()
      setLastUpdated(now.toTimeString().split(' ')[0] + ' UTC')
    } catch (err) {
      setBackendConnected(false)
      const msg = err instanceof Error ? err.message : 'Backend connection error'
      setStatusMessage({
        type: 'error',
        title: 'Backend Disconnected',
        detail: msg,
      })
    } finally {
      isFetchingRef.current = false
      setInitialLoading(false)
      if (isManual) setIsRefreshing(false)
    }
  }

  // Polling loop (every 4 seconds)
  useEffect(() => {
    fetchDashboardData()
    const interval = setInterval(() => {
      fetchDashboardData()
    }, 4000)

    return () => clearInterval(interval)
  }, [])

  // Execute Live Simulation via POST /api/transactions/simulate
  const handleSimulate = async () => {
    if (isSimulating) return
    setIsSimulating(true)
    setStatusMessage(null)

    try {
      const response = await simulateTransaction({ scenario: selectedScenario })
      const newTx = response.transaction

      setTransactions((prev) => [newTx, ...prev.filter((t) => t.id !== newTx.id)])
      setSelected(newTx)

      if (response.alert) {
        const newAlert = response.alert
        setAlerts((prev) => [newAlert, ...prev.filter((a) => a.id !== newAlert.id)])
      }

      const alertNotice = response.alert
        ? ` · Triggered Alert ${response.alert.id} (${response.alert.status})`
        : ' · No alert generated (low risk)'

      setStatusMessage({
        type: 'success',
        title: `Simulated: ${newTx.id} (${response.scenario})`,
        detail: `Amount: $${newTx.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })} ${newTx.channel} · Risk Score: ${newTx.riskScore} (${newTx.riskLevel}) · Action: ${newTx.recommendedAction} · Latency: ${response.processingLatencyMs}ms${alertNotice}`,
      })

      const [mRes, audRes] = await Promise.all([getMetrics(), getAuditTrail(40)])
      setMetrics(mRes)
      setAuditLogs(audRes)
    } catch (err) {
      const errorDetail = err instanceof Error ? err.message : 'Simulation failed'
      setStatusMessage({
        type: 'error',
        title: 'Simulation Failed',
        detail: errorDetail,
      })
    } finally {
      setIsSimulating(false)
    }
  }

  // Update Alert Review Status (persisted to SQLite backend)
  const handleUpdateAlertStatus = async (alertId: string, newStatus: ReviewStatus) => {
    try {
      const updated = await updateAlertStatus(alertId, newStatus)
      setAlerts((prev) => prev.map((a) => (a.id === updated.id ? updated : a)))
      const [audRes, mRes] = await Promise.all([getAuditTrail(40), getMetrics()])
      setAuditLogs(audRes)
      setMetrics(mRes)
      setStatusMessage({
        type: 'success',
        title: `Alert ${alertId} Updated`,
        detail: `Status successfully updated to '${newStatus}' and recorded in audit log.`,
      })
    } catch (err) {
      const errorDetail = err instanceof Error ? err.message : 'Failed to update alert'
      setStatusMessage({
        type: 'error',
        title: 'Status Update Failed',
        detail: errorDetail,
      })
    }
  }

  return (
    <div className="min-h-screen bg-[#09111f] text-slate-200">
      {/* Sidebar Navigation */}
      <aside
        className={`fixed inset-y-0 left-0 z-20 flex w-64 flex-col border-r border-white/[0.07] bg-[#0c1626] transition-transform lg:translate-x-0 ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex h-20 items-center gap-3 border-b border-white/[0.07] px-6">
          <div className="flex size-9 items-center justify-center rounded-lg bg-sky-400 text-[#07111f]">
            <ShieldCheck className="size-5" />
          </div>
          <div>
            <div className="text-[15px] font-bold tracking-tight text-white">
              SentinelZ <span className="text-sky-400">AI</span>
            </div>
            <p className="text-[9px] uppercase tracking-[0.16em] text-slate-500">
              IBM Z Datathon 2026
            </p>
          </div>
          <button
            onClick={() => setMobileOpen(false)}
            aria-label="Close menu"
            className="ml-auto text-slate-400 lg:hidden"
          >
            <X className="size-4" />
          </button>
        </div>

        <nav className="flex flex-1 flex-col gap-1 px-3 py-4 overflow-y-auto">
          {[
            { id: 'overview', icon: LayoutDashboard, label: 'Overview' },
            { id: 'transactions', icon: Activity, label: 'Transactions' },
            { id: 'risk-analysis', icon: Target, label: 'Risk Analysis' },
            { id: 'alerts', icon: Bell, label: 'Alerts Queue', badge: alerts.filter((a) => a.status === 'Needs review').length },
            { id: 'performance', icon: TrendingUp, label: 'Model Evaluation' },
            { id: 'audit', icon: FileText, label: 'Audit Trail', badge: auditLogs.length },
            { id: 'health', icon: Server, label: 'System Health' },
            { id: 'settings', icon: SettingsIcon, label: 'Settings & Policy' },
          ].map((item) => {
            const Icon = item.icon
            const isActive = activeTab === item.id
            return (
              <button
                key={item.id}
                onClick={() => {
                  setActiveTab(item.id as ActiveTab)
                  setMobileOpen(false)
                }}
                className={`flex items-center gap-3 rounded-lg px-3 py-2 text-left text-xs transition-colors ${
                  isActive
                    ? 'bg-sky-400/10 font-semibold text-sky-300'
                    : 'text-slate-400 hover:bg-white/[0.04] hover:text-slate-200'
                }`}
              >
                <Icon className="size-4" />
                {item.label}
                {item.badge !== undefined && item.badge > 0 && (
                  <span
                    className={`ml-auto rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                      item.id === 'alerts'
                        ? 'bg-red-400/20 text-red-300'
                        : 'bg-white/10 text-slate-300'
                    }`}
                  >
                    {item.badge}
                  </span>
                )}
              </button>
            )
          })}

          <div className="my-3 border-t border-white/[0.07]" />

          {/* IBM Z Integration Badge in Sidebar */}
          <div className="space-y-2 rounded-lg border border-white/[0.07] bg-white/[0.025] p-3">
            <p className="text-[10px] uppercase tracking-wider text-slate-500">Platform Deployment</p>
            <div className="flex items-center gap-2 text-xs text-slate-300">
              <span
                className={`size-2 rounded-full ${
                  health?.status === 'healthy' ? 'bg-emerald-400' : 'bg-amber-400'
                }`}
              />
              <span className="truncate">
                {health ? `Model ${health.modelStatus.split(' ')[0]}` : 'Connecting...'}
              </span>
            </div>
            <div className="flex items-center gap-2 text-[11px] text-slate-400">
              <Cpu
                className={`size-3 ${
                  health?.ibmZAdapter?.status === 'connected'
                    ? 'text-emerald-400'
                    : health?.ibmZAdapter?.status === 'configured'
                      ? 'text-sky-400'
                      : 'text-amber-400'
                }`}
              />
              <span className="capitalize">
                IBM Z: {health?.ibmZAdapter?.mode ?? 'local_simulation'}
              </span>
            </div>
            <p className="text-[9px] leading-tight text-slate-500">
              {health?.ibmZAdapter?.details ??
                'Local verification mode. Mainframe adapter ready for LinuxONE s390x.'}
            </p>
          </div>
        </nav>

        <div className="border-t border-white/[0.07] p-4 text-[10px] text-slate-500">
          FastAPI & Next.js · SQLite WAL
        </div>
      </aside>

      {mobileOpen && (
        <button
          aria-label="Close navigation"
          onClick={() => setMobileOpen(false)}
          className="fixed inset-0 z-10 bg-black/50 lg:hidden"
        />
      )}

      {/* Main Content Area */}
      <main className="lg:pl-64">
        {/* Sticky Header */}
        <header className="sticky top-0 z-10 flex h-20 items-center justify-between border-b border-white/[0.07] bg-[#09111f]/95 px-5 backdrop-blur-xl md:px-8">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setMobileOpen(true)}
              aria-label="Open menu"
              className="lg:hidden text-slate-400"
            >
              <Menu className="size-5" />
            </button>
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-sky-400">
                Command center
              </p>
              <h1 className="text-lg font-semibold tracking-tight text-white capitalize">
                {activeTab === 'overview' && 'Executive Risk Overview'}
                {activeTab === 'transactions' && 'Transaction Explorer'}
                {activeTab === 'risk-analysis' && 'Explainable Risk Analysis'}
                {activeTab === 'alerts' && 'Alert Management Queue'}
                {activeTab === 'performance' && 'Model Evaluation & Benchmarks'}
                {activeTab === 'audit' && 'System Audit Trail'}
                {activeTab === 'health' && 'System Health & IBM Z Integration'}
                {activeTab === 'settings' && 'Decision Engine Policies & Settings'}
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {backendConnected === true ? (
              <div className="flex items-center gap-2 rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-1.5 text-[11px] text-emerald-300">
                <span className="size-1.5 rounded-full bg-emerald-400 animate-pulse" />
                <span className="hidden sm:inline">Backend connected</span>
                <span className="sm:hidden">Live</span>
              </div>
            ) : backendConnected === false ? (
              <div className="flex items-center gap-2 rounded-full border border-red-400/20 bg-red-400/10 px-3 py-1.5 text-[11px] text-red-300">
                <span className="size-1.5 rounded-full bg-red-400" />
                <span className="hidden sm:inline">Backend unreachable (port 8000)</span>
                <span className="sm:hidden">Offline</span>
              </div>
            ) : (
              <div className="flex items-center gap-2 rounded-full border border-amber-400/20 bg-amber-400/10 px-3 py-1.5 text-[11px] text-amber-300">
                <span className="size-1.5 rounded-full bg-amber-400" />
                <span>Connecting...</span>
              </div>
            )}

            <span className="hidden text-xs text-slate-500 xl:inline">
              Updated {lastUpdated}
            </span>

            <button
              onClick={() => fetchDashboardData(true)}
              disabled={isRefreshing}
              title="Refresh live data from backend"
              className="flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.03] px-2.5 py-1.5 text-xs text-slate-300 hover:bg-white/[0.08] disabled:opacity-50"
            >
              <RefreshCw className={`size-3.5 ${isRefreshing ? 'animate-spin text-sky-400' : ''}`} />
              <span className="hidden sm:inline">Refresh</span>
            </button>
          </div>
        </header>

        {/* Status Toast / Banner */}
        {statusMessage && (
          <div
            className={`border-b px-5 py-3 text-xs md:px-8 flex items-start justify-between gap-3 ${
              statusMessage.type === 'success'
                ? 'border-emerald-400/30 bg-emerald-400/10 text-emerald-200'
                : statusMessage.type === 'error'
                  ? 'border-red-400/30 bg-red-400/10 text-red-200'
                  : 'border-sky-400/30 bg-sky-400/10 text-sky-200'
            }`}
          >
            <div>
              <p className="font-semibold">{statusMessage.title}</p>
              <p className="mt-0.5 text-[11px] opacity-90">{statusMessage.detail}</p>
            </div>
            <button
              onClick={() => setStatusMessage(null)}
              aria-label="Dismiss notice"
              className="text-xs opacity-70 hover:opacity-100"
            >
              <X className="size-4" />
            </button>
          </div>
        )}

        <div className="mx-auto max-w-[1600px] space-y-6 p-5 md:p-8">
          {/* Universal Simulation Bar (Available across all tabs) */}
          <div className="flex flex-col justify-between gap-4 rounded-xl border border-white/[0.08] bg-[#111b2b] p-5 md:flex-row md:items-center">
            <div>
              <div className="flex items-center gap-2">
                <Sparkles className="size-4 text-sky-400" />
                <h3 className="text-sm font-semibold text-white">Live Transaction Simulator</h3>
                <span className="rounded bg-sky-400/15 px-2 py-0.5 text-[10px] font-medium text-sky-300">
                  Interactive Pipeline
                </span>
              </div>
              <p className="mt-1 text-xs text-slate-400">
                Trigger real synthetic transactions through the Random Forest pipeline, decision engine, and SQLite persistence.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-2">
                <label htmlFor="scenario-select" className="text-xs text-slate-400">
                  Scenario:
                </label>
                <select
                  id="scenario-select"
                  value={selectedScenario}
                  onChange={(e) => setSelectedScenario(e.target.value as ScenarioName)}
                  disabled={isSimulating}
                  className="rounded-lg border border-white/10 bg-[#0c1626] px-3 py-2 text-xs text-slate-200 outline-none focus:border-sky-400/50"
                >
                  {SCENARIOS.map((sc) => (
                    <option key={sc.id} value={sc.id}>
                      {sc.label}
                    </option>
                  ))}
                </select>
              </div>

              <button
                onClick={handleSimulate}
                disabled={isSimulating || backendConnected === false}
                className="flex items-center gap-2 rounded-lg bg-sky-400 px-4 py-2 text-xs font-semibold text-[#07111f] transition-all hover:bg-sky-300 disabled:opacity-50"
              >
                {isSimulating ? (
                  <>
                    <RefreshCw className="size-3.5 animate-spin" />
                    <span>Processing pipeline...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="size-3.5" />
                    <span>Simulate Transaction</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* ========================================================================= */}
          {/* TAB 1: OVERVIEW DASHBOARD */}
          {/* ========================================================================= */}
          {activeTab === 'overview' && (
            <div className="space-y-6">
              {/* KPI Metrics Cards */}
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                {[
                  {
                    label: 'Transactions processed',
                    value: metrics ? metrics.transactionsProcessed.toLocaleString() : '—',
                    sub: 'Persisted in SQLite database',
                    color: 'bg-sky-400',
                  },
                  {
                    label: 'High-risk transactions',
                    value: metrics ? metrics.highRiskTransactions.toLocaleString() : '—',
                    sub: `${riskDistribution.highPct} of processed volume`,
                    color: 'bg-red-400',
                  },
                  {
                    label: 'Active alerts generated',
                    value: metrics ? metrics.alertsGenerated.toLocaleString() : '—',
                    sub: `${alerts.filter((a) => a.status === 'Needs review').length} pending investigation`,
                    color: 'bg-amber-400',
                  },
                  {
                    label: 'Avg. processing latency',
                    value: metrics ? `${metrics.averageLatencyMs.toFixed(1)} ms` : '—',
                    sub: 'Measured via time.perf_counter()',
                    color: 'bg-emerald-400',
                  },
                ].map((kpi) => (
                  <div key={kpi.label} className="rounded-xl border border-white/[0.08] bg-[#111b2b] p-5">
                    <div className="flex items-center justify-between">
                      <p className="text-xs text-slate-400">{kpi.label}</p>
                      <span className={`size-2 rounded-full ${kpi.color}`} />
                    </div>
                    <div className="mt-3 flex items-end justify-between">
                      <p className="text-2xl font-semibold tracking-tight text-white">
                        {initialLoading ? (
                          <span className="inline-block h-7 w-20 animate-pulse rounded bg-white/10" />
                        ) : (
                          kpi.value
                        )}
                      </p>
                    </div>
                    <p className="mt-2 text-[10px] uppercase tracking-wider text-slate-500">{kpi.sub}</p>
                  </div>
                ))}
              </div>

              {/* Charts Row: Volume and Risk Distribution */}
              <div className="grid gap-6 xl:grid-cols-[minmax(0,1.65fr)_minmax(320px,0.8fr)]">
                <Panel title="Transaction Volume" eyebrow="Real-time Activity">
                  <div className="h-56 p-4">
                    {metrics?.volumeData && metrics.volumeData.length > 0 ? (
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={metrics.volumeData}>
                          <defs>
                            <linearGradient id="volume" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="0%" stopColor="#38bdf8" stopOpacity={0.3} />
                              <stop offset="100%" stopColor="#38bdf8" stopOpacity={0} />
                            </linearGradient>
                          </defs>
                          <CartesianGrid stroke="#ffffff0d" vertical={false} />
                          <XAxis
                            dataKey="time"
                            axisLine={false}
                            tickLine={false}
                            tick={{ fill: '#64748b', fontSize: 10 }}
                          />
                          <YAxis
                            axisLine={false}
                            tickLine={false}
                            tick={{ fill: '#64748b', fontSize: 10 }}
                          />
                          <Tooltip
                            contentStyle={{
                              background: '#111b2b',
                              border: '1px solid #ffffff1a',
                              borderRadius: 8,
                              fontSize: 11,
                            }}
                          />
                          <Area
                            type="monotone"
                            dataKey="value"
                            name="Cumulative Volume"
                            stroke="#38bdf8"
                            strokeWidth={2}
                            fill="url(#volume)"
                          />
                        </AreaChart>
                      </ResponsiveContainer>
                    ) : (
                      <div className="flex h-full flex-col items-center justify-center text-center">
                        <p className="text-xs text-slate-500">No volume telemetry recorded yet.</p>
                        <p className="mt-1 text-[11px] text-slate-600">
                          Run simulations above to generate live transaction series.
                        </p>
                      </div>
                    )}
                  </div>
                </Panel>

                <Panel title="Risk Level Distribution" eyebrow="Stored Transactions">
                  <div className="flex items-center gap-5 p-5">
                    <div className="h-32 w-32">
                      <ResponsiveContainer>
                        <PieChart>
                          <Pie
                            data={riskDistribution.data}
                            dataKey="value"
                            innerRadius={42}
                            outerRadius={60}
                            strokeWidth={0}
                          >
                            <Cell fill="#34d399" />
                            <Cell fill="#fbbf24" />
                            <Cell fill="#f87171" />
                          </Pie>
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                    <div className="flex flex-col gap-3 text-xs">
                      {[
                        { label: 'Low', val: riskDistribution.lowPct, color: 'bg-emerald-400' },
                        { label: 'Medium', val: riskDistribution.medPct, color: 'bg-amber-400' },
                        { label: 'High', val: riskDistribution.highPct, color: 'bg-red-400' },
                      ].map((item) => (
                        <div key={item.label} className="flex items-center gap-2">
                          <span className={`size-2 rounded-full ${item.color}`} />
                          <span className="w-14 text-slate-400">{item.label}</span>
                          <b className="text-slate-200">{item.val}</b>
                        </div>
                      ))}
                    </div>
                  </div>
                </Panel>
              </div>

              {/* Quick Split: Recent Transactions & Alerts */}
              <div className="grid gap-6 xl:grid-cols-2">
                <Panel title="Recent Transactions" eyebrow="Live Stream">
                  <div className="overflow-x-auto p-4">
                    <table className="w-full text-left text-xs">
                      <thead className="text-[10px] uppercase tracking-wider text-slate-500 border-b border-white/[0.05]">
                        <tr>
                          <th className="pb-2">ID</th>
                          <th className="pb-2">Amount</th>
                          <th className="pb-2">Channel</th>
                          <th className="pb-2">Risk</th>
                          <th className="pb-2">Action</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/[0.03]">
                        {transactions.slice(0, 5).map((tx) => (
                          <tr
                            key={tx.id}
                            onClick={() => {
                              setSelected(tx)
                              setActiveTab('risk-analysis')
                            }}
                            className="cursor-pointer hover:bg-white/[0.02]"
                          >
                            <td className="py-2.5 font-mono text-sky-400">{tx.id}</td>
                            <td className="py-2.5 text-slate-200">
                              ${tx.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                            </td>
                            <td className="py-2.5 text-slate-400">{tx.channel}</td>
                            <td className="py-2.5">
                              <RiskBadge level={tx.riskLevel} />
                            </td>
                            <td className="py-2.5 text-slate-300">{tx.recommendedAction}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    <div className="mt-3 flex justify-end">
                      <button
                        onClick={() => setActiveTab('transactions')}
                        className="text-xs text-sky-400 hover:text-sky-300 flex items-center gap-1"
                      >
                        Open Transaction Explorer <ArrowUpRight className="size-3" />
                      </button>
                    </div>
                  </div>
                </Panel>

                <Panel title="Priority Alert Queue" eyebrow="Needs Review">
                  <div className="divide-y divide-white/[0.05] p-4">
                    {alerts.filter((a) => a.status === 'Needs review').slice(0, 3).map((a) => (
                      <div key={a.id} className="py-3 first:pt-0 last:pb-0">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <AlertTriangle className="size-3.5 text-red-400" />
                            <span className="font-mono text-xs text-sky-300">{a.transactionId}</span>
                            <span className="text-[10px] text-slate-500">{a.id}</span>
                          </div>
                          <span className="text-xs font-semibold text-red-300">Score {a.riskScore}</span>
                        </div>
                        <p className="mt-1 text-xs text-slate-300">{a.reason}</p>
                        <div className="mt-2 flex items-center justify-between">
                          <span className="text-[10px] text-slate-500">Next: {a.nextStep}</span>
                          <button
                            onClick={() => handleUpdateAlertStatus(a.id, 'In review')}
                            className="rounded bg-sky-400/10 px-2 py-0.5 text-[10px] text-sky-300 hover:bg-sky-400/20"
                          >
                            Start Review
                          </button>
                        </div>
                      </div>
                    ))}
                    {alerts.filter((a) => a.status === 'Needs review').length === 0 && (
                      <p className="py-6 text-center text-xs text-slate-500">No active alerts requiring review.</p>
                    )}
                    <div className="pt-3 flex justify-end">
                      <button
                        onClick={() => setActiveTab('alerts')}
                        className="text-xs text-sky-400 hover:text-sky-300 flex items-center gap-1"
                      >
                        Open Alert Center <ArrowUpRight className="size-3" />
                      </button>
                    </div>
                  </div>
                </Panel>
              </div>
            </div>
          )}

          {/* ========================================================================= */}
          {/* TAB 2: TRANSACTION EXPLORER */}
          {/* ========================================================================= */}
          {activeTab === 'transactions' && (
            <div className="space-y-6">
              <Panel title="Transaction Explorer & Search" eyebrow="Persistent Archive">
                {/* Search & Multi-filter Controls */}
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[0.07] p-4">
                  <div className="relative min-w-56 flex-1">
                    <Search className="absolute left-3 top-2.5 size-3.5 text-slate-500" />
                    <input
                      aria-label="Search transactions"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                      placeholder="Search transaction ID, channel, action..."
                      className="w-full rounded-md border border-white/10 bg-white/[0.03] py-2 pl-9 pr-3 text-xs text-slate-200 outline-none placeholder:text-slate-600 focus:border-sky-400/50"
                    />
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    {/* Risk Level Filter */}
                    <div className="flex gap-1 rounded-md border border-white/10 bg-white/[0.02] p-1">
                      <button
                        onClick={() => setRiskFilter('all')}
                        className={`rounded px-2.5 py-1 text-[11px] ${
                          riskFilter === 'all' ? 'bg-white/10 text-white' : 'text-slate-500'
                        }`}
                      >
                        All Risk
                      </button>
                      {(['high', 'medium', 'low'] as RiskLevel[]).map((level) => (
                        <button
                          key={level}
                          onClick={() => setRiskFilter(level)}
                          className={`rounded px-2.5 py-1 text-[11px] capitalize ${
                            riskFilter === level ? 'bg-white/10 text-white' : 'text-slate-500'
                          }`}
                        >
                          {level}
                        </button>
                      ))}
                    </div>

                    {/* Channel Filter */}
                    <div className="flex gap-1 rounded-md border border-white/10 bg-white/[0.02] p-1">
                      <button
                        onClick={() => setChannelFilter('all')}
                        className={`rounded px-2.5 py-1 text-[11px] ${
                          channelFilter === 'all' ? 'bg-white/10 text-white' : 'text-slate-500'
                        }`}
                      >
                        All Channels
                      </button>
                      {(['Wire', 'Card', 'ACH', 'Mobile'] as Channel[]).map((ch) => (
                        <button
                          key={ch}
                          onClick={() => setChannelFilter(ch)}
                          className={`rounded px-2.5 py-1 text-[11px] ${
                            channelFilter === ch ? 'bg-white/10 text-white' : 'text-slate-500'
                          }`}
                        >
                          {ch}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Table */}
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="text-[10px] uppercase tracking-wider text-slate-500 border-b border-white/[0.05]">
                      <tr>
                        <th className="px-4 py-3 font-medium">Transaction</th>
                        <th className="px-4 py-3 font-medium">Time</th>
                        <th className="px-4 py-3 font-medium">Amount</th>
                        <th className="px-4 py-3 font-medium">Channel</th>
                        <th className="px-4 py-3 font-medium">Risk Score</th>
                        <th className="px-4 py-3 font-medium">Policy Action</th>
                        <th className="px-4 py-3 font-medium">Execution Engine</th>
                        <th className="px-4 py-3 font-medium">Details</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/[0.03]">
                      {filtered.length === 0 ? (
                        <tr>
                          <td colSpan={8} className="py-8 text-center text-slate-500">
                            No transactions match the filter criteria.
                          </td>
                        </tr>
                      ) : (
                        filtered.map((tx) => (
                          <tr
                            key={tx.id}
                            onClick={() => setSelected(tx)}
                            className={`cursor-pointer transition-colors hover:bg-white/[0.035] ${
                              selected?.id === tx.id ? 'bg-sky-400/[0.08]' : ''
                            }`}
                          >
                            <td className="whitespace-nowrap px-4 py-3 font-medium text-sky-300">
                              {tx.id}
                            </td>
                            <td className="whitespace-nowrap px-4 py-3 font-mono text-[11px] text-slate-400">
                              {tx.timestamp}
                            </td>
                            <td className="whitespace-nowrap px-4 py-3 text-slate-200 font-medium">
                              ${tx.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                            </td>
                            <td className="px-4 py-3 text-slate-400">{tx.channel}</td>
                            <td className="px-4 py-3">
                              <div className="flex items-center gap-2">
                                <span
                                  className={`font-semibold ${
                                    tx.riskLevel === 'high'
                                      ? 'text-red-300'
                                      : tx.riskLevel === 'medium'
                                        ? 'text-amber-300'
                                        : 'text-emerald-300'
                                  }`}
                                >
                                  {tx.riskScore}
                                </span>
                                <RiskBadge level={tx.riskLevel} />
                              </div>
                            </td>
                            <td className="whitespace-nowrap px-4 py-3 text-slate-300">
                              {tx.recommendedAction}
                            </td>
                            <td className="whitespace-nowrap px-4 py-3 font-mono text-[10px] text-slate-400">
                              {tx.processedBy || 'sentinelz_local'}
                            </td>
                            <td className="whitespace-nowrap px-4 py-3">
                              <button
                                onClick={(e) => {
                                  e.stopPropagation()
                                  setSelected(tx)
                                  setActiveTab('risk-analysis')
                                }}
                                className="rounded bg-sky-400/10 px-2 py-1 text-[11px] text-sky-300 hover:bg-sky-400/20"
                              >
                                Analyze &rarr;
                              </button>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>

                <div className="flex items-center justify-between px-4 py-3 text-[10px] text-slate-500">
                  <span>
                    Showing {filtered.length} of {transactions.length} persisted records
                  </span>
                  <span>Bounded to latest 100 entries for client stability</span>
                </div>
              </Panel>
            </div>
          )}

          {/* ========================================================================= */}
          {/* TAB 3: EXPLAINABLE RISK ANALYSIS */}
          {/* ========================================================================= */}
          {activeTab === 'risk-analysis' && (
            <div className="space-y-6">
              {selected ? (
                <div className="space-y-6">
                  {/* Transaction Overview Header */}
                  <div className="flex flex-col justify-between gap-4 rounded-xl border border-white/[0.08] bg-[#111b2b] p-6 md:flex-row md:items-center">
                    <div>
                      <div className="flex items-center gap-3">
                        <h2 className="font-mono text-xl font-bold text-sky-300">{selected.id}</h2>
                        <RiskBadge level={selected.riskLevel} />
                        <span className="rounded bg-white/[0.06] px-2 py-0.5 text-xs font-mono text-slate-400">
                          {selected.channel}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-slate-400">
                        Processed at {selected.processingTimestamp} · Engine: {selected.processedBy || 'sentinelz_local'}
                      </p>
                    </div>

                    <div className="flex items-center gap-4">
                      <div className="text-right">
                        <p className="text-[10px] uppercase tracking-wider text-slate-500">Normalized Score</p>
                        <p className="text-2xl font-bold text-white">{selected.riskScore} <span className="text-xs text-slate-500">/ 100</span></p>
                      </div>
                      <div className="text-right border-l border-white/10 pl-4">
                        <p className="text-[10px] uppercase tracking-wider text-slate-500">Policy Action</p>
                        <p className="text-sm font-semibold text-sky-300">{selected.recommendedAction}</p>
                      </div>
                    </div>
                  </div>

                  {/* Explainable 4-Pillar Breakdown */}
                  <div className="grid gap-6 md:grid-cols-2">
                    {/* Pillar 1: Observable Features */}
                    <Panel title="Pillar 1: Observable Transaction Attributes" eyebrow="Feature Extraction">
                      <div className="p-5 space-y-3 text-xs">
                        <div className="flex justify-between py-1.5 border-b border-white/[0.04]">
                          <span className="text-slate-400">Amount</span>
                          <span className="font-semibold text-slate-200">
                            ${selected.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                          </span>
                        </div>
                        <div className="flex justify-between py-1.5 border-b border-white/[0.04]">
                          <span className="text-slate-400">Payment Channel</span>
                          <span className="font-semibold text-slate-200">{selected.channel}</span>
                        </div>
                        <div className="flex justify-between py-1.5 border-b border-white/[0.04]">
                          <span className="text-slate-400">Execution Origin</span>
                          <span className="font-mono text-sky-300">{selected.processedBy || 'sentinelz_local'}</span>
                        </div>
                        <div className="flex justify-between py-1.5 border-b border-white/[0.04]">
                          <span className="text-slate-400">Initiation Timestamp</span>
                          <span className="font-mono text-slate-400">{selected.timestamp}</span>
                        </div>
                        <p className="mt-2 text-[10px] text-slate-500">
                          Observable attributes are fed directly into the Random Forest feature matrix without data leakage.
                        </p>
                      </div>
                    </Panel>

                    {/* Pillar 2: Deterministic Evidence Signals */}
                    <Panel title="Pillar 2: Triggered Risk Indicators" eyebrow="Rule Evaluation">
                      <div className="p-5 space-y-3">
                        <p className="text-xs text-slate-400">
                          Evidence-based rules evaluate observable features against deterministic policy thresholds:
                        </p>
                        <div className="flex flex-wrap gap-2 pt-2">
                          {selected.indicators && selected.indicators.length > 0 ? (
                            selected.indicators.map((ind) => (
                              <div
                                key={ind}
                                className="flex items-center gap-1.5 rounded-lg border border-sky-400/20 bg-sky-400/10 px-3 py-1.5 text-xs text-sky-200"
                              >
                                <CheckCircle2 className="size-3.5 text-sky-400" />
                                {ind}
                              </div>
                            ))
                          ) : (
                            <div className="text-xs text-slate-500">Normal activity pattern — no anomaly triggers.</div>
                          )}
                        </div>
                        <p className="text-[10px] text-slate-500 pt-2">
                          Indicators represent explicit deterministic triggers. They are not simulated or fabricated.
                        </p>
                      </div>
                    </Panel>

                    {/* Pillar 3: Model Posterior vs Display Score */}
                    <Panel title="Pillar 3: Model Scoring & Boundary Logic" eyebrow="Decision Engine">
                      <div className="p-5 space-y-4 text-xs">
                        <div>
                          <div className="flex justify-between text-slate-400 mb-1">
                            <span>Normalized Risk Score: <b>{selected.riskScore} / 100</b></span>
                            <span>Level: <b className="capitalize text-white">{selected.riskLevel}</b></span>
                          </div>
                          <div className="h-2 rounded-full bg-white/10">
                            <div
                              className={`h-full rounded-full transition-all duration-500 ${
                                selected.riskLevel === 'high'
                                  ? 'bg-red-400'
                                  : selected.riskLevel === 'medium'
                                    ? 'bg-amber-400'
                                    : 'bg-emerald-400'
                              }`}
                              style={{ width: `${selected.riskScore}%` }}
                            />
                          </div>
                        </div>

                        <div className="grid grid-cols-3 gap-2 text-center text-[11px] pt-2">
                          <div className="rounded border border-emerald-500/20 bg-emerald-950/20 p-2">
                            <p className="text-slate-400">Low Risk</p>
                            <p className="font-semibold text-emerald-400">&lt; 0.270</p>
                            <p className="text-[9px] text-slate-500">Allow</p>
                          </div>
                          <div className="rounded border border-amber-500/20 bg-amber-950/20 p-2">
                            <p className="text-slate-400">Medium Risk</p>
                            <p className="font-semibold text-amber-400">0.270 – 0.450</p>
                            <p className="text-[9px] text-slate-500">Step-up auth</p>
                          </div>
                          <div className="rounded border border-red-500/20 bg-red-950/20 p-2">
                            <p className="text-slate-400">High Risk</p>
                            <p className="font-semibold text-red-400">&ge; 0.450</p>
                            <p className="text-[9px] text-slate-500">Hold for review</p>
                          </div>
                        </div>

                        <p className="text-[10px] text-slate-500">
                          Display score is a scaled 0–100 integer. Thresholds reflect validation-tuned tuning ($\tau = 0.450$).
                        </p>
                      </div>
                    </Panel>

                    {/* Pillar 4: Investigator Explanation & Policy Guidance */}
                    <Panel title="Pillar 4: Investigator Recommendation" eyebrow="Triage Guidance">
                      <div className="p-5 space-y-3 text-xs">
                        <div className="rounded-lg border border-sky-400/20 bg-sky-400/[0.04] p-3">
                          <p className="font-semibold text-sky-300">Mandated Action: {selected.recommendedAction}</p>
                          <p className="mt-1 text-slate-300 text-[11px] leading-relaxed">
                            {selected.riskLevel === 'high'
                              ? 'This transaction poses severe risk due to cumulative anomalous signals. Hold settlement immediately and initiate enhanced due diligence.'
                              : selected.riskLevel === 'medium'
                                ? 'Elevated risk profile detected. Issue an out-of-band step-up authentication challenge to the cardholder/account owner.'
                                : 'Risk profile within normal operational parameters. Approved for automated straight-through processing.'}
                          </p>
                        </div>

                        <div className="rounded border border-white/[0.06] bg-white/[0.02] p-3 text-[10px] text-slate-400 space-y-1">
                          <p className="font-semibold text-slate-300">Audit Provenance Note:</p>
                          <p>Transaction ID: {selected.id}</p>
                          <p>Recorded by: {selected.processedBy || 'sentinelz_local'}</p>
                          <p>Advisory Notice: Synthetic demonstration benchmark. Decision guidance is advisory.</p>
                        </div>
                      </div>
                    </Panel>
                  </div>
                </div>
              ) : (
                <Panel title="No Transaction Selected" eyebrow="Inspection">
                  <div className="p-12 text-center text-slate-500">
                    <p className="text-sm">Please select a transaction from the explorer or simulate one above.</p>
                    <button
                      onClick={() => setActiveTab('transactions')}
                      className="mt-3 rounded bg-sky-400/10 px-3 py-1.5 text-xs text-sky-300 hover:bg-sky-400/20"
                    >
                      Go to Transactions Explorer
                    </button>
                  </div>
                </Panel>
              )}
            </div>
          )}

          {/* ========================================================================= */}
          {/* TAB 4: ALERTS QUEUE & INVESTIGATION WORKFLOW */}
          {/* ========================================================================= */}
          {activeTab === 'alerts' && (
            <div className="space-y-6">
              <Panel title="Alert Priority Management Queue" eyebrow="Analyst Triage">
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[0.07] p-4">
                  <div className="flex gap-1 rounded-md border border-white/10 bg-white/[0.02] p-1">
                    <button
                      onClick={() => setAlertStatusFilter('all')}
                      className={`rounded px-2.5 py-1 text-[11px] ${
                        alertStatusFilter === 'all' ? 'bg-white/10 text-white' : 'text-slate-500'
                      }`}
                    >
                      All ({alerts.length})
                    </button>
                    {(['Needs review', 'In review', 'Resolved'] as ReviewStatus[]).map((st) => (
                      <button
                        key={st}
                        onClick={() => setAlertStatusFilter(st)}
                        className={`rounded px-2.5 py-1 text-[11px] ${
                          alertStatusFilter === st ? 'bg-white/10 text-white' : 'text-slate-500'
                        }`}
                      >
                        {st} ({alerts.filter((a) => a.status === st).length})
                      </button>
                    ))}
                  </div>

                  <p className="text-xs text-slate-500">
                    Status updates persist atomically to backend SQLite and record compliance audit entries.
                  </p>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="text-[10px] uppercase tracking-wider text-slate-500 border-b border-white/[0.05]">
                      <tr>
                        <th className="px-4 py-3 font-medium">Alert ID</th>
                        <th className="px-4 py-3 font-medium">Linked Txn</th>
                        <th className="px-4 py-3 font-medium">Risk Score</th>
                        <th className="px-4 py-3 font-medium">Trigger Reason</th>
                        <th className="px-4 py-3 font-medium">Next Step</th>
                        <th className="px-4 py-3 font-medium">Current Status</th>
                        <th className="px-4 py-3 font-medium">Triage Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/[0.03]">
                      {filteredAlerts.length === 0 ? (
                        <tr>
                          <td colSpan={7} className="py-8 text-center text-slate-500">
                            No alerts matching filter &ldquo;{alertStatusFilter}&rdquo;.
                          </td>
                        </tr>
                      ) : (
                        filteredAlerts.map((a) => (
                          <tr key={a.id} className="hover:bg-white/[0.02]">
                            <td className="px-4 py-3 font-mono text-sky-400 font-medium">{a.id}</td>
                            <td className="px-4 py-3 font-mono text-slate-300">
                              <button
                                onClick={() => {
                                  const match = transactions.find((t) => t.id === a.transactionId)
                                  if (match) setSelected(match)
                                  setActiveTab('risk-analysis')
                                }}
                                className="hover:text-sky-300 hover:underline"
                              >
                                {a.transactionId}
                              </button>
                            </td>
                            <td className="px-4 py-3 font-semibold text-red-300">{a.riskScore}</td>
                            <td className="px-4 py-3 text-slate-200">{a.reason}</td>
                            <td className="px-4 py-3 text-slate-400">{a.nextStep}</td>
                            <td className="px-4 py-3">
                              <StatusBadge status={a.status} />
                            </td>
                            <td className="px-4 py-3">
                              <div className="flex items-center gap-1.5">
                                {a.status === 'Needs review' && (
                                  <button
                                    onClick={() => handleUpdateAlertStatus(a.id, 'In review')}
                                    className="rounded bg-amber-400/10 px-2 py-1 text-[10px] text-amber-300 hover:bg-amber-400/20"
                                  >
                                    Review
                                  </button>
                                )}
                                {a.status === 'In review' && (
                                  <button
                                    onClick={() => handleUpdateAlertStatus(a.id, 'Resolved')}
                                    className="rounded bg-emerald-400/10 px-2 py-1 text-[10px] text-emerald-300 hover:bg-emerald-400/20"
                                  >
                                    Resolve
                                  </button>
                                )}
                                {a.status === 'Resolved' && (
                                  <button
                                    onClick={() => handleUpdateAlertStatus(a.id, 'Needs review')}
                                    className="rounded bg-white/10 px-2 py-1 text-[10px] text-slate-300 hover:bg-white/20"
                                  >
                                    Re-open
                                  </button>
                                )}
                              </div>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </Panel>
            </div>
          )}

          {/* ========================================================================= */}
          {/* TAB 5: MODEL EVALUATION & SCIENTIFIC BENCHMARKS */}
          {/* ========================================================================= */}
          {activeTab === 'performance' && (
            <div className="space-y-6">
              <Panel title="Machine Learning Evaluation & Benchmarks" eyebrow="Held-out Test (N=900)">
                <div className="p-6 space-y-6">
                  <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 border-b border-white/[0.06] pb-4">
                    <div>
                      <h3 className="text-base font-semibold text-white">Random Forest Classifier Pipeline</h3>
                      <p className="text-xs text-slate-400">
                        Evaluated with Stratified 80/20 Split on 3.5% Fraud Imbalance (Seed = 42, Fixed &tau; = 0.450)
                      </p>
                    </div>
                    <span className="rounded bg-sky-400/10 px-3 py-1 font-mono text-xs text-sky-300">
                      Version: {performance?.modelVersion || '1.0.0'}
                    </span>
                  </div>

                  {/* Metrics Grid */}
                  <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
                    {[
                      {
                        label: 'Precision (PPV)',
                        val: performance?.precision ? `${(performance.precision * 100).toFixed(1)}%` : '—',
                        desc: 'True Positives / All Flagged',
                      },
                      {
                        label: 'Recall (TPR)',
                        val: performance?.recall ? `${(performance.recall * 100).toFixed(1)}%` : '—',
                        desc: 'Frauds Detected / Total Frauds',
                      },
                      {
                        label: 'F1-Score',
                        val: performance?.f1Score ? performance.f1Score.toFixed(4) : '—',
                        desc: 'Harmonic Mean P & R',
                      },
                      {
                        label: 'PR-AUC',
                        val: performance?.prAuc ? performance.prAuc.toFixed(4) : '—',
                        desc: 'Area under Precision-Recall',
                      },
                      {
                        label: 'ROC-AUC',
                        val: performance?.rocAuc ? performance.rocAuc.toFixed(4) : '—',
                        desc: 'Discrimination Index',
                      },
                      {
                        label: 'False Pos. Rate',
                        val: performance?.falsePositiveRate ? `${(performance.falsePositiveRate * 100).toFixed(2)}%` : '—',
                        desc: 'False Alarms / Legitimate',
                      },
                    ].map((m) => (
                      <div key={m.label} className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
                        <p className="text-[10px] uppercase tracking-wider text-slate-400">{m.label}</p>
                        <p className="mt-2 text-2xl font-bold text-white">{m.val}</p>
                        <p className="mt-1 text-[10px] text-slate-500">{m.desc}</p>
                      </div>
                    ))}
                  </div>

                  {/* Confusion Matrix Breakdown */}
                  {performance?.confusionMatrix && (
                    <div className="rounded-xl border border-white/[0.07] bg-slate-950/60 p-5 space-y-3">
                      <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                        Held-Out Confusion Matrix Breakdown (N = 900)
                      </h4>
                      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                        <div className="rounded-lg border border-emerald-500/20 bg-emerald-950/20 p-3 text-center">
                          <p className="text-xl font-bold text-emerald-400">{performance.confusionMatrix.true_negatives}</p>
                          <p className="text-xs font-medium text-slate-300 mt-1">True Negatives</p>
                          <p className="text-[10px] text-slate-500">Correctly Cleared Normal</p>
                        </div>
                        <div className="rounded-lg border border-amber-500/20 bg-amber-950/20 p-3 text-center">
                          <p className="text-xl font-bold text-amber-400">{performance.confusionMatrix.false_positives}</p>
                          <p className="text-xs font-medium text-slate-300 mt-1">False Positives</p>
                          <p className="text-[10px] text-slate-500">False Alarms (FPR 2.31%)</p>
                        </div>
                        <div className="rounded-lg border border-red-500/20 bg-red-950/20 p-3 text-center">
                          <p className="text-xl font-bold text-red-400">{performance.confusionMatrix.false_negatives}</p>
                          <p className="text-xs font-medium text-slate-300 mt-1">False Negatives</p>
                          <p className="text-[10px] text-slate-500">Missed Suspicious Events</p>
                        </div>
                        <div className="rounded-lg border border-sky-500/20 bg-sky-950/20 p-3 text-center">
                          <p className="text-xl font-bold text-sky-400">{performance.confusionMatrix.true_positives}</p>
                          <p className="text-xs font-medium text-slate-300 mt-1">True Positives</p>
                          <p className="text-[10px] text-slate-500">Correctly Caught Frauds</p>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Scientific Disclosure */}
                  <div className="rounded-xl border border-amber-400/20 bg-amber-400/[0.04] p-4 text-xs leading-relaxed text-amber-200/90">
                    <p className="font-semibold text-amber-300 mb-1">Scientific Integrity & Class Imbalance Disclosure:</p>
                    <p>
                      {performance?.datasetDisclosures ||
                        'Metrics reflect realistic high-imbalance financial distributions (~3.5% fraud rate). High class imbalance dictates that Precision (25.93%) and Recall (21.21%) reflect an authentic 6x lift in PR-AUC (0.2197 vs 0.0366 no-skill baseline) while strictly constraining false positives (2.31%) to prevent analyst alert fatigue.'}
                    </p>
                  </div>
                </div>
              </Panel>
            </div>
          )}

          {/* ========================================================================= */}
          {/* TAB 6: AUDIT TRAIL */}
          {/* ========================================================================= */}
          {activeTab === 'audit' && (
            <div className="space-y-6">
              <Panel title="System Audit Trail & Compliance Log" eyebrow="ACID Persistence">
                <div className="overflow-x-auto p-4">
                  <table className="w-full text-left text-xs">
                    <thead className="text-[10px] uppercase tracking-wider text-slate-500 border-b border-white/[0.05]">
                      <tr>
                        <th className="px-3 py-2.5 font-medium">Log ID</th>
                        <th className="px-3 py-2.5 font-medium">Timestamp</th>
                        <th className="px-3 py-2.5 font-medium">Action</th>
                        <th className="px-3 py-2.5 font-medium">Actor</th>
                        <th className="px-3 py-2.5 font-medium">Event Details</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/[0.03]">
                      {auditLogs.length === 0 ? (
                        <tr>
                          <td colSpan={5} className="py-6 text-center text-slate-500">
                            No audit records found.
                          </td>
                        </tr>
                      ) : (
                        auditLogs.map((log) => (
                          <tr key={log.id} className="hover:bg-white/[0.02]">
                            <td className="whitespace-nowrap px-3 py-2.5 font-mono text-[11px] text-sky-400">
                              {log.id}
                            </td>
                            <td className="whitespace-nowrap px-3 py-2.5 font-mono text-[11px] text-slate-400">
                              {log.timestamp}
                            </td>
                            <td className="whitespace-nowrap px-3 py-2.5 font-semibold text-slate-300">
                              {log.action}
                            </td>
                            <td className="whitespace-nowrap px-3 py-2.5 text-slate-400 font-mono text-[11px]">
                              {log.actor}
                            </td>
                            <td className="px-3 py-2.5 text-slate-300 text-[11px] leading-relaxed">
                              {log.details}
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </Panel>
            </div>
          )}

          {/* ========================================================================= */}
          {/* TAB 7: SYSTEM HEALTH & IBM Z INTEGRATION */}
          {/* ========================================================================= */}
          {activeTab === 'health' && (
            <div className="space-y-6">
              <Panel title="IBM Z Mainframe & LinuxONE Architecture Console" eyebrow="Platform Integrity">
                <div className="p-6 space-y-6">
                  {/* Status Banner */}
                  <div className="grid gap-4 md:grid-cols-3">
                    <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4">
                      <p className="text-[10px] uppercase tracking-wider text-slate-500">Service Status</p>
                      <p className="mt-2 text-xl font-bold text-emerald-400 capitalize">{health?.status || 'Active'}</p>
                      <p className="mt-1 text-xs text-slate-400">FastAPI Gateway v{health?.version || '0.1.0'}</p>
                    </div>

                    <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4">
                      <p className="text-[10px] uppercase tracking-wider text-slate-500">Adapter Mode</p>
                      <p className="mt-2 text-xl font-bold text-sky-300 font-mono">
                        {health?.ibmZAdapter?.mode || 'local_simulation'}
                      </p>
                      <p className="mt-1 text-xs text-slate-400">Execution Origin Attribution</p>
                    </div>

                    <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4">
                      <p className="text-[10px] uppercase tracking-wider text-slate-500">Database Layer</p>
                      <p className="mt-2 text-xl font-bold text-slate-200">SQLite (WAL)</p>
                      <p className="mt-1 text-xs text-slate-400">{health?.databaseStatus || 'Connected'}</p>
                    </div>
                  </div>

                  {/* Architecture & Capabilities */}
                  <div className="rounded-xl border border-white/[0.07] bg-slate-950/50 p-5 space-y-4">
                    <h3 className="text-sm font-semibold text-white">Target Infrastructure: IBM LinuxONE (s390x)</h3>
                    <div className="grid gap-4 sm:grid-cols-2 text-xs">
                      <div className="space-y-2">
                        <p className="text-slate-400">
                          <b className="text-slate-200">CPU Architecture:</b> s390x (IBM z16 / LinuxONE Emperor)
                        </p>
                        <p className="text-slate-400">
                          <b className="text-slate-200">Byte Ordering:</b> Big-Endian (verified in Python struct/numpy)
                        </p>
                        <p className="text-slate-400">
                          <b className="text-slate-200">Cryptographic Acceleration:</b> CPACF hardware coprocessors
                        </p>
                      </div>
                      <div className="space-y-2">
                        <p className="text-slate-400">
                          <b className="text-slate-200">Adapter State:</b> {health?.ibmZAdapter?.status}
                        </p>
                        <p className="text-slate-400">
                          <b className="text-slate-200">Target Host:</b> {health?.ibmZAdapter?.targetHost || 'None (Running locally)'}
                        </p>
                        <p className="text-slate-400">
                          <b className="text-slate-200">Supported Capabilities:</b>{' '}
                          {health?.ibmZAdapter?.capabilities?.join(', ') || 'local_ml_inference, decision_policy'}
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Zero Silent Fallback Policy */}
                  <div className="rounded-xl border border-sky-400/20 bg-sky-400/[0.04] p-5 space-y-2 text-xs leading-relaxed">
                    <div className="flex items-center gap-2">
                      <ShieldAlert className="size-4 text-sky-400" />
                      <h4 className="font-semibold text-sky-300">Zero Silent Fallback Policy</h4>
                    </div>
                    <p className="text-slate-300">
                      When <code className="text-sky-300">IBM_Z_MODE=ibm_z</code> is activated, all transactions route directly to the configured IBM z/OS Connect EE gateway. If connectivity fails or times out, the system explicitly raises <code className="text-amber-300">IBMZConnectionError</code> or <code className="text-amber-300">IBMZTimeoutError</code> and halts the transaction. The adapter <b>never silently degrades</b> to local simulation while falsely presenting results as mainframe-validated.
                    </p>
                  </div>
                </div>
              </Panel>
            </div>
          )}

          {/* ========================================================================= */}
          {/* TAB 8: SETTINGS & POLICY THRESHOLDS */}
          {/* ========================================================================= */}
          {activeTab === 'settings' && (
            <div className="space-y-6">
              <Panel title="Decision Engine Policy Thresholds & Trigger Rules" eyebrow="Configuration">
                <div className="p-6 space-y-6">
                  <div className="border-b border-white/[0.06] pb-4">
                    <h3 className="text-sm font-semibold text-white">Active Risk Boundary Parameters</h3>
                    <p className="text-xs text-slate-400 mt-1">
                      Central single source of truth defined in <code className="text-sky-300">app/engine/config.py</code>.
                    </p>
                  </div>

                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 text-xs">
                    <div className="rounded-xl border border-red-500/20 bg-red-950/10 p-4 space-y-1">
                      <p className="text-[10px] uppercase tracking-wider text-red-300">High Risk Threshold (&tau;)</p>
                      <p className="text-2xl font-bold text-white">{engineConfig?.high_risk_threshold ?? 0.450}</p>
                      <p className="text-[10px] text-slate-400">Action: {engineConfig?.action_high ?? 'Hold for review'}</p>
                    </div>

                    <div className="rounded-xl border border-amber-500/20 bg-amber-950/10 p-4 space-y-1">
                      <p className="text-[10px] uppercase tracking-wider text-amber-300">Medium Risk Threshold (&tau;)</p>
                      <p className="text-2xl font-bold text-white">{engineConfig?.medium_risk_threshold ?? 0.270}</p>
                      <p className="text-[10px] text-slate-400">Action: {engineConfig?.action_medium ?? 'Step-up authentication'}</p>
                    </div>

                    <div className="rounded-xl border border-emerald-500/20 bg-emerald-950/10 p-4 space-y-1">
                      <p className="text-[10px] uppercase tracking-wider text-emerald-300">Low Risk Floor</p>
                      <p className="text-2xl font-bold text-white">&lt; 0.270</p>
                      <p className="text-[10px] text-slate-400">Action: {engineConfig?.action_low ?? 'Allow'}</p>
                    </div>

                    <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4 space-y-1">
                      <p className="text-[10px] uppercase tracking-wider text-slate-400">Amount Anomaly Multiplier</p>
                      <p className="text-xl font-bold text-white">{engineConfig?.amount_anomaly_multiplier ?? 4.0}x</p>
                      <p className="text-[10px] text-slate-500">Triggers when amount &ge; 4.0x baseline</p>
                    </div>

                    <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4 space-y-1">
                      <p className="text-[10px] uppercase tracking-wider text-slate-400">Velocity Burst Threshold</p>
                      <p className="text-xl font-bold text-white">{engineConfig?.velocity_burst_tx_per_hour ?? 5} tx/hr</p>
                      <p className="text-[10px] text-slate-500">Triggers when velocity &ge; 5 tx in 1hr</p>
                    </div>

                    <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4 space-y-1">
                      <p className="text-[10px] uppercase tracking-wider text-slate-400">Device Risk Threshold</p>
                      <p className="text-xl font-bold text-white">{engineConfig?.device_risk_threshold ?? 0.60}</p>
                      <p className="text-[10px] text-slate-500">Triggers on unrecognized device score &ge; 0.60</p>
                    </div>
                  </div>

                  <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4 text-xs text-slate-400">
                    <p className="font-semibold text-slate-200 mb-1">Human-in-the-Loop Workflow Rule:</p>
                    <p>
                      Automated decision algorithms assign initial workflow review states (<code className="text-sky-300">Needs review</code>). An automated algorithm <b>never</b> automatically marks a transaction or alert as <code className="text-emerald-300">Resolved</code>. Only authorized analysts may close or resolve compliance cases.
                    </p>
                  </div>
                </div>
              </Panel>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
