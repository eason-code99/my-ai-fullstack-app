import os

from dotenv import load_dotenv
from openai import OpenAI

# 1. 加载环境变量 (读取 .env 文件)
load_dotenv()

# 2. 初始化客户端 (重点检查这里！)
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    # ↓↓↓ 这一行非常重要！没有它，代码就会默认去连美国的 OpenAI
    base_url=os.getenv("OPENAI_BASE_URL"),
)
print(f"正在连接服务器: {client.base_url}")


# 【修改点 1】入参从 user_input 变成了 messages (列表)
def get_ai_response(messages):
    try:
        response = client.chat.completions.create(
            model="qwen-plus",
            # 【修改点 2】直接把整个聊天记录传给 AI
            messages=messages,
            temperature=0.7,
            # 【修改点 3】从 500 改成 2000，防止回答被截断
            max_tokens=2000,
            # 【关键修改】开启流式输出
            stream=True,
        )
        # 这里不再返回 content 字符串，而是返回整个流对象
        return response

    except Exception as e:
        print(f"调用 AI 接口出错: {e}")
        return None


# --- 简单测试代码 ---
# if __name__ == "__main__":
#     print("--------------------------------------------------")
#     print("🎉 AI 助手已启动！(输入 'exit' 或 '退出' 结束对话)")
#     print("--------------------------------------------------")

#     while True:
#         # 1. 获取你在键盘上的输入
#         user_input = input("\n你: ")

#         # 2. 如果输入 exit 就退出程序
#         if user_input.strip().lower() in ["exit", "quit", "退出"]:
#             print("再见！")
#             break

#         # 3. 如果输入为空，跳过
#         if not user_input.strip():
#             continue

#         print("AI 正在思考...", end="", flush=True)

#         # 4. 调用你的函数
#         answer = get_ai_response(user_input)

#         # 5. 打印回答
#         print(f"\rAI: {answer}")  # \r 是为了把“正在思考”覆盖掉
