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

# 加载环境变量
load_dotenv()

# === 打印启动日志（作为更新成功的证据） ===
print("🚀 Server is starting... Version: ROUTER_V2.0_FIXED")

app = FastAPI()

# === 1. 定义模型 ===
# 我们复用同一个模型配置
llm = ChatOpenAI(
    model="qwen-turbo",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    api_key=os.getenv("DASHSCOPE_API_KEY") or "sk-placeholder",  # 防止None报错
    temperature=0.1,
)

# === 2. 🧠 定义“意图识别经理” (Router) ===
router_template = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """你是一个意图识别专家。请判断用户的输入意图。
    - 如果用户明确想要生成图片、画画、照片、绘图，请只回复: IMAGE
    - 如果用户只是在聊天、提问、或者用比喻（比如'画大饼'），请只回复: TEXT
    不要回复任何其他废话，只回单词。""",
        ),
        ("human", "{user_input}"),
    ]
)

router_chain = router_template | llm | StrOutputParser()


# === 3. 定义“作家” (聊天逻辑) ===
def get_beijing_time():
    utc_now = datetime.utcnow()
    beijing_now = utc_now + timedelta(hours=8)
    return beijing_now.strftime("%Y-%m-%d %H:%M:%S")


chat_template = ChatPromptTemplate.from_messages(
    [
        ("system", f"你是一个全栈AI助手。当前北京时间是：{get_beijing_time()}。"),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{user_input}"),
    ]
)

chat_model_creative = ChatOpenAI(
    model="qwen-turbo",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    api_key=os.getenv("DASHSCOPE_API_KEY") or "sk-placeholder",
    temperature=0.7,
)

chat_chain = chat_template | chat_model_creative | StrOutputParser()

# 内存记忆
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


# === 4. 定义“画家” (通义万相) ===
def generate_image_from_text(prompt):
    try:
        # 强制获取 Key，防止环境变量丢失
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            return "❌ 错误：未找到 DASHSCOPE_API_KEY"

        dashscope.api_key = api_key
        print(f"🎨 画家正在工作: {prompt}")

        rsp = ImageSynthesis.call(
            model=ImageSynthesis.Models.wanx_v1, prompt=prompt, n=1, size="1024*1024"
        )
        if rsp.status_code == 200:
            return rsp.output.results[0].url
        else:
            return f"画图失败: {rsp.code}, {rsp.message}"
    except Exception as e:
        return f"画图出错: {str(e)}"


# === 5. 请求数据模型 ===
class ChatRequest(BaseModel):
    message: str  # 前端只发这个字段
    session_id: str = "default_user"


# === 6. 核心接口 (无 generate_stream，只有 chat) ===
@app.post("/chat")
async def chat(request: ChatRequest):
    user_input = request.message
    session_id = request.session_id

    print(f"📥 收到请求: {user_input}")  # 打印日志

    # 🕵️‍♂️ 第一步：让经理判断意图
    intent = "TEXT"  # 默认值
    try:
        intent = await router_chain.ainvoke({"user_input": user_input})
        intent = intent.strip().upper()
        print(f"✅ 意图识别: {intent}")
    except Exception as e:
        print(f"⚠️ 路由判断出错，转为聊天模式: {e}")

    # 🚦 第二步：根据意图分流
    if "IMAGE" in intent:
        image_url = generate_image_from_text(user_input)
        return {"response": f"IMAGE_URL:{image_url}"}
    else:
        response = await with_message_history.ainvoke(
            {"user_input": user_input},
            config={"configurable": {"session_id": session_id}},
        )
        return {"response": response}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
