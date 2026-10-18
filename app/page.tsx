'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Activity,
  AlertTriangle,
  Bell,
  CheckCircle2,
  ChevronDown,
  Clock3,
  Cpu,
  Database,
  FileText,
  Filter,
  LayoutDashboard,
  Menu,
  MoreHorizontal,
  RefreshCw,
  Search,
  Settings,
  ShieldAlert,
  ShieldCheck,
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
  getHealth,
  getMetrics,
  getModelPerformance,
  getTransactions,
  simulateTransaction,
  type Alert,
  type AuditRecord,
  type HealthResponse,
  type Metrics,
  type ModelPerformance,
  type RiskLevel,
  type ScenarioName,
  type Transaction,
} from '@/lib/api'

function RiskBadge({ level }: { level: RiskLevel }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-[11px] font-semibold uppercase tracking-wide ${
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

export default function Page() {
  // Live State
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [selected, setSelected] = useState<Transaction | null>(null)
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [performance, setPerformance] = useState<ModelPerformance | null>(null)
  const [auditLogs, setAuditLogs] = useState<AuditRecord[]>([])

  // UI Control State
  const [activeTab, setActiveTab] = useState<'overview' | 'transactions' | 'alerts' | 'performance' | 'audit'>('overview')
  const [riskFilter, setRiskFilter] = useState<'all' | RiskLevel>('all')
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

  // Filtered transactions for search & risk level
  const filtered = useMemo(() => {
    return transactions.filter(
      (tx) =>
        (riskFilter === 'all' || tx.riskLevel === riskFilter) &&
        (tx.id.toLowerCase().includes(query.toLowerCase()) ||
          tx.channel.toLowerCase().includes(query.toLowerCase()) ||
          tx.recommendedAction.toLowerCase().includes(query.toLowerCase()))
    )
  }, [transactions, riskFilter, query])

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
      const [hRes, txRes, mRes, aRes, pRes, audRes] = await Promise.all([
        getHealth(),
        getTransactions({ limit: 100 }),
        getMetrics(),
        getAlerts(),
        getModelPerformance(),
        getAuditTrail(30),
      ])

      setHealth(hRes)
      setTransactions(txRes)
      setMetrics(mRes)
      setAlerts(aRes)
      setPerformance(pRes)
      setAuditLogs(audRes)
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

      // Immediately prepend new transaction
      setTransactions((prev) => [newTx, ...prev.filter((t) => t.id !== newTx.id)])
      setSelected(newTx)

      // If an alert was generated, prepend to alerts
      if (response.alert) {
        const newAlert = response.alert
        setAlerts((prev) => [newAlert, ...prev.filter((a) => a.id !== newAlert.id)])
      }

      // Display informative notification
      const alertNotice = response.alert
        ? ` · Triggered Alert ${response.alert.id} (${response.alert.status})`
        : ' · No alert generated (low risk)'

      setStatusMessage({
        type: 'success',
        title: `Simulated: ${newTx.id} (${response.scenario})`,
        detail: `Amount: $${newTx.amount.toLocaleString()} ${newTx.channel} · Risk Score: ${newTx.riskScore} (${newTx.riskLevel}) · Action: ${newTx.recommendedAction} · End-to-end Latency: ${response.processingLatencyMs}ms (ML: ${response.inferenceLatencyMs}ms)${alertNotice}`,
      })

      // Refresh metrics and audit log immediately
      const [mRes, audRes] = await Promise.all([getMetrics(), getAuditTrail(30)])
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
            <p className="text-[9px] uppercase tracking-[0.16em] text-slate-500">IBM Z Datathon 2026</p>
          </div>
          <button onClick={() => setMobileOpen(false)} className="ml-auto lg:hidden">
            <X className="size-4" />
          </button>
        </div>

        <nav className="flex flex-1 flex-col gap-1 px-3 py-6">
          {[
            { id: 'overview', icon: LayoutDashboard, label: 'Overview' },
            { id: 'transactions', icon: Activity, label: 'Live Transactions' },
            { id: 'alerts', icon: Bell, label: 'Alert Center', badge: alerts.length },
            { id: 'performance', icon: TrendingUp, label: 'Model Performance' },
            { id: 'audit', icon: FileText, label: 'Audit Trail', badge: auditLogs.length },
          ].map((item) => {
            const Icon = item.icon
            const isActive = activeTab === item.id
            return (
              <button
                key={item.id}
                onClick={() => {
                  setActiveTab(item.id as typeof activeTab)
                  setMobileOpen(false)
                }}
                className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition-colors ${
                  isActive
                    ? 'bg-sky-400/10 font-medium text-sky-300'
                    : 'text-slate-400 hover:bg-white/[0.04] hover:text-slate-200'
                }`}
              >
                <Icon className="size-4" />
                {item.label}
                {item.badge !== undefined && item.badge > 0 && (
                  <span
                    className={`ml-auto rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                      item.id === 'alerts'
                        ? 'bg-red-400/15 text-red-300'
                        : 'bg-white/10 text-slate-300'
                    }`}
                  >
                    {item.badge}
                  </span>
                )}
              </button>
            )
          })}

          <div className="my-4 border-t border-white/[0.07]" />

          {/* Model & IBM Z Integration Pill in Sidebar */}
          <div className="space-y-2 rounded-lg border border-white/[0.07] bg-white/[0.025] p-3">
            <p className="text-[10px] uppercase tracking-wider text-slate-500">System State</p>
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
                IBM Z: {health?.ibmZAdapter?.status ?? 'Unconfigured'}
              </span>
            </div>
            <p className="text-[9px] leading-tight text-slate-500">
              {health?.ibmZAdapter?.details ??
                'Running in local verification mode until verified IBM Z service access is configured.'}
            </p>
          </div>
        </nav>

        <div className="border-t border-white/[0.07] p-4 text-[10px] text-slate-500">
          FastAPI & Next.js · SQLite Persistence
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
            <button onClick={() => setMobileOpen(true)} className="lg:hidden text-slate-400">
              <Menu className="size-5" />
            </button>
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-sky-400">
                Command center
              </p>
              <h1 className="text-lg font-semibold tracking-tight text-white">
                {activeTab === 'overview' && 'Risk Overview'}
                {activeTab === 'transactions' && 'Live Transaction Monitor'}
                {activeTab === 'alerts' && 'Alert Management Queue'}
                {activeTab === 'performance' && 'Model Evaluation & Benchmarks'}
                {activeTab === 'audit' && 'System Audit Trail'}
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Live Connection Badge */}
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

            {/* Manual Refresh Button */}
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
              className="text-xs opacity-70 hover:opacity-100"
            >
              <X className="size-4" />
            </button>
          </div>
        )}

        <div className="mx-auto max-w-[1600px] space-y-6 p-5 md:p-8">
          {/* Top Control Bar with Simulation Options */}
          <div className="flex flex-col justify-between gap-4 rounded-xl border border-white/[0.08] bg-[#111b2b] p-5 md:flex-row md:items-center">
            <div>
              <div className="flex items-center gap-2">
                <Sparkles className="size-4 text-sky-400" />
                <h3 className="text-sm font-semibold text-white">Live Transaction Simulator</h3>
                <span className="rounded bg-sky-400/15 px-2 py-0.5 text-[10px] font-medium text-sky-300">
                  Stage 6 Pipeline
                </span>
              </div>
              <p className="mt-1 text-xs text-slate-400">
                Trigger real synthetic transactions through the Random Forest model and decision engine.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              {/* Scenario Selector Dropdown */}
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

              {/* Simulation Trigger Button */}
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
                    <span>Run Simulation</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Scenario description hint */}
          <div className="rounded-lg border border-white/[0.05] bg-white/[0.02] px-4 py-2.5 text-[11px] text-slate-400">
            <span className="font-semibold text-slate-300">Active Scenario:</span>{' '}
            {SCENARIOS.find((s) => s.id === selectedScenario)?.description}{' '}
            <span className="text-slate-500">
              (Synthetic demonstration input; decision recommendations are advisory.)
            </span>
          </div>

          {/* KPI Metrics Cards */}
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {[
              {
                label: 'Transactions processed',
                value: metrics ? metrics.transactionsProcessed.toLocaleString() : '—',
                sub: 'Persisted in SQLite',
                color: 'bg-sky-400',
              },
              {
                label: 'High-risk transactions',
                value: metrics ? metrics.highRiskTransactions.toLocaleString() : '—',
                sub: `${riskDistribution.highPct} of processed volume`,
                color: 'bg-red-400',
              },
              {
                label: 'Alerts generated',
                value: metrics ? metrics.alertsGenerated.toLocaleString() : '—',
                sub: `${alerts.length} active in priority queue`,
                color: 'bg-amber-400',
              },
              {
                label: 'Avg. processing latency',
                value: metrics ? `${metrics.averageLatencyMs.toFixed(1)} ms` : '—',
                sub: 'Real measurement (perf_counter)',
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
                        name="Processed Volume"
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

            <Panel title="Risk Distribution" eyebrow="Stored Transactions">
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

          {/* Main Transaction Monitor and Selected Transaction Panel */}
          <div className="grid gap-6 xl:grid-cols-[minmax(0,1.65fr)_minmax(320px,0.8fr)]">
            <Panel title="Live Transaction Monitor" eyebrow="SQLite Database">
              {/* Search & Filter Controls */}
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
                <div className="flex gap-1 rounded-md border border-white/10 bg-white/[0.02] p-1">
                  <button
                    onClick={() => setRiskFilter('all')}
                    className={`rounded px-2.5 py-1.5 text-[11px] ${
                      riskFilter === 'all' ? 'bg-white/10 text-white' : 'text-slate-500'
                    }`}
                  >
                    All
                  </button>
                  {(['high', 'medium', 'low'] as RiskLevel[]).map((level) => (
                    <button
                      key={level}
                      onClick={() => setRiskFilter(level)}
                      className={`rounded px-2.5 py-1.5 text-[11px] capitalize ${
                        riskFilter === level ? 'bg-white/10 text-white' : 'text-slate-500'
                      }`}
                    >
                      {level}
                    </button>
                  ))}
                </div>
              </div>

              {/* Transactions Table */}
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-wider text-slate-500">
                    <tr className="border-b border-white/[0.05]">
                      <th className="px-4 py-3 font-medium">Transaction</th>
                      <th className="px-4 py-3 font-medium">Time</th>
                      <th className="px-4 py-3 font-medium">Amount</th>
                      <th className="px-4 py-3 font-medium">Channel</th>
                      <th className="px-4 py-3 font-medium">Risk Score</th>
                      <th className="px-4 py-3 font-medium">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {initialLoading ? (
                      <tr>
                        <td colSpan={6} className="py-8 text-center text-slate-500">
                          <RefreshCw className="mx-auto size-5 animate-spin text-sky-400 mb-2" />
                          Loading persisted transactions...
                        </td>
                      </tr>
                    ) : filtered.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="py-8 text-center text-slate-500">
                          No transactions found matching the filter criteria.
                        </td>
                      </tr>
                    ) : (
                      filtered.map((tx) => (
                        <tr
                          key={tx.id}
                          onClick={() => setSelected(tx)}
                          className={`cursor-pointer border-b border-white/[0.04] transition-colors hover:bg-white/[0.035] ${
                            selected?.id === tx.id ? 'bg-sky-400/[0.08]' : ''
                          }`}
                        >
                          <td className="whitespace-nowrap px-4 py-3 font-medium text-sky-300">
                            {tx.id}
                          </td>
                          <td className="whitespace-nowrap px-4 py-3 font-mono text-[11px] text-slate-400">
                            {tx.timestamp}
                          </td>
                          <td className="whitespace-nowrap px-4 py-3 text-slate-300">
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
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              <div className="flex items-center justify-between px-4 py-3 text-[10px] text-slate-500">
                <span>
                  Showing {filtered.length} of {transactions.length} persisted transactions
                </span>
                <span className="flex items-center gap-1">
                  <Clock3 className="size-3 text-sky-400" />
                  Live polling active (4s)
                </span>
              </div>
            </Panel>

            {/* Selected Transaction Detail View */}
            <Panel title="Selected Transaction" eyebrow="Risk Assessment">
              {selected ? (
                <div className="flex flex-col gap-5 p-5">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="font-mono text-sm text-sky-300">{selected.id}</p>
                      <p className="mt-1 text-[11px] text-slate-500">
                        Processed at {selected.processingTimestamp}
                      </p>
                    </div>
                    <RiskBadge level={selected.riskLevel} />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="rounded-lg border border-white/[0.06] bg-white/[0.025] p-3">
                      <p className="text-[10px] uppercase tracking-wider text-slate-500">Amount</p>
                      <p className="mt-1 text-sm font-semibold text-slate-200">
                        ${selected.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </p>
                    </div>
                    <div className="rounded-lg border border-white/[0.06] bg-white/[0.025] p-3">
                      <p className="text-[10px] uppercase tracking-wider text-slate-500">Channel</p>
                      <p className="mt-1 text-sm font-semibold text-slate-200">{selected.channel}</p>
                    </div>
                  </div>

                  <div>
                    <div className="mb-2 flex items-center justify-between text-xs">
                      <span className="text-slate-400">Risk Score</span>
                      <span className="font-semibold text-white">{selected.riskScore} / 100</span>
                    </div>
                    <div className="h-1.5 rounded-full bg-white/10">
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

                  <div>
                    <p className="mb-2 text-xs font-medium text-slate-300">Contributing Indicators</p>
                    <div className="flex flex-wrap gap-1.5">
                      {selected.indicators && selected.indicators.length > 0 ? (
                        selected.indicators.map((indicator) => (
                          <span
                            key={indicator}
                            className="rounded bg-white/[0.06] px-2 py-1 text-[10px] text-slate-300 border border-white/[0.05]"
                          >
                            {indicator}
                          </span>
                        ))
                      ) : (
                        <span className="text-[10px] text-slate-500">None detected</span>
                      )}
                    </div>
                  </div>

                  <div className="rounded-lg border border-sky-400/15 bg-sky-400/[0.05] p-3">
                    <p className="text-[10px] uppercase tracking-wider text-sky-400">
                      Recommended Action
                    </p>
                    <p className="mt-1 text-xs font-medium text-slate-200">
                      {selected.recommendedAction}
                    </p>
                    <p className="mt-1 text-[10px] text-slate-500">
                      Engine: {selected.processedBy || 'sentinelz_local'} · Advisory guidance
                    </p>
                  </div>
                </div>
              ) : (
                <div className="flex h-64 flex-col items-center justify-center p-5 text-center text-slate-500">
                  <p className="text-xs">No transaction selected.</p>
                  <p className="mt-1 text-[11px]">Click a row in the monitor to inspect risk signals.</p>
                </div>
              )}
            </Panel>
          </div>

          {/* Third Row: Alert Center, Latency Chart, Model Performance */}
          <div className="grid gap-6 xl:grid-cols-3">
            {/* Alert Center */}
            <Panel title="Alert Center" eyebrow="Priority Queue">
              <div className="flex flex-col divide-y divide-white/[0.06]">
                {alerts.length === 0 ? (
                  <div className="p-6 text-center text-xs text-slate-500">
                    No active priority alerts in queue.
                  </div>
                ) : (
                  alerts.slice(0, 5).map((alert) => (
                    <div key={alert.id} className="p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="flex items-center gap-2">
                            <AlertTriangle className="size-3.5 text-red-300" />
                            <span className="font-mono text-xs text-sky-300">
                              {alert.transactionId}
                            </span>
                            <span className="text-[10px] text-slate-500">{alert.id}</span>
                          </div>
                          <p className="mt-2 text-xs text-slate-300">{alert.reason}</p>
                          <p className="mt-1 text-[10px] text-slate-500">Next: {alert.nextStep}</p>
                        </div>
                        <span className="text-sm font-semibold text-red-300">{alert.riskScore}</span>
                      </div>
                      <div className="mt-3 flex items-center justify-between text-[10px]">
                        <span
                          className={`font-medium ${
                            alert.status === 'In review'
                              ? 'text-amber-300'
                              : alert.status === 'Resolved'
                                ? 'text-emerald-300'
                                : 'text-red-300'
                          }`}
                        >
                          {alert.status}
                        </span>
                        <span className="text-slate-500">Triage queue</span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </Panel>

            {/* Processing Latency Chart */}
            <Panel title="Processing Latency" eyebrow="Real-time Timing">
              <div className="h-48 p-4">
                {metrics?.latencyData && metrics.latencyData.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={metrics.latencyData}>
                      <CartesianGrid stroke="#ffffff0d" vertical={false} />
                      <XAxis
                        dataKey="time"
                        axisLine={false}
                        tickLine={false}
                        tick={{ fill: '#64748b', fontSize: 9 }}
                      />
                      <YAxis
                        axisLine={false}
                        tickLine={false}
                        tick={{ fill: '#64748b', fontSize: 9 }}
                      />
                      <Tooltip
                        contentStyle={{
                          background: '#111b2b',
                          border: '1px solid #ffffff1a',
                          borderRadius: 8,
                          fontSize: 11,
                        }}
                      />
                      <Line
                        type="monotone"
                        dataKey="value"
                        name="Latency (ms)"
                        stroke="#34d399"
                        strokeWidth={2}
                        dot={false}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex h-full flex-col items-center justify-center text-center">
                    <p className="text-xs text-slate-500">No latency measurements recorded.</p>
                  </div>
                )}
              </div>
              <p className="px-5 pb-4 text-[10px] text-slate-500">
                End-to-end local latency in milliseconds · Measured via time.perf_counter()
              </p>
            </Panel>

            {/* Model Performance Card */}
            <Panel title="Model Performance" eyebrow="Held-out Evaluation">
              <div className="p-5">
                <div className="flex items-center justify-between border-b border-white/[0.06] pb-4">
                  <div>
                    <p className="text-xs font-medium text-slate-300">Model Pipeline</p>
                    <p className="mt-1 font-mono text-sm text-sky-300">
                      {performance?.modelVersion || 'Pending evaluation'}
                    </p>
                  </div>
                  <Database className="size-5 text-slate-500" />
                </div>

                <div className="grid grid-cols-2 gap-3 py-4 sm:grid-cols-3">
                  {[
                    {
                      label: 'Precision',
                      val:
                        performance?.precision !== null && performance?.precision !== undefined
                          ? `${(performance.precision * 100).toFixed(1)}%`
                          : '—',
                    },
                    {
                      label: 'Recall',
                      val:
                        performance?.recall !== null && performance?.recall !== undefined
                          ? `${(performance.recall * 100).toFixed(1)}%`
                          : '—',
                    },
                    {
                      label: 'F1-Score',
                      val:
                        performance?.f1Score !== null && performance?.f1Score !== undefined
                          ? performance.f1Score.toFixed(4)
                          : '—',
                    },
                    {
                      label: 'PR-AUC',
                      val:
                        performance?.prAuc !== null && performance?.prAuc !== undefined
                          ? performance.prAuc.toFixed(4)
                          : '—',
                    },
                    {
                      label: 'ROC-AUC',
                      val:
                        performance?.rocAuc !== null && performance?.rocAuc !== undefined
                          ? performance.rocAuc.toFixed(4)
                          : '—',
                    },
                    {
                      label: 'FPR (False Pos)',
                      val:
                        performance?.falsePositiveRate !== null &&
                        performance?.falsePositiveRate !== undefined
                          ? `${(performance.falsePositiveRate * 100).toFixed(2)}%`
                          : '—',
                    },
                  ].map((metric) => (
                    <div key={metric.label} className="rounded-lg border border-white/[0.05] bg-white/[0.02] p-2.5">
                      <p className="text-[10px] uppercase tracking-wider text-slate-500">
                        {metric.label}
                      </p>
                      <p className="mt-1 text-base font-semibold text-slate-200">{metric.val}</p>
                    </div>
                  ))}
                </div>

                {performance?.confusionMatrix && (
                  <div className="mb-3 rounded-lg border border-white/[0.06] bg-slate-950/60 p-2.5 text-[11px] font-mono text-slate-400">
                    <p className="text-[10px] uppercase tracking-wider text-slate-500 font-sans mb-1">
                      Held-Out Test Confusion Matrix (N=900)
                    </p>
                    <div className="grid grid-cols-2 gap-2 text-center text-xs">
                      <div className="bg-emerald-950/30 border border-emerald-500/20 rounded p-1">
                        <span className="text-emerald-400 font-semibold">TN: {performance.confusionMatrix.true_negatives}</span>
                        <span className="block text-[9px] text-slate-500">Correct Normal</span>
                      </div>
                      <div className="bg-amber-950/30 border border-amber-500/20 rounded p-1">
                        <span className="text-amber-400 font-semibold">FP: {performance.confusionMatrix.false_positives}</span>
                        <span className="block text-[9px] text-slate-500">False Alarm</span>
                      </div>
                      <div className="bg-red-950/30 border border-red-500/20 rounded p-1">
                        <span className="text-red-400 font-semibold">FN: {performance.confusionMatrix.false_negatives}</span>
                        <span className="block text-[9px] text-slate-500">Missed Fraud</span>
                      </div>
                      <div className="bg-sky-950/30 border border-sky-500/20 rounded p-1">
                        <span className="text-sky-400 font-semibold">TP: {performance.confusionMatrix.true_positives}</span>
                        <span className="block text-[9px] text-slate-500">Caught Fraud</span>
                      </div>
                    </div>
                  </div>
                )}

                <div className="rounded-lg border border-amber-400/15 bg-amber-400/[0.04] p-3 text-[10px] leading-relaxed text-amber-200/80">
                  {performance?.datasetDisclosures ||
                    'Demonstration benchmarks evaluated on held-out synthetic test transactions.'}
                </div>
              </div>
            </Panel>
          </div>

          {/* Audit Trail Section */}
          <Panel title="System Audit Trail" eyebrow="Compliance Log">
            <div className="overflow-x-auto p-4">
              <table className="w-full text-left text-xs">
                <thead className="text-[10px] uppercase tracking-wider text-slate-500">
                  <tr className="border-b border-white/[0.05]">
                    <th className="px-3 py-2 font-medium">Log ID</th>
                    <th className="px-3 py-2 font-medium">Timestamp</th>
                    <th className="px-3 py-2 font-medium">Action</th>
                    <th className="px-3 py-2 font-medium">Actor</th>
                    <th className="px-3 py-2 font-medium">Event Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/[0.03]">
                  {auditLogs.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="py-4 text-center text-slate-500">
                        No audit records recorded yet.
                      </td>
                    </tr>
                  ) : (
                    auditLogs.slice(0, 8).map((log) => (
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
                        <td className="whitespace-nowrap px-3 py-2.5 text-slate-400">{log.actor}</td>
                        <td className="px-3 py-2.5 text-slate-300">{log.details}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </Panel>
        </div>
      </main>
    </div>
  )
}
