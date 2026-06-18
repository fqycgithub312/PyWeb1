// ============================================================
// 大模型问答助手 —— 前端逻辑
// 职责：
//   1. 监听用户输入、发送请求给后端 /api/chat
//   2. 把历史消息（history）存在 localStorage，刷新页面后保留
//   3. 渲染聊天气泡、"正在思考" 状态、错误提示
// ============================================================

// 后端接口前缀，在 index.html 里根据打开方式动态决定
const API_BASE = window.__API_BASE__ || "/api";

// localStorage 的 key，用来保存对话历史
const STORAGE_KEY = "chat_history_v1";

// 获取 DOM 元素
const chatBox = document.getElementById("chat-box");
const input = document.getElementById("input");
const btnSend = document.getElementById("btn-send");
const btnClear = document.getElementById("btn-clear");
const statusEl = document.getElementById("status");

// 读取本地保存的历史消息（格式：[{role, content}, ...]）
let history = loadHistory();

// 页面初始化：先把历史渲染出来
renderAll();
if (history.length === 0) {
    appendBubble("assistant", "你好呀！有什么问题尽管问我 😊");
}

// -------------- 事件绑定 --------------

// 点击"发送"按钮
btnSend.addEventListener("click", onSend);

// 点击"清空对话"按钮
btnClear.addEventListener("click", () => {
    if (!confirm("确定清空当前对话吗？")) return;
    history = [];
    saveHistory(history);
    chatBox.innerHTML = "";
    appendBubble("assistant", "对话已清空，我们重新开始吧~");
});

// 在输入框里按 Enter 发送；Shift+Enter 换行
input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        onSend();
    }
});

// 输入时根据内容自动调整 textarea 的高度
input.addEventListener("input", autoResize);
autoResize();

// -------------- 核心函数 --------------

/** 处理发送消息 */
async function onSend() {
    const text = input.value.trim();
    if (!text) return;

    // 先把用户消息显示出来，并清空输入框
    appendBubble("user", text);
    input.value = "";
    autoResize();

    // 禁用按钮，显示"思考中"
    setSending(true);
    showStatus("正在思考中...");

    try {
        // 向后端发起请求
        const resp = await fetch(API_BASE + "/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: text, history: history }),
        });

        const data = await resp.json();

        // 把回复显示出来，并更新 history
        appendBubble("assistant", data.reply || "(模型没有返回内容)");
        history = data.history || [];
        saveHistory(history);

        if (data.ok) {
            showStatus("");
        } else {
            showStatus("模型返回了一个提示：" + (data.reply || ""), true);
        }
    } catch (err) {
        // 请求出错：多半是后端没启动 / 跨域
        appendBubble(
            "assistant",
            "❌ 请求失败：" +
                (err && err.message ? err.message : err) +
                "\n\n请确认：\n1) 已用 Python 运行 main.py 启动后端\n2) config.json 里已经填好 API Key"
        );
        showStatus("网络错误，请检查后端是否已启动", true);
    } finally {
        setSending(false);
    }
}

/** 向聊天框追加一条气泡消息 */
function appendBubble(role, content) {
    const msg = document.createElement("div");
    msg.className = "msg " + role;

    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = role === "user" ? "🧑" : "🤖";

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = content;

    msg.appendChild(avatar);
    msg.appendChild(bubble);
    chatBox.appendChild(msg);

    // 自动滚到底部
    chatBox.scrollTop = chatBox.scrollHeight;
}

/** 把本地保存的历史消息一次性渲染出来 */
function renderAll() {
    chatBox.innerHTML = "";
    for (const item of history) {
        appendBubble(item.role, item.content);
    }
}

/** 设置底部状态提示文字（可标记为红色错误样式） */
function showStatus(text, isError) {
    statusEl.textContent = text || "";
    statusEl.classList.toggle("error", !!isError);
}

/** 在等待回复时禁用发送按钮，防止重复点击 */
function setSending(sending) {
    btnSend.disabled = sending;
    btnSend.textContent = sending ? "发送中..." : "发送";
}

/** 根据输入内容自动调整 textarea 高度 */
function autoResize() {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 160) + "px";
}

// -------------- localStorage 读写 --------------

function loadHistory() {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) return [];
        const list = JSON.parse(raw);
        return Array.isArray(list) ? list : [];
    } catch (e) {
        return [];
    }
}

function saveHistory(list) {
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
    } catch (e) {
        // 写不进去就算了（比如隐私模式下）
    }
}
