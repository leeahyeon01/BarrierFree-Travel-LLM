import os
import json
from openai import OpenAI
from .tools import tools_schema, available_functions
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def load_system_prompt():
    prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", "system_prompt.txt")
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()

def run_agent(user_message: str, max_loops: int = 5):
    """ReAct 기반 OpenAI Tool Calling 에이전트 실행 루프"""
    messages = [
        {"role": "system", "content": load_system_prompt()},
        {"role": "user", "content": user_message}
    ]
    
    loop_count = 0
    while loop_count < max_loops:
        loop_count += 1
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=tools_schema,
            tool_choice="auto"
        )
        
        response_message = response.choices[0].message
        messages.append(response_message)
        
        # 도구(Tool)를 호출하라는 응답이 있는 경우
        if response_message.tool_calls:
            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                
                # 정의되지 않은 도구 호출 방어 로직
                if function_name not in available_functions:
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": json.dumps({"error": "Unknown function"})
                    })
                    continue

                function_to_call = available_functions[function_name]
                try:
                    function_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    function_args = {}
                
                print(f"[Agent Loop {loop_count}] Calling '{function_name}' with args: {function_args}")
                
                # 도구 실행
                function_response = function_to_call(**function_args)
                
                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": function_name,
                    "content": function_response,
                })
        else:
            # 최종 텍스트 답변이 완성된 경우 루프 종료
            return response_message.content
            
    return "에이전트가 지정된 최대 반복 횟수를 초과했습니다. 최종 코스를 생성하지 못했습니다."
