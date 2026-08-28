// 客服后端与金融中台的接口封装

const JSON_HEADERS = { 'Content-Type': 'application/json' }

export async function chat(payload) {
  const resp = await fetch('/api/chat', { method: 'POST', headers: JSON_HEADERS, body: JSON.stringify(payload) })
  if (!resp.ok) throw new Error(`chat http ${resp.status}`)
  return resp.json()
}

export async function chatStream(payload, onEvent) {
  const resp = await fetch('/api/chat/stream', { method: 'POST', headers: JSON_HEADERS, body: JSON.stringify(payload) })
  if (!resp.ok) throw new Error(`chat/stream http ${resp.status}`)
  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    let idx
    while ((idx = buf.indexOf('\n\n')) >= 0) {
      const raw = buf.slice(0, idx)
      buf = buf.slice(idx + 2)
      let event = 'message'
      let data = ''
      for (const line of raw.split('\n')) {
        if (line.startsWith('event: ')) event = line.slice(7).trim()
        else if (line.startsWith('data: ')) data += line.slice(6)
      }
      if (data) {
        try { onEvent(event, JSON.parse(data)) } catch (e) { /* 忽略非法事件 */ }
      }
    }
  }
}

export async function createSession(senderId, triggerOnboarding = true) {
  const resp = await fetch('/api/sessions', {
    method: 'POST', headers: JSON_HEADERS,
    body: JSON.stringify({ sender_id: senderId, trigger_onboarding: triggerOnboarding }),
  })
  if (!resp.ok) throw new Error(`sessions http ${resp.status}`)
  return resp.json()
}

export async function fetchHistory(senderId) {
  const resp = await fetch(`/api/chat/history?sender_id=${encodeURIComponent(senderId)}`)
  if (!resp.ok) throw new Error(`history http ${resp.status}`)
  return resp.json()
}

export async function fetchSessionState(senderId) {
  const resp = await fetch(`/api/sessions/state?sender_id=${encodeURIComponent(senderId)}`)
  if (!resp.ok) throw new Error(`state http ${resp.status}`)
  return resp.json()
}

// 金融中台（经 Vite 代理 /finance）：读取客户账户列表用于左侧面板
export async function fetchCustomerAccounts(customerNo) {
  const resp = await fetch(`/finance/api/v1/customers/${encodeURIComponent(customerNo)}/accounts`, {
    headers: {
      Authorization: `Bearer ${customerNo}`,
      'X-Channel-Code': 'AI_CS',
      'X-Request-Id': crypto.randomUUID().replaceAll('-', ''),
    },
  })
  if (!resp.ok) return null
  const payload = await resp.json()
  return payload.code === 0 ? payload.data : null
}
