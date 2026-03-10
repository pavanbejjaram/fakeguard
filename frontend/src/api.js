const BASE = '/api'
const tok  = () => localStorage.getItem('fg_token')
const hdr  = () => ({
  'Content-Type': 'application/json',
  ...(tok() ? { Authorization: `Bearer ${tok()}` } : {}),
})
async function go(res) {
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`)
  return data
}
export const api = {
  register:  (username,email,password) => fetch(`${BASE}/auth/register`,{method:'POST',headers:hdr(),body:JSON.stringify({username,email,password})}).then(go),
  login:     (username,password)       => fetch(`${BASE}/auth/login`,   {method:'POST',headers:hdr(),body:JSON.stringify({username,password})}).then(go),
  logout:    ()                        => fetch(`${BASE}/auth/logout`,  {method:'POST',headers:hdr()}).then(go),
  check:     (news_text,api_key)       => fetch(`${BASE}/check`,        {method:'POST',headers:hdr(),body:JSON.stringify({news_text,api_key:api_key||null})}).then(go),
  history:   ()                        => fetch(`${BASE}/history`,      {headers:hdr()}).then(go),
  stats:     ()                        => fetch(`${BASE}/stats`,        {headers:hdr()}).then(go),
  modelInfo: ()                        => fetch(`${BASE}/model-info`,   {headers:hdr()}).then(go),
  dashboard: ()                        => fetch(`${BASE}/dashboard`,    {headers:hdr()}).then(go),
  trending:  (hours=24)                => fetch(`${BASE}/trending?hours=${hours}`,{headers:hdr()}).then(go),
  getBookmarks: ()                     => fetch(`${BASE}/bookmarks`,    {headers:hdr()}).then(go),
  addBookmark:  (id,note='')           => fetch(`${BASE}/bookmarks/${id}?note=${encodeURIComponent(note)}`,{method:'POST',headers:hdr()}).then(go),
  removeBookmark:(id)                  => fetch(`${BASE}/bookmarks/${id}`,{method:'DELETE',headers:hdr()}).then(go),
  exportPDF: async (id) => {
    const res = await fetch(`${BASE}/export/${id}`, { headers: hdr() })
    if (!res.ok) throw new Error('Export failed')
    const blob = await res.blob()
    const url  = URL.createObjectURL(blob)
    const a    = document.createElement('a')
    a.href = url; a.download = `fakeguard_report_${id}.pdf`; a.click()
    URL.revokeObjectURL(url)
  },
}
