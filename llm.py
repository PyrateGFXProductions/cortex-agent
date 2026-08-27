import json
import os

from openai import OpenAI

from tools import TOOLS, TOOL_SCHEMAS

client = OpenAI(
    base_url=os.environ["BASE_URL"],
    api_key=os.environ["API_KEY"],
)

user_input = input("Enter your prompt> ")

SYSTEM_PROMPT = f"""
You are a coding agent. Your job is to code. Always code.
Use the bash tool to inspect files.
Answer back to the user once exploration is done.

Your current working directory is: {os.getcwd()}
"""

response = client.chat.completions.create(
    model="deepseek/deepseek-v4-flash",
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_input}
    ],
    tools=TOOL_SCHEMAS,
)

message = response.choices[0].message
output = message.content

completion_details = response.usage.completion_tokens_details
prompt_details = response.usage.prompt_tokens_details

usage = {
    "prompt_tokens": response.usage.prompt_tokens,
    "completion_tokens": response.usage.completion_tokens,
    "reasoning_tokens": getattr(completion_details, "reasoning_tokens", None),
    "cached_tokens": getattr(prompt_details, "cached_tokens", None),
}
print("\nAgent: ", output, "\n")

if message.tool_calls:
    tool_call = message.tool_calls[0]
    args = json.loads(tool_call.function.arguments)
    result = TOOLS[tool_call.function.name](**args)
    print("Tool: ", tool_call.function.name, args)
    print(result, "\n")

print(usage)
