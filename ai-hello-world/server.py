import os
from datetime import datetime, timedelta

import dashscope
from dashscope import ImageSynthesis
from dotenv import load_dotenv
from fastapi import FastAPI
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

load_dotenv()

# === 启动标记 V2.1 ===
print("🚀 Server is starting... Version: ERROR_CATCHER_V2.1")

app = FastAPI()

# === 1. 定义模型 ===
# 强制检查 Key，如果没有 Key，给一个占位符防止启动报错，但在调用时会报错
api_key_val = os.getenv("DASHSCOPE_API_KEY") or "sk-missing-key"

llm = ChatOpenAI(
    model="qwen-turbo",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    api_key=api_key_val,
    temperature=0.1,
)

chat_model_creative = ChatOpenAI(
    model="qwen-turbo",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    api_key=api_key_val,
    temperature=0.7,
)

# === 2. 意图识别 ===
router_template = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "你是一个意图识别专家。如果用户想画画/生成图片，回复IMAGE。如果只是聊天，回复TEXT。只回复单词。",
        ),
        ("human", "{user_input}"),
    ]
)
router_chain = router_template | llm | StrOutputParser()


# === 3. 聊天逻辑 ===
def get_beijing_time():
    utc_now = datetime.utcnow()
    beijing_now = utc_now + timedelta(hours=8)
    return beijing_now.strftime("%Y-%m-%d %H:%M:%S")


chat_template = ChatPromptTemplate.from_messages(
    [
        ("system", f"你是一个全栈AI助手。当前北京时间：{get_beijing_time()}"),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{user_input}"),
    ]
)
chat_chain = chat_template | chat_model_creative | StrOutputParser()

store = {}


def get_session_history(session_id: str):
    if session_id not in store:
        store[session_id] = ChatMessageHistory()
    return store[session_id]


with_message_history = RunnableWithMessageHistory(
    chat_chain,
    get_session_history,
    input_messages_key="user_input",
    history_messages_key="history",
)


# === 4. 画图函数 ===
def generate_image_from_text(prompt):
    try:
        current_key = os.getenv("DASHSCOPE_API_KEY")
        if not current_key:
            return "❌ 错误: 环境变量 DASHSCOPE_API_KEY 未设置"
        dashscope.api_key = current_key

        rsp = ImageSynthesis.call(
            model=ImageSynthesis.Models.wanx_v1, prompt=prompt, n=1, size="1024*1024"
        )
        if rsp.status_code == 200:
            return rsp.output.results[0].url
        else:
            return f"❌ 画图API报错: {rsp.code} - {rsp.message}"
    except Exception as e:
        return f"❌ 画图代码崩溃: {str(e)}"


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default_user"


# === 5. 核心接口 (带防弹护盾) ===
@app.post("/chat")
async def chat(request: ChatRequest):
    # 🔥 全局异常捕获：无论发生什么，都把错误发回给前端显示 🔥
    try:
        user_input = request.message
        session_id = request.session_id
        print(f"📥 收到消息: {user_input}")

        # 1. 意图识别
        try:
            intent = await router_chain.ainvoke({"user_input": user_input})
            intent = intent.strip().upper()
            print(f"🧠 意图: {intent}")
        except Exception as e:
            print(f"⚠️ 意图识别失败: {e}")
            # 如果识别失败，很有可能是 Key 错了，这里记录一下，默认转聊天
            intent = "TEXT"

        # 2. 执行逻辑
        if "IMAGE" in intent:
            url = generate_image_from_text(user_input)
            # 如果 url 开头是❌，说明画图函数内部报错了，直接把错误显示出来
            if url.startswith("❌"):
                return {"response": f"画图失败了: {url}"}
            return {"response": f"IMAGE_URL:{url}"}
        else:
            # 聊天模式
            response = await with_message_history.ainvoke(
                {"user_input": user_input},
                config={"configurable": {"session_id": session_id}},
            )
            return {"response": response}

    except Exception as e:
        # 🚨 捕捉所有漏网之鱼 🚨
        error_msg = str(e)
        print(f"💥 严重崩溃: {error_msg}")
        # 如果是 401，提示用户 Key 有问题
        if "401" in error_msg:
            return {
                "response": "❌ 权限错误 (401): 请检查 Railway 里的 API Key 是否正确，或者阿里云是否欠费/未开通。"
            }
        return {"response": f"❌ 系统内部报错: {error_msg}"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
