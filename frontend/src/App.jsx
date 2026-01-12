import React, { useState, useEffect, useCallback } from 'react'
import { 
  Upload, 
  FileSpreadsheet, 
  Loader2, 
  Download, 
  Trash2, 
  XCircle,
  ChevronDown,
  ChevronUp,
  Flame,
  Thermometer,
  Eye,
  Snowflake,
  Cpu,
  Building2,
  DollarSign,
  Users,
  MapPin,
  Sparkles,
  Info,
  X
} from 'lucide-react'

const API_BASE = '/api'

// Tier badge component
function TierBadge({ tier }) {
  const config = {
    HOT: { class: 'badge-hot', icon: Flame, label: 'HOT' },
    WARM: { class: 'badge-warm', icon: Thermometer, label: 'WARM' },
    WATCH: { class: 'badge-watch', icon: Eye, label: 'WATCH' },
    COLD: { class: 'badge-cold', icon: Snowflake, label: 'COLD' },
  }
  
  const { class: className, icon: Icon, label } = config[tier] || config.COLD
  
  return (
    <span className={`badge ${className}`}>
      <Icon size={12} style={{ marginRight: 4 }} />
      {label}
    </span>
  )
}

// GPU Tier badge
function GPUTierBadge({ tier }) {
  const colors = {
    S: '#ef4444',
    A: '#f59e0b',
    B: '#3b82f6',
    C: '#8b5cf6',
    D: '#10b981',
    E: '#6b7280',
    UNKNOWN: '#374151',
  }
  
  return (
    <span 
      className="badge" 
      style={{ 
        background: `${colors[tier]}20`,
        color: colors[tier],
        border: `1px solid ${colors[tier]}50`,
        fontWeight: 600,
      }}
    >
      Tier {tier}
    </span>
  )
}

// Score bar component
function ScoreBar({ score, max = 100 }) {
  const percent = (score / max) * 100
  const color = percent >= 70 ? 'var(--tier-hot)' : 
                percent >= 50 ? 'var(--tier-warm)' : 
                percent >= 30 ? 'var(--tier-watch)' : 'var(--tier-cold)'
  
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div className="progress-bar" style={{ width: 60 }}>
        <div 
          className="progress-bar-fill" 
          style={{ width: `${percent}%`, background: color }}
        />
      </div>
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--text-secondary)' }}>
        {score}
      </span>
    </div>
  )
}

// Company row expanded details
function CompanyDetails({ company }) {
  return (
    <tr>
      <td colSpan={7} style={{ padding: 0, background: 'var(--bg-secondary)' }}>
        <div style={{ padding: '20px 24px' }} className="animate-fade-in">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 24 }}>
            {/* Company Info */}
            <div>
              <h4 style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 12, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Company Info
              </h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {company.description && (
                  <p style={{ color: 'var(--text-secondary)', fontSize: 14, lineHeight: 1.6 }}>
                    {company.description}
                  </p>
                )}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, marginTop: 8 }}>
                  {company.employee_count && (
                    <span style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--text-secondary)', fontSize: 13 }}>
                      <Users size={14} /> {company.employee_count} employees
                    </span>
                  )}
                  {company.headquarters && (
                    <span style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--text-secondary)', fontSize: 13 }}>
                      <MapPin size={14} /> {company.headquarters}
                    </span>
                  )}
                  {company.industry && (
                    <span style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--text-secondary)', fontSize: 13 }}>
                      <Building2 size={14} /> {company.industry}
                    </span>
                  )}
                </div>
              </div>
            </div>
            
            {/* GPU Analysis */}
            <div>
              <h4 style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 12, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                GPU Analysis
              </h4>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                {company.gpu_use_case_tier && <GPUTierBadge tier={company.gpu_use_case_tier} />}
                <span style={{ color: 'var(--text-secondary)', fontSize: 13 }}>
                  {company.gpu_use_case_label}
                </span>
              </div>
              {company.gpu_analysis_reasoning && (
                <p style={{ color: 'var(--text-secondary)', fontSize: 13, lineHeight: 1.6, fontStyle: 'italic' }}>
                  "{company.gpu_analysis_reasoning}"
                </p>
              )}
            </div>
            
            {/* Score Breakdown */}
            <div>
              <h4 style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 12, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Score Breakdown
              </h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>GPU Use Case</span>
                  <ScoreBar score={company.score_gpu_use_case} max={50} />
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Scale & Budget</span>
                  <ScoreBar score={company.score_scale_budget} max={30} />
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Growth Signals</span>
                  <ScoreBar score={company.score_growth_signals || company.score_timing_urgency} max={10} />
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Confidence</span>
                  <ScoreBar score={company.score_confidence} max={10} />
                </div>
              </div>
            </div>
          </div>
          
          {company.recommended_action && (
            <div style={{ marginTop: 20, padding: '12px 16px', background: 'var(--bg-tertiary)', borderRadius: 'var(--radius-md)', borderLeft: `3px solid var(--accent-emerald)` }}>
              <span style={{ fontSize: 13 }}>
                <strong style={{ color: 'var(--accent-emerald)' }}>Recommended: </strong>
                <span style={{ color: 'var(--text-secondary)' }}>{company.recommended_action}</span>
              </span>
            </div>
          )}
        </div>
      </td>
    </tr>
  )
}

// Main App
export default function App() {
  const [jobs, setJobs] = useState([])
  const [selectedJob, setSelectedJob] = useState(null)
  const [jobDetails, setJobDetails] = useState(null)
  const [expandedRows, setExpandedRows] = useState(new Set())
  const [uploading, setUploading] = useState(false)
  const [loading, setLoading] = useState(true)
  const [submitterName, setSubmitterName] = useState('')
  const [filterBySubmitter, setFilterBySubmitter] = useState('all')
  const [inputMode, setInputMode] = useState('csv') // 'csv' or 'single'
  const [singleCompanyName, setSingleCompanyName] = useState('')
  const [processingSingle, setProcessingSingle] = useState(false)
  const [showScoringInfo, setShowScoringInfo] = useState(false)
  
  // Fetch jobs list
  const fetchJobs = useCallback(async () => {
    try {
      const params = new URLSearchParams()
      if (filterBySubmitter && filterBySubmitter !== 'all') {
        params.append('submitted_by', filterBySubmitter)
      }
      const res = await fetch(`${API_BASE}/jobs/?${params.toString()}`)
      const data = await res.json()
      setJobs(data.jobs)
    } catch (err) {
      console.error('Failed to fetch jobs:', err)
    } finally {
      setLoading(false)
    }
  }, [filterBySubmitter])
  
  // Fetch job details
  const fetchJobDetails = useCallback(async (jobId) => {
    try {
      const res = await fetch(`${API_BASE}/jobs/${jobId}`)
      const data = await res.json()
      setJobDetails(data)
    } catch (err) {
      console.error('Failed to fetch job details:', err)
    }
  }, [])
  
  // Poll for progress on running jobs
    useEffect(() => {
      fetchJobs()
      
      const interval = setInterval(() => {
        fetchJobs()
        if (selectedJob && jobDetails?.status === 'running') {
          fetchJobDetails(selectedJob)
        }
      }, 3000)
      
      return () => clearInterval(interval)
    }, [fetchJobs, selectedJob, jobDetails?.status, fetchJobDetails, filterBySubmitter])
  
  // Load job details when selected
  useEffect(() => {
    if (selectedJob) {
      fetchJobDetails(selectedJob)
    }
  }, [selectedJob, fetchJobDetails])
  
  // Handle file upload
  const handleUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    
    setUploading(true)
    const formData = new FormData()
    formData.append('file', file)
    
    // Add submitter name if provided
    const params = new URLSearchParams()
    if (submitterName.trim()) {
      params.append('submitted_by', submitterName.trim())
    }
    
    try {
      const res = await fetch(`${API_BASE}/jobs/upload?${params.toString()}`, {
        method: 'POST',
        body: formData,
      })
      
      if (!res.ok) {
        const error = await res.json()
        alert(`Upload failed: ${error.detail}`)
        return
      }
      
      const job = await res.json()
      setSelectedJob(job.id)
      fetchJobs()
    } catch (err) {
      alert(`Upload failed: ${err.message}`)
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }
  
  // Handle single company lookup
  const handleSingleLookup = async () => {
    if (!singleCompanyName.trim()) {
      alert('Please enter a company name')
      return
    }
    
    setProcessingSingle(true)
    const params = new URLSearchParams()
    params.append('company_name', singleCompanyName.trim())
    if (submitterName.trim()) {
      params.append('submitted_by', submitterName.trim())
    }
    
    try {
      const res = await fetch(`${API_BASE}/jobs/single?${params.toString()}`, {
        method: 'POST',
      })
      
      if (!res.ok) {
        const error = await res.json()
        alert(`Lookup failed: ${error.detail}`)
        return
      }
      
      const job = await res.json()
      setSelectedJob(job.id)
      setSingleCompanyName('')
      fetchJobs()
    } catch (err) {
      alert(`Lookup failed: ${err.message}`)
    } finally {
      setProcessingSingle(false)
    }
  }
  
  // Handle job deletion
  const handleDelete = async (jobId) => {
    if (!confirm('Are you sure you want to delete this job?')) return
    
    try {
      await fetch(`${API_BASE}/jobs/${jobId}`, { method: 'DELETE' })
      if (selectedJob === jobId) {
        setSelectedJob(null)
        setJobDetails(null)
      }
      fetchJobs()
    } catch (err) {
      alert(`Delete failed: ${err.message}`)
    }
  }
  
  // Handle job cancellation
  const handleCancel = async (jobId) => {
    try {
      await fetch(`${API_BASE}/jobs/${jobId}/cancel`, { method: 'POST' })
      fetchJobs()
    } catch (err) {
      alert(`Cancel failed: ${err.message}`)
    }
  }
  
  // Toggle row expansion
  const toggleRow = (companyId) => {
    setExpandedRows(prev => {
      const next = new Set(prev)
      if (next.has(companyId)) {
        next.delete(companyId)
      } else {
        next.add(companyId)
      }
      return next
    })
  }
  
  // Get status color
  const getStatusColor = (status) => {
    switch (status) {
      case 'running': return 'var(--accent-emerald)'
      case 'completed': return '#10b981'
      case 'failed': return '#ef4444'
      case 'cancelled': return '#f59e0b'
      default: return 'var(--text-muted)'
    }
  }
  
  // Filter companies by tier
  const [tierFilter, setTierFilter] = useState('all')
  const filteredCompanies = jobDetails?.companies?.filter(c => 
    tierFilter === 'all' || c.priority_tier === tierFilter
  ) || []
  
  // Tier counts
  const tierCounts = {
    HOT: jobDetails?.companies?.filter(c => c.priority_tier === 'HOT').length || 0,
    WARM: jobDetails?.companies?.filter(c => c.priority_tier === 'WARM').length || 0,
    WATCH: jobDetails?.companies?.filter(c => c.priority_tier === 'WATCH').length || 0,
    COLD: jobDetails?.companies?.filter(c => c.priority_tier === 'COLD').length || 0,
  }

  return (
    <div style={{ minHeight: '100vh', padding: '40px 0' }}>
      <div className="container">
        {/* Header */}
        <header style={{ marginBottom: 40 }} className="animate-fade-in">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <Cpu size={32} style={{ color: 'var(--accent-emerald)' }} />
              <h1 style={{ fontSize: 28 }}>Territory Planner</h1>
            </div>
            <button
              onClick={() => setShowScoringInfo(true)}
              className="btn btn-ghost"
              style={{ padding: '8px 12px', fontSize: 13 }}
              title="Learn about the scoring system"
            >
              <Info size={18} />
              How It Works
            </button>
          </div>
          <p style={{ color: 'var(--text-secondary)', maxWidth: 600 }}>
            AI-powered company research and ranking for GPU infrastructure sales prospects.
          </p>
        </header>
        
        {/* Scoring System Info Modal */}
        {showScoringInfo && (
          <div
            style={{
              position: 'fixed',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              background: 'rgba(0, 0, 0, 0.7)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              zIndex: 1000,
              padding: 20,
            }}
            onClick={() => setShowScoringInfo(false)}
          >
            <div
              className="card"
              style={{
                maxWidth: 700,
                maxHeight: '90vh',
                overflow: 'auto',
                position: 'relative',
              }}
              onClick={(e) => e.stopPropagation()}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
                <h2 style={{ fontSize: 20, margin: 0 }}>Scoring System</h2>
                <button
                  onClick={() => setShowScoringInfo(false)}
                  className="btn btn-ghost"
                  style={{ padding: '4px 8px' }}
                >
                  <X size={20} />
                </button>
              </div>
              <div style={{ color: 'var(--text-secondary)', lineHeight: 1.7, fontSize: 14 }}>
                <p style={{ marginBottom: 16 }}>
                  The Territory Planner uses a four-component scoring model (0–100 total) to rank AI-native startups by GPU infrastructure need. The primary component is <strong style={{ color: 'var(--text-primary)' }}>GPU Use Case (0–50 points)</strong>, which classifies companies into six tiers: <strong style={{ color: 'var(--text-primary)' }}>Tier S (50 points)</strong> for frontier pre-training companies like Anthropic and Mistral; <strong style={{ color: 'var(--text-primary)' }}>Tier A/B/C (45 points each)</strong> for post-training at scale, massive in-house inference, or AI infrastructure platforms; <strong style={{ color: 'var(--text-primary)' }}>Tier D (35 points)</strong> for specialized training or GPU-heavy industries like autonomous vehicles, robotics, and quantitative trading; and <strong style={{ color: 'var(--text-primary)' }}>Tier E (10 points)</strong> for API wrappers or companies with no evidence of custom model training. The remaining components are <strong style={{ color: 'var(--text-primary)' }}>Scale & Budget (0–30 points)</strong> based on funding amount, <strong style={{ color: 'var(--text-primary)' }}>Growth Signals (0–10 points)</strong> for hiring and expansion activity, and <strong style={{ color: 'var(--text-primary)' }}>Confidence (0–10 points)</strong> reflecting data quality.
                </p>
                <p>
                  The system uses Llama-3.3-70B-Instruct via Crusoe Cloud with a structured prompt that includes tier definitions, scoring guidelines, and signal detection rules. The LLM receives Tavily search results formatted as web snippets and analyzes them to extract company information, classify GPU use case tier, and assign scores. The prompt emphasizes critical distinctions: companies using third-party APIs cannot score above 10 points for GPU use case regardless of funding, autonomous vehicle and quant trading firms default to at least Tier D unless they outsource all AI, and companies with "no clear evidence" of training automatically receive Tier E classification. The LLM outputs structured JSON with reasoning, positive/negative signals, and all four score components, which are summed to produce a final 0–100 score that maps to priority tiers: <strong style={{ color: 'var(--tier-hot)' }}>HOT (75+)</strong>, <strong style={{ color: 'var(--tier-warm)' }}>WARM (55–74)</strong>, <strong style={{ color: 'var(--tier-watch)' }}>WATCH (35–54)</strong>, and <strong style={{ color: 'var(--tier-cold)' }}>COLD (&lt;35)</strong>.
                </p>
              </div>
            </div>
          </div>
        )}
        
        {/* Main Content */}
        <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: 24 }}>
          {/* Sidebar - Jobs List */}
          <aside className="stagger-children">
            <div className="card" style={{ marginBottom: 16 }}>
              <div style={{ marginBottom: 12 }}>
                <label style={{ display: 'block', fontSize: 12, color: 'var(--text-muted)', marginBottom: 6 }}>
                  Your Name (optional)
                </label>
                <input
                  type="text"
                  value={submitterName}
                  onChange={(e) => setSubmitterName(e.target.value)}
                  placeholder="Enter your name"
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    background: 'var(--bg-tertiary)',
                    border: '1px solid var(--border-default)',
                    borderRadius: 'var(--radius-md)',
                    color: 'var(--text-primary)',
                    fontSize: 13,
                    fontFamily: 'var(--font-sans)',
                  }}
                />
              </div>
              
              {/* Mode Tabs */}
              <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
                <button
                  onClick={() => setInputMode('csv')}
                  className={`btn ${inputMode === 'csv' ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ flex: 1, padding: '8px 12px', fontSize: 13 }}
                >
                  Upload CSV
                </button>
                <button
                  onClick={() => setInputMode('single')}
                  className={`btn ${inputMode === 'single' ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ flex: 1, padding: '8px 12px', fontSize: 13 }}
                >
                  Single Lookup
                </button>
              </div>
              
              {/* CSV Upload Mode */}
              {inputMode === 'csv' && (
                <label className="btn btn-primary" style={{ width: '100%', cursor: 'pointer' }}>
                  <input
                    type="file"
                    accept=".csv"
                    onChange={handleUpload}
                    style={{ display: 'none' }}
                    disabled={uploading}
                  />
                  {uploading ? (
                    <>
                      <Loader2 size={18} className="animate-spin" />
                      Uploading...
                    </>
                  ) : (
                    <>
                      <Upload size={18} />
                      Upload CSV
                    </>
                  )}
                </label>
              )}
              
              {/* Single Company Lookup Mode */}
              {inputMode === 'single' && (
                <div>
                  <div style={{ marginBottom: 12 }}>
                    <label style={{ display: 'block', fontSize: 12, color: 'var(--text-muted)', marginBottom: 6 }}>
                      Company Name
                    </label>
                    <input
                      type="text"
                      value={singleCompanyName}
                      onChange={(e) => setSingleCompanyName(e.target.value)}
                      onKeyPress={(e) => e.key === 'Enter' && handleSingleLookup()}
                      placeholder="Enter company name"
                      disabled={processingSingle}
                      style={{
                        width: '100%',
                        padding: '8px 12px',
                        background: 'var(--bg-tertiary)',
                        border: '1px solid var(--border-default)',
                        borderRadius: 'var(--radius-md)',
                        color: 'var(--text-primary)',
                        fontSize: 13,
                        fontFamily: 'var(--font-sans)',
                      }}
                    />
                  </div>
                  <button
                    onClick={handleSingleLookup}
                    disabled={processingSingle || !singleCompanyName.trim()}
                    className="btn btn-primary"
                    style={{ width: '100%' }}
                  >
                    {processingSingle ? (
                      <>
                        <Loader2 size={18} className="animate-spin" />
                        Researching...
                      </>
                    ) : (
                      <>
                        <Sparkles size={18} />
                        Research Company
                      </>
                    )}
                  </button>
                </div>
              )}
            </div>
            
            <div className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                <h3 style={{ fontSize: 14, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', margin: 0 }}>
                  Research Jobs
                </h3>
                {jobs.length > 0 && (
                  <select
                    value={filterBySubmitter}
                    onChange={(e) => setFilterBySubmitter(e.target.value)}
                    style={{
                      padding: '4px 8px',
                      background: 'var(--bg-tertiary)',
                      border: '1px solid var(--border-default)',
                      borderRadius: 'var(--radius-sm)',
                      color: 'var(--text-primary)',
                      fontSize: 11,
                      fontFamily: 'var(--font-sans)',
                      cursor: 'pointer',
                    }}
                  >
                    <option value="all">All Users</option>
                    {[...new Set(jobs.map(j => j.submitted_by).filter(Boolean))].map(name => (
                      <option key={name} value={name}>{name}</option>
                    ))}
                  </select>
                )}
              </div>
              
              {loading ? (
                <div style={{ textAlign: 'center', padding: 20 }}>
                  <Loader2 size={24} className="animate-spin" style={{ color: 'var(--text-muted)' }} />
                </div>
              ) : jobs.length === 0 ? (
                <p style={{ color: 'var(--text-muted)', fontSize: 14, textAlign: 'center', padding: 20 }}>
                  No jobs yet. Upload a CSV to get started.
                </p>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {jobs.map(job => (
                    <div
                      key={job.id}
                      onClick={() => setSelectedJob(job.id)}
                      className="card-hover"
                      style={{
                        padding: 14,
                        borderRadius: 'var(--radius-md)',
                        cursor: 'pointer',
                        background: selectedJob === job.id ? 'var(--bg-hover)' : 'transparent',
                        border: `1px solid ${selectedJob === job.id ? 'var(--border-strong)' : 'transparent'}`,
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                          <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <FileSpreadsheet size={16} style={{ color: 'var(--accent-emerald)' }} />
                            <span style={{ fontSize: 14, fontWeight: 500 }}>Job #{job.id}</span>
                          </span>
                          {job.submitted_by && (
                            <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 24 }}>
                              by {job.submitted_by}
                            </span>
                          )}
                        </div>
                        <span style={{ 
                          fontSize: 11, 
                          fontFamily: 'var(--font-mono)', 
                          color: getStatusColor(job.status),
                          textTransform: 'uppercase',
                        }}>
                          {job.status === 'running' && <Loader2 size={10} className="animate-spin" style={{ marginRight: 4, display: 'inline' }} />}
                          {job.status}
                        </span>
                      </div>
                      
                      <div className="progress-bar" style={{ marginBottom: 8 }}>
                        <div 
                          className="progress-bar-fill" 
                          style={{ 
                            width: `${job.total_companies > 0 ? ((job.completed_companies + job.failed_companies) / job.total_companies) * 100 : 0}%` 
                          }}
                        />
                      </div>
                      
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--text-muted)' }}>
                        <span>{job.completed_companies}/{job.total_companies} companies</span>
                        <span>{new Date(job.created_at).toLocaleDateString()}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </aside>
          
          {/* Main Panel - Results */}
          <main>
            {!selectedJob ? (
              <div className="card animate-fade-in" style={{ textAlign: 'center', padding: 60 }}>
                <Sparkles size={48} style={{ color: 'var(--text-muted)', marginBottom: 16 }} />
                <h2 style={{ fontSize: 20, marginBottom: 8 }}>No Job Selected</h2>
                <p style={{ color: 'var(--text-secondary)' }}>
                  Upload a CSV or select an existing job to view results.
                </p>
              </div>
            ) : !jobDetails ? (
              <div className="card" style={{ textAlign: 'center', padding: 60 }}>
                <Loader2 size={32} className="animate-spin" style={{ color: 'var(--accent-emerald)' }} />
              </div>
            ) : (
              <div className="animate-fade-in">
                {/* Job Header */}
                <div className="card" style={{ marginBottom: 16 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
                    <div>
                      <h2 style={{ fontSize: 20, marginBottom: 4 }}>{jobDetails.name || `Job #${jobDetails.id}`}</h2>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                        {jobDetails.original_filename && (
                          <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>
                            Source: {jobDetails.original_filename}
                          </p>
                        )}
                        {jobDetails.submitted_by && (
                          <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>
                            Submitted by: <span style={{ color: 'var(--text-secondary)' }}>{jobDetails.submitted_by}</span>
                          </p>
                        )}
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: 8 }}>
                      {jobDetails.status === 'running' && (
                        <button className="btn btn-secondary" onClick={() => handleCancel(jobDetails.id)}>
                          <XCircle size={16} />
                          Cancel
                        </button>
                      )}
                      <a 
                        href={`${API_BASE}/jobs/${jobDetails.id}/export`} 
                        className="btn btn-secondary"
                        download
                      >
                        <Download size={16} />
                        Export CSV
                      </a>
                      <button 
                        className="btn btn-ghost" 
                        onClick={() => handleDelete(jobDetails.id)}
                        disabled={jobDetails.status === 'running'}
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </div>
                  
                  {/* Progress */}
                  <div style={{ marginBottom: 16 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                      <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                        {jobDetails.status === 'running' ? 'Processing...' : 'Complete'}
                      </span>
                      <span style={{ fontSize: 13, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                        {jobDetails.completed_companies + jobDetails.failed_companies}/{jobDetails.total_companies}
                      </span>
                    </div>
                    <div className="progress-bar" style={{ height: 8 }}>
                      <div 
                        className="progress-bar-fill" 
                        style={{ 
                          width: `${jobDetails.total_companies > 0 ? ((jobDetails.completed_companies + jobDetails.failed_companies) / jobDetails.total_companies) * 100 : 0}%` 
                        }}
                      />
                    </div>
                  </div>
                  
                  {/* Tier Summary */}
                  <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                    {[
                      { tier: 'all', label: 'All', count: jobDetails.companies?.length || 0 },
                      { tier: 'HOT', label: 'Hot', count: tierCounts.HOT },
                      { tier: 'WARM', label: 'Warm', count: tierCounts.WARM },
                      { tier: 'WATCH', label: 'Watch', count: tierCounts.WATCH },
                      { tier: 'COLD', label: 'Cold', count: tierCounts.COLD },
                    ].map(({ tier, label, count }) => (
                      <button
                        key={tier}
                        onClick={() => setTierFilter(tier)}
                        className={`btn ${tierFilter === tier ? 'btn-primary' : 'btn-ghost'}`}
                        style={{ padding: '8px 14px', fontSize: 13 }}
                      >
                        {label} ({count})
                      </button>
                    ))}
                  </div>
                </div>
                
                {/* Results Table */}
                <div className="card table-container" style={{ padding: 0 }}>
                  <table>
                    <thead>
                      <tr>
                        <th style={{ width: 40 }}>#</th>
                        <th>Company</th>
                        <th>Tier</th>
                        <th>GPU Use Case</th>
                        <th>Funding</th>
                        <th>Score</th>
                        <th style={{ width: 40 }}></th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredCompanies.map((company, idx) => (
                        <React.Fragment key={company.id}>
                          <tr 
                            onClick={() => toggleRow(company.id)}
                            style={{ cursor: 'pointer' }}
                          >
                            <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', fontSize: 13 }}>
                              {idx + 1}
                            </td>
                            <td>
                              <div style={{ fontWeight: 500 }}>{company.name}</div>
                              {company.industry && (
                                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{company.industry}</div>
                              )}
                            </td>
                            <td>
                              {company.priority_tier ? (
                                <TierBadge tier={company.priority_tier} />
                              ) : (
                                <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                                  {company.status === 'researching' ? (
                                    <><Loader2 size={12} className="animate-spin" style={{ marginRight: 4 }} /> Researching...</>
                                  ) : company.status === 'pending' ? (
                                    'Pending'
                                  ) : company.status === 'failed' ? (
                                    <span style={{ color: 'var(--tier-hot)' }}>Failed</span>
                                  ) : (
                                    'N/A'
                                  )}
                                </span>
                              )}
                            </td>
                            <td>
                              {company.gpu_use_case_tier ? (
                                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                  <GPUTierBadge tier={company.gpu_use_case_tier} />
                                </div>
                              ) : (
                                <span style={{ color: 'var(--text-muted)' }}>-</span>
                              )}
                            </td>
                            <td style={{ fontFamily: 'var(--font-mono)', fontSize: 13 }}>
                              {company.funding_millions 
                                ? `$${company.funding_millions >= 1000 
                                    ? (company.funding_millions / 1000).toFixed(1) + 'B' 
                                    : company.funding_millions.toFixed(0) + 'M'}`
                                : company.total_funding || '-'}
                            </td>
                            <td>
                              <ScoreBar score={company.score_total} />
                            </td>
                            <td>
                              {expandedRows.has(company.id) ? (
                                <ChevronUp size={16} style={{ color: 'var(--text-muted)' }} />
                              ) : (
                                <ChevronDown size={16} style={{ color: 'var(--text-muted)' }} />
                              )}
                            </td>
                          </tr>
                          {expandedRows.has(company.id) && company.status === 'completed' && (
                            <CompanyDetails company={company} />
                          )}
                        </React.Fragment>
                      ))}
                    </tbody>
                  </table>
                  
                  {filteredCompanies.length === 0 && (
                    <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>
                      No companies match the selected filter.
                    </div>
                  )}
                </div>
              </div>
            )}
          </main>
        </div>
      </div>
    </div>
  )
}

