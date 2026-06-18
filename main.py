# -*- coding: utf-8 -*-
"""
大模型问答网站 —— 后端入口
=================================

功能说明：
1. 用 Flask 作为 Web 服务器，同时托管 static/ 目录下的前端页面
2. 通过 /api/chat 接口与前端交互，请求大模型并返回回复
3. 支持「多轮对话」（保留 history 历史消息），也支持「清空对话」
4. 通过 config.json 读取 API Key / 模型名 / 接口地址，方便切换不同厂商

运行方式：
- PyCharm：直接运行本文件 main 函数
- 命令行： python main.py
- 浏览器：访问 http://127.0.0.1:5000  （或直接双击 static/index.html 也行）

如果你要改后端逻辑 / 加功能，直接在本文件里改就行。
"""

import json
import os
from openai import OpenAI
from flask import Flask, request, jsonify, send_from_directory


# --------------------------- 路径与配置 ---------------------------
# 取当前文件所在目录作为项目根目录，这样无论从哪里启动都能找到 static/ 和 config.json
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
STATIC_DIR = os.path.join(BASE_DIR, "static")


def load_config():
    """读取 config.json。
    如果文件不存在，会返回一份默认配置，并提示用户去填 API Key。
    """
    default_config = {
        # 阿里云百炼（DashScope）的 OpenAI 兼容接口地址
        "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key": "sk-6ecd6d21f0954a90b7db922a2b9c2894",
        # 常用模型：qwen-turbo / qwen-plus / qwen-max
        "model": "qwen-plus",
        "timeout": 60,
        "system_prompt": "你是一个乐于助人、回答简洁清晰的智能助手。"
    }

    # 如果配置文件不存在，就写一份默认的，方便用户直接改
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(default_config, f, ensure_ascii=False, indent=2)
        return default_config

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        user_config = json.load(f)# 变成字典格式？

    # 用用户配置覆盖默认配置（缺省字段用默认值补齐）
    for k, v in default_config.items():
        user_config.setdefault(k, v)
    return user_config


# --------------------------- Flask App 初始化 ---------------------------
app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="")


@app.after_request
def add_cors_headers(resp):
    """给所有响应加上跨域头，这样直接双击 static/index.html 也能调用后端。"""
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return resp


@app.route("/", methods=["GET"])
def index():
    """根路径直接返回 index.html，访问 http://127.0.0.1:5000 就能看到页面。"""
    return send_from_directory(STATIC_DIR, "index.html")


# --------------------------- 与大模型通信的核心函数 ---------------------------
def call_llm(config, messages):
    """调用大模型，返回模型回复字符串。

    使用 OpenAI SDK 的兼容模式（通过 base_url 指向阿里云百炼），
    这样切换到其他 OpenAI 兼容厂商（DeepSeek / 智谱 / 本地 Ollama 等）
    只要改 config.json 里的 api_base / api_key / model 就行。

    参数：
        config   : 从 config.json 读出来的配置字典
        messages : OpenAI 格式的消息列表，形如：
                   [
                       {"role": "system", "content": "你是一个助手"},
                       {"role": "user", "content": "你好"},
                       {"role": "assistant", "content": "你好！"}
                   ]

    返回值：模型回复的纯文本字符串。如果失败，返回带错误信息的字符串。
    """
    # 构造 OpenAI 客户端，base_url 指向百炼兼容接口
    client = OpenAI(
        api_key=config["api_key"],
        base_url=config["api_base"],
    )

    # 调用 chat.completions.create，这是 OpenAI SDK 的标准用法
    # 百炼的 qwen-turbo / qwen-plus / qwen-max 都兼容这个接口
    completion = client.chat.completions.create(
        model=config["model"],
        messages=messages,
        temperature=0.7,
        timeout=config.get("timeout", 60),
    )

    # 解析标准返回结构，取出模型的回复文本
    reply = completion.choices[0].message.content
    return reply


# --------------------------- API 路由 ---------------------------
@app.route("/api/chat", methods=["POST"])
def api_chat():
    """前端发来的聊天请求。

    请求体（JSON）格式：
    {
        "message": "用户说的话",
        "history": [
            {"role": "user", "content": "..."},
            {"role": "assistant", "content": "..."}
        ]
    }

    返回（JSON）：
    {
        "ok": true,
        "reply": "模型的回复",
        "history": [ 更新后的完整消息历史，方便前端保存 ]
    }
    """
    body = request.get_json(force=True, silent=True) or {}
    user_message = (body.get("message") or "").strip()
    history = body.get("history") or []

    # 基本校验：空消息直接报错返回
    if not user_message:
        return jsonify({"ok": False, "reply": "请输入内容再发送哦~", "history": history}), 400

    config = load_config()

    # 组装最终发送给模型的消息列表：系统提示 + 历史 + 当前问题
    messages = [{"role": "system", "content": config.get("system_prompt", "")}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    # 调用模型；如果出错，把错误信息返回给前端，前端会弹窗显示
    try:
        reply = call_llm(config, messages)
    except Exception as e:
        # OpenAI SDK 会抛出各种具体异常（APIError / APIConnectionError /
        # AuthenticationError / Timeout 等），这里统一捕获并把消息返回给前端
        reply = "调用大模型失败：{}（{}）".format(type(e).__name__, e)

    # 更新历史记录，返回给前端
    new_history = list(history) + [
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": reply},
    ]

    return jsonify({"ok": True, "reply": reply, "history": new_history})


# --------------------------- 程序入口 ---------------------------
if __name__ == "__main__":
    # 启动 Flask 开发服务器；host=0.0.0.0 让同局域网的其他设备也能访问
    print("=" * 60)
    print("  大模型问答后端启动中...")
    print("  访问方式 1：浏览器打开  http://127.0.0.1:3000")
    print("  访问方式 2：直接双击文件  static/index.html")
    print("  配置文件  ：{}".format(CONFIG_PATH))
    print("=" * 30)
    app.run(host="0.0.0.0", port=3000, debug=True)
