import os
from datetime import datetime, timedelta

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

# 👇 依然使用 SQL 数据库组件
from langchain_community.chat_message_histories import SQLChatMessageHistory
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory

# === LangChain 核心组件 ===
from langchain_openai import ChatOpenAI

# 在 import 部分加入这行

# 加载环境变量
load_dotenv()

app = FastAPI()

# 配置跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def gei_beijing_time():
    """获取当前北京时间"""
    utc_now = datetime.utcnow()
    beijing_now = utc_now + timedelta(hours=8)
    return beijing_now.strftime("%Y-%m-%d %H:%M:%S")


current_time = gei_beijing_time()

# === 1. 初始化模型 (阿里云) ===
model = ChatOpenAI(
    model="qwen-turbo",  # 这是一个较稳的模型，如果报错可尝试 qwen-plus
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    # 这里的 `or ""` 是为了防止获取不到 Key 变成 None，转成空字符串更安全
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    streaming=True,
    temperature=0.7,
)

# === 2. 定义 Prompt ===
prompt_template = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            f"当前北京时间是：{current_time}"
            "你是一个全栈技术专家，擅长用通俗易懂的语言解释技术问题。",
        ),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{user_input}"),
    ]
)

# === 3. 创建链 ===
chain = prompt_template | model | StrOutputParser()


# === 4. 关键修改：同步数据库连接 ===
# === 原来的代码 ===
# return SQLChatMessageHistory(
#     session_id=session_id,
#     connection_string="sqlite:///memory.db"
# )


# === ✨ 修改后的代码 (适配云数据库) ===
def get_session_history(session_id: str):
    # 1. 优先从环境变量读取云数据库地址
    # 2. 如果没读到（在本地测试时），还是用本地 SQLite
    db_url = os.getenv("DATABASE_URL", "sqlite:///memory.db")

    # ⚠️ 注意：Neon 的地址通常是 postgresql://...
    # 如果你的地址是 postgres:// 开头，SQLAlchemy 需要改成 postgresql://
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    return SQLChatMessageHistory(session_id=session_id, connection_string=db_url)


chain_with_history = RunnableWithMessageHistory(
    chain,
    get_session_history,
    input_messages_key="user_input",
    history_messages_key="history",
)


# === 5. 关键修改：生成器改为同步函数 ===
# 去掉了 async，使用普通的 def。FastAPI 会自动在后台线程运行它，不会卡住服务器。
def generate_stream(messages, session_id):
    last_user_message = messages[-1]["content"]

    # 使用 .stream() 而不是 .astream()
    try:
        for chunk in chain_with_history.stream(
            {"user_input": last_user_message},
            config={"configurable": {"session_id": session_id}},
        ):
            yield chunk
    except Exception as e:
        print(f"生成回复时出错: {e}")
        yield f"系统繁忙，请稍后再试。(错误: {str(e)})"


@app.post("/chat")
async def chat(request: Request):
    data = await request.json()
    messages = data.get("messages", [])
    session_id = data.get("sessionId", "default_user")

    return StreamingResponse(
        # 调用上面的同步生成器
        generate_stream(messages, session_id),
        media_type="text/event-stream",
    )


# === 6. 获取历史记录接口 ===
@app.get("/history/{session_id}")
def get_history(session_id: str):
    # 直接读取数据库
    try:
        history_db = get_session_history(session_id)
        return {"messages": history_db.messages}
    except Exception as e:
        print(f"获取历史出错: {e}")
        return {"messages": []}


if __name__ == "__main__":
    import uvicorn

    # 删除旧的数据库文件，避免格式冲突（可选，但推荐）
    if os.path.exists("memory.db"):
        try:
            os.remove("memory.db")
            print("已清理旧的数据库文件")
        except:
            pass

    print("🚀 服务正在启动 (同步数据库模式)...")
    uvicorn.run(app, host="127.0.0.1", port=8000)
