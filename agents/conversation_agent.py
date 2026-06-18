import os
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
load_dotenv()

class ConversationAgent:
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-5.4-mini-2026-03-17",
            temperature=0.5,
            api_key=os.getenv("OPENAI_API_KEY"),
        )

    def chat(self, message: str) -> str:
        response = self.llm.invoke(message)
        return response.content