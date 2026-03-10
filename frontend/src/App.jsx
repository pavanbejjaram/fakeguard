import { useState, useEffect, useCallback } from 'react'
import { api } from './api'

const vc  = v => v === 'FAKE' ? 'fake' : v === 'REAL' ? 'real' : 'unc'
const vi  = v => v === 'REAL' ? '✅' : v === 'FAKE' ? '🚨' : '⚠️'
const pct = n => `${Math.round(n * 100)}%`
const fmt = iso => new Date(iso).toLocaleString(undefined, { month:'short', day:'numeric', hour:'2-digit', minute:'2-digit' })
const fmtD = iso => new Date(iso).toLocaleDateString(undefined, { month:'short', day:'numeric' })
const clamp = (n, lo, hi) => Math.max(lo, Math.min(hi, n))

function AuthPage({ onAuth }) {
  const [tab,  setTab]  = useState('login')
  const [form, setForm] = useState({ username:'', email:'', password:'', confirm:'' })
  const [msg,  setMsg]  = useState(null)
  const [busy, setBusy] = useState(false)
  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }))
  async function submit() {
    setMsg(null)
    const { username, email, password, confirm } = form
    if (!username.trim() || !password.trim()) { setMsg({ t:'err', s:'Fill in all required fields.' }); return }
    if (tab === 'register') {
      if (!email.trim())        { setMsg({ t:'err', s:'Email is required.' }); return }
      if (password !== confirm) { setMsg({ t:'err', s:"Passwords don't match." }); return }
      if (password.length < 6)  { setMsg({ t:'err', s:'Password must be at least 6 characters.' }); return }
    }
    setBusy(true)
    try {
      const data = tab === 'login'
        ? await api.login(username, password)
        : await api.register(username, email, password)
      localStorage.setItem('fg_token', data.access_token)
      localStorage.setItem('fg_username', data.username)
      onAuth(data.username)
    } catch (e) { setMsg({ t:'err', s: e.message }) }
    finally { setBusy(false) }
  }
  return (
    <div className="auth-page">
      <div className="brand">
        <div className="brand-eyebrow"></div>
        <h1 className="brand-h1">Truth or<br /><b>Fiction?</b></h1>
        <p className="brand-p">Paste any headline or article. Our trained PassiveAggressiveClassifier (92%+ accuracy) instantly flags misinformation — optionally boosted by Claude AI.</p>
        <div className="brand-chips">
          <span className="chip">🤖 ML Model</span><span className="chip">🧠 Claude AI</span>
          <span className="chip">📊 Dashboard</span><span className="chip">🔥 Trending</span>
          <span className="chip">🔖 Bookmarks</span><span className="chip">📄 PDF Export</span>
        </div>
        <div className="brand-footer">FAKEGUARD v2 // FASTAPI + REACT + SCIKIT-LEARN</div>
      </div>
      <div className="form-side">
        <div className="form-card">
          <div className="tabs">
            <button className={`tab ${tab==='login'?'on':''}`}    onClick={() => { setTab('login');    setMsg(null) }}>Login</button>
            <button className={`tab ${tab==='register'?'on':''}`} onClick={() => { setTab('register'); setMsg(null) }}>Register</button>
          </div>
          <div className="field"><label>Username</label>
            <input value={form.username} onChange={set('username')} placeholder="your_username" onKeyDown={e => e.key==='Enter' && submit()} /></div>
          {tab === 'register' && (
            <div className="field"><label>Email</label>
              <input type="email" value={form.email} onChange={set('email')} placeholder="you@example.com" onKeyDown={e => e.key==='Enter' && submit()} /></div>
          )}
          <div className="field"><label>Password</label>
            <input type="password" value={form.password} onChange={set('password')} placeholder="••••••••" onKeyDown={e => e.key==='Enter' && submit()} /></div>
          {tab === 'register' && (
            <div className="field"><label>Confirm Password</label>
              <input type="password" value={form.confirm} onChange={set('confirm')} placeholder="••••••••" onKeyDown={e => e.key==='Enter' && submit()} /></div>
          )}
          <button className="btn-main" onClick={submit} disabled={busy}>{busy ? 'Please wait…' : tab === 'login' ? 'Sign In' : 'Create Account'}</button>
          {msg && <div className={`msg ${msg.t}`}>{msg.s}</div>}
        </div>
      </div>
    </div>
  )
}

function Topbar({ username, page, setPage, onLogout }) {
  const nav = [
    { id:'checker',   label:'🔍 Checker' },
    { id:'dashboard', label:'📊 Dashboard' },
    { id:'trending',  label:'🔥 Trending' },
    { id:'bookmarks', label:'🔖 Bookmarks' },
  ]
  return (
    <nav className="topbar">
      <div className="logo">Fake<span>Guard</span></div>
      <div className="topbar-nav">
        {nav.map(n => (
          <button key={n.id} className={`nav-btn ${page===n.id?'active':''}`} onClick={() => setPage(n.id)}>{n.label}</button>
        ))}
      </div>
      <div className="topbar-right">
        <span className="topbar-user">👤 {username}</span>
        <button className="btn-logout" onClick={onLogout}>Logout</button>
      </div>
    </nav>
  )
}

function CheckerPage() {
  const [apiKey,    setApiKey]    = useState(localStorage.getItem('fg_api') || '')
  const [keySaved,  setKeySaved]  = useState(!!localStorage.getItem('fg_api'))
  const [text,      setText]      = useState('')
  const [loading,   setLoading]   = useState(false)
  const [result,    setResult]    = useState(null)
  const [error,     setError]     = useState(null)
  const [history,   setHistory]   = useState([])
  const [stats,     setStats]     = useState(null)
  const [modelInfo, setModelInfo] = useState(null)
  const [bookmarked,setBookmarked]= useState({})
  const [exporting, setExporting] = useState(null)

  const refresh = useCallback(async () => {
    try {
      const [h, s, m, bms] = await Promise.all([api.history(), api.stats(), api.modelInfo(), api.getBookmarks()])
      setHistory(h); setStats(s); setModelInfo(m)
      const bmap = {}; bms.forEach(b => { bmap[b.check_id] = true }); setBookmarked(bmap)
    } catch {}
  }, [])
  useEffect(() => { refresh() }, [refresh])

  function saveKey() {
    if (!apiKey.trim().startsWith('sk-')) { alert('Enter a valid Anthropic key (starts with sk-)'); return }
    localStorage.setItem('fg_api', apiKey.trim()); setKeySaved(true)
  }
  function clearKey() { localStorage.removeItem('fg_api'); setApiKey(''); setKeySaved(false) }

  async function analyze() {
    if (!text.trim()) return
    setLoading(true); setResult(null); setError(null)
    try { const r = await api.check(text, keySaved ? localStorage.getItem('fg_api') : null); setResult(r); refresh() }
    catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }
  async function toggleBookmark(id) {
    if (bookmarked[id]) { await api.removeBookmark(id); setBookmarked(b => { const n={...b}; delete n[id]; return n }) }
    else { await api.addBookmark(id); setBookmarked(b => ({ ...b, [id]: true })) }
  }
  async function exportPDF(id) {
    setExporting(id); try { await api.exportPDF(id) } catch(e){ alert('Export failed: '+e.message) } finally { setExporting(null) }
  }

  const trained = modelInfo && modelInfo.accuracy
  return (
    <main className="main">
      <h1 className="page-title">Detect <span>Fake</span> News</h1>
      <p className="page-sub"></p>
      {modelInfo && (
        <div className={`model-banner ${trained?'':'warn'}`}>
          {trained ? `✅ ${modelInfo.model_name} · ${(modelInfo.accuracy*100).toFixed(1)}% accuracy` : '⚠️ Model not trained. Run: python ml/train_model.py'}
        </div>
      )}
      {stats && (
        <div className="stats-row">
          <div className="stat all">📊 {stats.total} checked</div>
          <div className="stat fake">🚨 {stats.fake} fake</div>
          <div className="stat real">✅ {stats.real} real</div>
          <div className="stat unc">⚠️ {stats.uncertain} uncertain</div>
        </div>
      )}
      <div className="card">
        {!keySaved ? (
          <div className="api-row">
            <input value={apiKey} onChange={e=>setApiKey(e.target.value)} placeholder="Optional: Anthropic API key (sk-ant-…)" onKeyDown={e=>e.key==='Enter'&&saveKey()} />
            <button className="btn-main" style={{width:'auto',padding:'10px 20px',marginTop:0}} onClick={saveKey}>Save</button>
          </div>
        ) : (
          <div className="api-saved">🔑 AI key active — dual ML + Claude analysis enabled
            <button className="btn-xs" onClick={clearKey}>change</button>
          </div>
        )}
        <textarea className="textarea" value={text} onChange={e=>setText(e.target.value)} placeholder="Paste any news headline, article, or claim to fact-check…" />
        <div className="charcount">{text.length} / 8 000</div>
        <button className="btn-analyze" onClick={analyze} disabled={loading||!text.trim()}>
          {loading ? 'Analyzing…' : `🔍  Analyze${keySaved?' with ML + Claude AI':' with ML Model'}`}
        </button>
        {loading && <div className="loading"><div className="spin" /><span>{keySaved?'Running ML · Querying Claude AI · Fusing scores…':'Running TF-IDF + PAC model…'}</span></div>}
        {error && <div className="err-box">⚠️ {error}</div>}
        {result && !error && (() => {
          const fc = vc(result.final_verdict)
          return (
            <div className="result">
              <div className="dual">
                <div className="panel ml">
                  <div className="panel-tag">🤖 ML — {result.ml.model.split('(')[0].trim()}</div>
                  <div className={`panel-v v${vc(result.ml.verdict)}`}>{vi(result.ml.verdict)} {result.ml.verdict}</div>
                  <div className="panel-c">Confidence: {pct(result.ml.confidence)}<br/>Fake: {pct(result.ml.fake_prob)} · Real: {pct(result.ml.real_prob)}</div>
                </div>
                <div className="panel ai">
                  <div className="panel-tag">🧠 Claude AI</div>
                  <div className={`panel-v v${vc(result.ai.verdict)}`}>{vi(result.ai.verdict)} {result.ai.verdict}</div>
                  <div className="panel-c">Confidence: {result.ai.confidence}%</div>
                </div>
              </div>
              <div className={`final-card ${fc}`}>
                <div className="final-top">
                  <span className="final-icon">{vi(result.final_verdict)}</span>
                  <span className="final-v">Final Verdict: {result.final_verdict}</span>
                  <div className="result-actions">
                    <button className={`action-btn bm${bookmarked[result.id]?' bm-on':''}`} onClick={()=>toggleBookmark(result.id)}>
                      {bookmarked[result.id]?'🔖 Saved':'🏷️ Bookmark'}
                    </button>
                    <button className="action-btn pdf" onClick={()=>exportPDF(result.id)} disabled={exporting===result.id}>
                      {exporting===result.id?'⏳':'📄'} Export PDF
                    </button>
                  </div>
                </div>
                <div className="bar-wrap">
                  <div className="bar-label"><span>Combined Score</span><span>{pct(result.final_score)}</span></div>
                  <div className="bar"><div className="bar-fill" style={{width:`${clamp(result.final_score*100,0,100)}%`}}/></div>
                </div>
                <div className="signals">
                  <span className="sig-chip">📡 ML: {result.ml.verdict} ({pct(result.ml.confidence)})</span>
                  <span className="sig-chip">🧠 AI: {result.ai.verdict} ({result.ai.confidence}%)</span>
                  <span className="sig-chip">⚡ Boost: {pct(result.ml.signals.boost)}</span>
                </div>
                <p className="ai-text">{result.ai.summary}</p>
              </div>
            </div>
          )
        })()}
      </div>
      {history.length > 0 && (
        <div className="history">
          <div className="sec-title">Recent Checks ({history.length})</div>
          {history.map(h => (
            <div className="h-item" key={h.id}>
              <div className={`h-dot ${vc(h.final_verdict)}`}/>
              <span className="h-txt">{h.news_snippet}</span>
              <span className={`h-v ${vc(h.final_verdict)}`}>{h.final_verdict}</span>
              <button className={`h-bm${bookmarked[h.id]?' h-bm-on':''}`} onClick={()=>toggleBookmark(h.id)} title="Bookmark">{bookmarked[h.id]?'🔖':'🏷️'}</button>
              <button className="h-pdf" onClick={()=>exportPDF(h.id)} disabled={exporting===h.id} title="Export PDF">{exporting===h.id?'⏳':'📄'}</button>
              <span className="h-d">{fmt(h.checked_at)}</span>
            </div>
          ))}
        </div>
      )}
    </main>
  )
}

function PieChart({ fake, real, uncertain }) {
  const total = fake + real + uncertain || 1
  const sz = 130, cx = sz/2, cy = sz/2, r = sz/2 - 8
  const slices = [{val:real,color:'#22c55e'},{val:fake,color:'#ff4a1c'},{val:uncertain,color:'#f59e0b'}]
  let angle = -Math.PI/2
  const paths = slices.map(s => {
    const sw = (s.val/total)*2*Math.PI
    const x1=cx+r*Math.cos(angle), y1=cy+r*Math.sin(angle)
    angle+=sw
    const x2=cx+r*Math.cos(angle), y2=cy+r*Math.sin(angle)
    return {...s, d:`M${cx},${cy} L${x1},${y1} A${r},${r} 0 ${sw>Math.PI?1:0},1 ${x2},${y2} Z`}
  })
  return (
    <svg width={sz} height={sz} style={{filter:'drop-shadow(0 4px 16px rgba(0,0,0,.5))'}}>
      {paths.map((p,i) => p.val>0 && <path key={i} d={p.d} fill={p.color}/>)}
      <circle cx={cx} cy={cy} r={r*.52} fill="#0d0d18"/>
      <text x={cx} y={cy-3} textAnchor="middle" fill="#f0ece0" fontFamily="serif" fontWeight="900" fontSize={20}>{total}</text>
      <text x={cx} y={cy+13} textAnchor="middle" fill="rgba(240,236,224,.35)" fontFamily="monospace" fontSize={8}>checks</text>
    </svg>
  )
}

function BarSparkline({ data }) {
  const max = Math.max(...data.map(d=>d.count), 1)
  return (
    <div style={{display:'flex',alignItems:'flex-end',gap:2,height:56,padding:'4px 0'}}>
      {data.map((d,i)=>(
        <div key={i} title={`${d.date}: ${d.count}`} style={{
          flex:1,borderRadius:2,
          background:d.count>0?'#ff4a1c':'rgba(255,255,255,.06)',
          height:`${Math.max((d.count/max)*100,d.count>0?8:3)}%`,
          transition:'height .3s'
        }}/>
      ))}
    </div>
  )
}

function DashboardPage() {
  const [data,setData]=useState(null), [busy,setBusy]=useState(true), [exporting,setEx]=useState(null)
  useEffect(()=>{ api.dashboard().then(d=>{setData(d);setBusy(false)}).catch(()=>setBusy(false)) },[])
  async function exportPDF(id){ setEx(id); try{await api.exportPDF(id)}catch(e){alert('Export failed: '+e.message)} finally{setEx(null)} }
  if(busy) return <div style={{display:'flex',alignItems:'center',justifyContent:'center',minHeight:400,gap:12,color:'rgba(240,236,224,.3)',fontFamily:'monospace',fontSize:12}}><div className="spin"/>Loading dashboard…</div>
  if(!data||data.total===0) return (
    <main className="main" style={{textAlign:'center',paddingTop:80}}>
      <div style={{fontSize:56,marginBottom:16}}>📊</div>
      <p style={{fontFamily:"'Playfair Display',serif",fontSize:22,color:'#f0ece0',marginBottom:8}}>No checks yet</p>
      <p style={{fontFamily:'monospace',fontSize:11,color:'rgba(240,236,224,.35)'}}>Start analyzing news to see your dashboard</p>
    </main>
  )
  const {total,fake,real,uncertain,checks_by_day,verdict_trend,recent,streak,member_since}=data
  return (
    <main className="main">
      <h1 className="page-title" style={{marginBottom:4}}>Your <span>Dashboard</span></h1>
      <p className="page-sub">Member since {member_since} · {streak>0?`🔥 ${streak}-day streak`:'No active streak'}</p>
      <div className="dash-top">
        <div className="card dash-pie-card">
          <PieChart fake={fake} real={real} uncertain={uncertain}/>
          <div className="dash-legend">
            {[['#22c55e','✅','Real',real],['#ff4a1c','🚨','Fake',fake],['#f59e0b','⚠️','Unc.',uncertain]].map(([c,ic,lb,n])=>(
              <div key={lb} className="legend-item">
                <div style={{width:8,height:8,borderRadius:2,background:c,flexShrink:0}}/>
                <span style={{color:'rgba(240,236,224,.4)',fontSize:10}}>{ic} {lb}</span>
                <span style={{fontFamily:"'Playfair Display',serif",fontWeight:900,fontSize:16,color:c,marginLeft:'auto'}}>{n}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="dash-stats">
          {[{icon:'📊',label:'Total Checks',val:total,color:'#6366f1'},{icon:'🚨',label:'Fake Detected',val:fake,color:'#ff4a1c'},{icon:'✅',label:'Real Verified',val:real,color:'#22c55e'},{icon:'🔥',label:'Day Streak',val:streak,color:'#f59e0b'}].map(s=>(
            <div key={s.label} className="card stat-card">
              <div className="stat-card-label">{s.icon} {s.label}</div>
              <div className="stat-card-val" style={{color:s.color}}>{s.val}</div>
            </div>
          ))}
        </div>
      </div>
      <div className="card" style={{marginBottom:16,padding:'20px 22px'}}>
        <div className="dash-sec-title">Activity — Last 30 Days</div>
        <BarSparkline data={checks_by_day}/>
        <div style={{display:'flex',justifyContent:'space-between',fontFamily:'monospace',fontSize:9,color:'rgba(240,236,224,.2)',marginTop:4}}><span>30 days ago</span><span>Today</span></div>
      </div>
      <div className="card" style={{marginBottom:16,padding:'20px 22px'}}>
        <div className="dash-sec-title">Fake vs Real — Last 14 Days</div>
        <div style={{display:'flex',gap:6,marginTop:8}}>
          {verdict_trend.map((d,i)=>{
            const t=(d.fake||0)+(d.real||0)||1
            return (
              <div key={i} style={{flex:1,display:'flex',flexDirection:'column',alignItems:'center',gap:2}}>
                <div style={{width:'100%',height:52,display:'flex',flexDirection:'column',justifyContent:'flex-end',gap:1}}>
                  <div style={{width:'100%',background:'#22c55e',borderRadius:2,opacity:.8,height:`${(d.real/t)*52}px`,transition:'height .3s'}}/>
                  <div style={{width:'100%',background:'#ff4a1c',borderRadius:2,opacity:.8,height:`${(d.fake/t)*52}px`,transition:'height .3s'}}/>
                </div>
                <div style={{fontFamily:'monospace',fontSize:7,color:'rgba(240,236,224,.2)',transform:'rotate(-45deg)',whiteSpace:'nowrap',marginTop:4}}>{d.date}</div>
              </div>
            )
          })}
        </div>
        <div style={{display:'flex',gap:14,marginTop:14}}>
          {[['#22c55e','Real'],['#ff4a1c','Fake']].map(([c,l])=>(
            <div key={l} style={{display:'flex',alignItems:'center',gap:6,fontFamily:'monospace',fontSize:9,color:'rgba(240,236,224,.4)'}}>
              <div style={{width:8,height:8,borderRadius:2,background:c}}/>{l}
            </div>
          ))}
        </div>
      </div>
      <div className="card" style={{padding:'20px 22px'}}>
        <div className="dash-sec-title">Recent Checks</div>
        {recent.map(r=>(
          <div key={r.id} className="dash-row">
            <div className={`h-dot ${vc(r.final_verdict)}`}/>
            <span className="dash-snip">{r.snippet}</span>
            <span className={`h-v ${vc(r.final_verdict)}`}>{r.final_verdict}</span>
            <button className="h-pdf" onClick={()=>exportPDF(r.id)} disabled={exporting===r.id} title="Export PDF">{exporting===r.id?'⏳':'📄'}</button>
            <span className="h-d">{fmtD(r.checked_at)}</span>
          </div>
        ))}
      </div>
    </main>
  )
}

function TrendingPage() {
  const [data,setData]=useState(null), [hours,setHours]=useState(24), [busy,setBusy]=useState(true)
  const load = useCallback((h)=>{ setBusy(true); api.trending(h).then(d=>{setData(d);setBusy(false)}).catch(()=>setBusy(false)) },[])
  useEffect(()=>{ load(hours) },[hours,load])
  const PERIODS=[{label:'Last 24h',val:24},{label:'Last 48h',val:48},{label:'Last 7d',val:168},{label:'All time',val:87600}]
  return (
    <main className="main">
      <h1 className="page-title">🔥 <span>Trending</span> Fake News</h1>
      <p className="page-sub">Most-checked news across all users — live community intelligence</p>
      <div className="trend-filters">
        {PERIODS.map(p=><button key={p.val} className={`trend-filter${hours===p.val?' on':''}`} onClick={()=>setHours(p.val)}>{p.label}</button>)}
      </div>
      {data&&data.stats&&(
        <div className="stats-row" style={{marginBottom:16}}>
          <div className="stat all">📊 {data.stats.total_checks} checks</div>
          <div className="stat fake">🚨 {data.stats.fake_count} fake</div>
          <div className="stat real">✅ {data.stats.real_count} real</div>
          <div className="stat unc">⚠️ {data.stats.fake_pct}% fake rate</div>
        </div>
      )}
      {busy&&<div style={{display:'flex',alignItems:'center',gap:12,padding:'48px 0',color:'rgba(240,236,224,.3)',fontFamily:'monospace',fontSize:12}}><div className="spin"/>Loading trending…</div>}
      {!busy&&data&&data.trending.length===0&&(
        <div className="card" style={{textAlign:'center',padding:'60px 24px'}}>
          <div style={{fontSize:48,marginBottom:12}}>🌐</div>
          <p style={{color:'rgba(240,236,224,.4)',fontFamily:'monospace',fontSize:12}}>No checks in this period yet.</p>
        </div>
      )}
      {!busy&&data&&data.trending.map((item,i)=>(
        <div key={i} className="card trend-card">
          <div className="trend-card-top">
            <div className="trend-rank">#{i+1}</div>
            <div className={`trend-verdict verdict-${vc(item.dominant_verdict)}`}>{vi(item.dominant_verdict)} {item.dominant_verdict}</div>
            <div className="trend-count">{item.check_count} checks</div>
          </div>
          <p className="trend-text">{item.snippet}</p>
          <div className="trend-bar-row">
            <div className="trend-mini-bar">
              {item.fake_count+item.real_count>0&&<>
                <div style={{width:`${(item.real_count/(item.fake_count+item.real_count))*100}%`,background:'#22c55e',height:'100%',borderRadius:'3px 0 0 3px'}}/>
                <div style={{width:`${(item.fake_count/(item.fake_count+item.real_count))*100}%`,background:'#ff4a1c',height:'100%',borderRadius:'0 3px 3px 0'}}/>
              </>}
            </div>
            <span className="trend-meta">✅ {item.real_count} · 🚨 {item.fake_count} · ⚠️ {item.uncertain_count}</span>
            <span className="trend-time">{fmt(item.last_checked)}</span>
          </div>
        </div>
      ))}
    </main>
  )
}

function BookmarksPage() {
  const [items,setItems]=useState([]), [busy,setBusy]=useState(true), [exporting,setEx]=useState(null), [removing,setRem]=useState(null), [filter,setFilter]=useState('ALL')
  const load = ()=>{ setBusy(true); api.getBookmarks().then(d=>{setItems(d);setBusy(false)}).catch(()=>setBusy(false)) }
  useEffect(()=>{ load() },[])
  async function remove(id){ setRem(id); await api.removeBookmark(id); setItems(p=>p.filter(b=>b.check_id!==id)); setRem(null) }
  async function exportPDF(id){ setEx(id); try{await api.exportPDF(id)}catch(e){alert('Export failed: '+e.message)} finally{setEx(null)} }
  const FILTERS=['ALL','FAKE','REAL','UNCERTAIN']
  const visible=filter==='ALL'?items:items.filter(b=>b.final_verdict===filter)
  return (
    <main className="main">
      <h1 className="page-title">🔖 <span>Bookmarks</span></h1>
      <p className="page-sub">{items.length} saved fact-checks · Export any as PDF</p>
      <div className="trend-filters" style={{marginBottom:20}}>
        {FILTERS.map(f=>(
          <button key={f} className={`trend-filter${filter===f?' on':''}`} onClick={()=>setFilter(f)}>
            {f==='ALL'?`All (${items.length})`:f==='FAKE'?`🚨 Fake (${items.filter(b=>b.final_verdict==='FAKE').length})`:f==='REAL'?`✅ Real (${items.filter(b=>b.final_verdict==='REAL').length})`:`⚠️ Uncertain (${items.filter(b=>b.final_verdict==='UNCERTAIN').length})`}
          </button>
        ))}
      </div>
      {busy&&<div style={{display:'flex',alignItems:'center',gap:12,padding:'48px 0',color:'rgba(240,236,224,.3)',fontFamily:'monospace',fontSize:12}}><div className="spin"/>Loading bookmarks…</div>}
      {!busy&&visible.length===0&&(
        <div className="card" style={{textAlign:'center',padding:'60px 24px'}}>
          <div style={{fontSize:48,marginBottom:12}}>🔖</div>
          <p style={{color:'rgba(240,236,224,.4)',fontFamily:'monospace',fontSize:12}}>
            {items.length===0?'No bookmarks yet — save checks using the 🏷️ button':'No bookmarks match this filter'}
          </p>
        </div>
      )}
      {!busy&&visible.map(b=>(
        <div key={b.bookmark_id} className="card bm-card">
          <div className="bm-header">
            <div className={`bm-verdict verdict-${vc(b.final_verdict)}`}>{vi(b.final_verdict)} {b.final_verdict}</div>
            <div className="bm-conf">{b.ml_confidence}% confidence</div>
            <div className="bm-date">Saved {fmtD(b.saved_at)}</div>
          </div>
          <p className="bm-text">{b.snippet}</p>
          {b.ai_summary&&!b.ai_summary.startsWith('No AI')&&<p className="bm-ai">🧠 {b.ai_summary}</p>}
          <div className="bm-actions">
            <button className="action-btn pdf" onClick={()=>exportPDF(b.check_id)} disabled={exporting===b.check_id}>{exporting===b.check_id?'⏳ Generating…':'📄 Export PDF'}</button>
            <button className="action-btn remove" onClick={()=>remove(b.check_id)} disabled={removing===b.check_id}>{removing===b.check_id?'⏳':'🗑️ Remove'}</button>
            <span className="bm-meta">Check #{b.check_id} · {fmt(b.checked_at)}</span>
          </div>
        </div>
      ))}
    </main>
  )
}

function AppShell({ username, onLogout }) {
  const [page, setPage] = useState('checker')
  async function handleLogout() {
    try { await api.logout() } catch {}
    localStorage.removeItem('fg_token'); localStorage.removeItem('fg_username'); onLogout()
  }
  const PAGE_MAP = { checker:<CheckerPage/>, dashboard:<DashboardPage/>, trending:<TrendingPage/>, bookmarks:<BookmarksPage/> }
  return (
    <div className="app">
      <Topbar username={username} page={page} setPage={setPage} onLogout={handleLogout}/>
      {PAGE_MAP[page]}
    </div>
  )
}

export default function App() {
  const [user, setUser] = useState(() => localStorage.getItem('fg_username'))
  if (user) return <AppShell username={user} onLogout={() => setUser(null)} />
  return <AuthPage onAuth={setUser} />
}
