<script setup>
import { nextTick, onMounted, ref, watch } from 'vue'
import { chat, chatStream, createSession, fetchCustomerAccounts } from './api.js'

// ============================================================
// 演示客户号：数据生成后，将 finance 库 customer 表中的客户号填入此处
// （可用脚本：SELECT customer_no FROM customer WHERE customer_status='active' LIMIT 5;）
// ============================================================
const DEMO_CUSTOMERS = ['CUS00000146', 'CUS00000076', 'CUS00000206']

const customer = ref(localStorage.getItem('finance_cs_customer') || DEMO_CUSTOMERS[0])
const messages = ref([])
const input = ref('')
const busy = ref(false)
const useStream = ref(true)
const accounts = ref([])
const messagesEl = ref(null)

const OBJECT_LABELS = {
  account: '账户', bank_card: '银行卡', transaction: '交易',
  loan_product: '贷款产品', wealth_product: '理财产品',
  loan_application: '贷款申请', ticket: '工单',
}

const QUICK_ACTIONS = ['查一下账户余额', '查一下昨天的交易', '有什么贷款产品', '推荐稳健的理财产品', '我要申请消费贷款', '我的信用卡丢了', '转账一直没有到账', '转人工']

// ---------------- 会话 ----------------

async function initSession() {
  localStorage.setItem('finance_cs_customer', customer.value)
  messages.value = []
  accounts.value = []
  try {
    const session = await createSession(customer.value, true)
    for (const msg of session.messages || []) {
      messages.value.push({ role: 'bot', text: msg.text, object: msg.object })
    }
  } catch (e) {
    messages.value.push({ role: 'bot', text: '会话初始化失败，请确认客服后端已启动。' })
  }
  loadAccounts()
}

async function loadAccounts() {
  try {
    const data = await fetchCustomerAccounts(customer.value)
    accounts.value = (data && data.list) || []
  } catch (e) {
    accounts.value = []
  }
}

// ---------------- 发送消息 ----------------

async function sendText() {
  const text = input.value.trim()
  if (!text || busy.value) return
  input.value = ''
  await sendPayload({ sender_id: customer.value, text })
}

async function sendObject(obj) {
  if (busy.value) return
  await sendPayload({ sender_id: customer.value, object: obj })
}

async function sendPayload(payload) {
  messages.value.push({
    role: 'user',
    text: payload.text || '',
    object: payload.object || null,
  })
  busy.value = true
  try {
    if (useStream.value) {
      await runStream(payload)
    } else {
      const result = await chat(payload)
      for (const msg of result.messages || []) {
        messages.value.push({ role: 'bot', text: msg.text, object: msg.object })
      }
    }
  } catch (e) {
    messages.value.push({ role: 'bot', text: '服务暂时不可用，请稍后再试。' })
  } finally {
    busy.value = false
  }
}

async function runStream(payload) {
  let current = null
  await chatStream(payload, (event, data) => {
    if (event === 'message_start') {
      current = { role: 'bot', text: '', object: null, streaming: true }
      messages.value.push(current)
    } else if (event === 'delta' && current) {
      current.text += data.text || ''
    } else if (event === 'message_end') {
      if (!current) {
        current = { role: 'bot', text: '', object: null }
        messages.value.push(current)
      }
      if (data.text) current.text = data.text
      current.object = data.object || null
      current.streaming = false
      current = null
    } else if (event === 'error') {
      messages.value.push({ role: 'bot', text: data.message || '处理出现异常，请重试。' })
    }
  })
  if (current) current.streaming = false
}

// ---------------- 交互细节 ----------------

function onEnter(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendText()
  }
}

function onQuick(text) {
  input.value = text
  sendText()
}

function accountToObject(acc) {
  const accountNo = acc.account_no || acc.id
  return {
    id: String(accountNo),
    type: 'account',
    title: `账户 ${String(accountNo).slice(-4)}`,
    attributes: {
      account_no: String(accountNo),
      account_status: acc.account_status || '',
      balance_amount: acc.balance_amount || '',
      available_amount: acc.available_amount || '',
    },
  }
}

function displayAttrs(object) {
  const attrs = object.attributes || {}
  return Object.entries(attrs).slice(0, 6)
}

watch(messages, async () => {
  await nextTick()
  if (messagesEl.value) messagesEl.value.scrollTop = messagesEl.value.scrollHeight
}, { deep: true })

onMounted(() => { initSession() })
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <div class="brand">
        <div class="brand-mark">融</div>
        <div>
          <div class="brand-name">金融智能客服</div>
          <div class="brand-sub">FINANCE CONCIERGE</div>
        </div>
      </div>
      <div class="header-spacer"></div>
      <div class="header-tools">
        <label class="switch">
          <input type="checkbox" v-model="useStream" />
          流式响应
        </label>
        <input class="customer-select" v-model="customer" list="demo-customers" placeholder="客户号"
               style="width: 170px" @change="initSession()" />
        <datalist id="demo-customers">
          <option v-for="c in DEMO_CUSTOMERS" :key="c" :value="c"></option>
        </datalist>
        <button class="btn-ghost" @click="initSession()">新会话</button>
      </div>
    </header>

    <div class="app-body">
      <aside class="side-panel">
        <div class="side-section">
          <div class="side-title">我的账户</div>
          <div v-if="!accounts.length" class="side-empty">暂无账户数据</div>
          <div v-for="acc in accounts" :key="acc.id || acc.account_no" class="account-card"
               @click="sendObject(accountToObject(acc))">
            <div class="ac-top">
              <span>{{ acc.account_no }}</span>
              <span>{{ acc.account_status === 'active' ? '正常' : acc.account_status }}</span>
            </div>
            <div class="ac-balance">¥ {{ acc.balance_amount }}</div>
            <div class="ac-sub">可用 {{ acc.available_amount }} · 冻结 {{ acc.frozen_amount }}</div>
          </div>
        </div>
        <div class="side-section">
          <div class="side-title">快捷服务</div>
          <div class="quick-chips">
            <button v-for="q in QUICK_ACTIONS" :key="q" class="chip" @click="onQuick(q)">{{ q }}</button>
          </div>
        </div>
      </aside>

      <main class="chat-panel">
        <div class="messages" ref="messagesEl">
          <div v-for="(m, i) in messages" :key="i" class="msg-row" :class="m.role">
            <div class="avatar" :class="m.role">{{ m.role === 'bot' ? '融' : '客' }}</div>
            <div>
              <div class="bubble" v-if="m.text || m.streaming">
                <template v-if="m.text">{{ m.text }}</template>
                <template v-else>
                  <span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span>
                </template>
              </div>
              <div class="object-card" v-if="m.object">
                <div class="oc-title">
                  {{ OBJECT_LABELS[m.object.type] || '业务对象' }} · {{ m.object.title }}
                </div>
                <div class="oc-grid">
                  <template v-for="[k, v] in displayAttrs(m.object)" :key="k">
                    <span class="oc-key">{{ k }}</span>
                    <span class="oc-val">{{ v }}</span>
                  </template>
                </div>
                <button v-if="m.role === 'bot'" class="oc-action" @click="sendObject(m.object)">
                  选择此{{ OBJECT_LABELS[m.object.type] || '对象' }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <div class="composer">
          <div class="composer-inner">
            <textarea v-model="input" rows="1" placeholder="请输入您的问题，例如：帮我查一下账户余额"
                      @keydown="onEnter"></textarea>
            <button class="btn-send" :disabled="busy || !input.trim()" @click="sendText">发送</button>
          </div>
        </div>
        <div class="footer-note">本服务内容由智能助手生成，不构成投资建议；理财有风险，投资须谨慎。</div>
      </main>
    </div>
  </div>
</template>
