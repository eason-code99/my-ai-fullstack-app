import os
from datetime import datetime, timedelta

import dashscope
from dashscope import ImageSynthesis
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware  # 👈 必须要有这个！
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

load_dotenv()

# === 🚩 启动标记：必须在日志里看到 V2.2 才是对的！ ===
print("🚀 Server is starting... Version: CORS_FIXED_V2.2")

app = FastAPI()

# === 🔥 核心修复：允许跨域 (CORS) 🔥 ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有前端访问
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === 1. 定义模型 ===
# 防止 Key 为空导致的启动报错
api_key_val = os.getenv("DASHSCOPE_API_KEY") or "sk-placeholder"

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
        if not current_key or current_key.startswith("sk-placeholder"):
            return "❌ 错误: API Key 未设置或无效"

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


# === 5. 核心接口 ===
@app.post("/chat")
async def chat(request: ChatRequest):
    try:
        user_input = request.message
        session_id = request.session_id
        print(f"📥 收到消息: {user_input}")

        try:
            intent = await router_chain.ainvoke({"user_input": user_input})
            intent = intent.strip().upper()
        except:
            intent = "TEXT"

        if "IMAGE" in intent:
            url = generate_image_from_text(user_input)
            if url.startswith("❌"):
                return {"response": f"画图失败: {url}"}
            return {"response": f"IMAGE_URL:{url}"}
        else:
            response = await with_message_history.ainvoke(
                {"user_input": user_input},
                config={"configurable": {"session_id": session_id}},
            )
            return {"response": response}

    except Exception as e:
        print(f"💥 错误: {e}")
        return {"response": f"❌ 服务器内部错误: {str(e)}"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


# version: CORS_FIXED_V2.22222222222222
