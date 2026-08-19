from llm import LLM
from registry import TOOLS
from prompts import TOOL_SELECTION_PROMPT, FINAL_RESPONSE_PROMPT
import json

llm = LLM()

while True:
    user_query = input("\nYou : ")

    if user_query.lower() == "exit":
        break

    print(f"user_query: {user_query}")

    # =====================================================
    # First LLM Call - Decide which tool to use
    # =====================================================

    tool_messages = [
        {
            "role": "system",
            "content": TOOL_SELECTION_PROMPT
        },
        {
            "role": "user",
            "content": user_query
        }
    ]

    response = llm.chat(tool_messages)

    content = response.choices[0].message.content

    print(f"\nAgent Decision:\n{content}")

    data = json.loads(content)

    tool_name = data["tool"]

    # =====================================================
    # No Tool Required
    # =====================================================

    if tool_name == "none":

        final_messages = [
            {
                "role": "system",
                "content": FINAL_RESPONSE_PROMPT
            },
            {
                "role": "user",
                "content": user_query
            }
        ]

        response = llm.chat(final_messages)

        print("\nAssistant:")
        print(response.choices[0].message.content)

        continue

    # =====================================================
    # Execute Tool
    # =====================================================

    tool = TOOLS[tool_name]

    try:
        result = tool(**data["arguments"])
    except Exception as e:
        print(f"\nTool Error: {e}")
        continue

    print("\nTool Result:", result)

    # =====================================================
    # Second LLM Call - Generate Final Answer
    # =====================================================

    final_messages = [
        {
            "role": "system",
            "content": FINAL_RESPONSE_PROMPT
        },
        {
            "role": "user",
            "content": f"""
The user asked:

{user_query}

The selected tool was:

{tool_name}

The tool returned:

{result}

Please answer the user's original question naturally.
"""
        }
    ]

    response = llm.chat(final_messages)

    final_answer = response.choices[0].message.content

    print("\nAssistant:")
    print(final_answer)