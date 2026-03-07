import os
from openai import OpenAI
import json
from retry import retry

client = OpenAI(
    api_key=os.environ["API_KEY"],
    base_url=os.environ["BASE_URL"]
)

@retry(tries=5, delay=5, backoff=2, jitter=(1, 3))
def get_llm_response(messages, is_string=False, model="gpt-4o"):
    response = client.chat.completions.create(
        model=model,
        messages=messages
    )
    if not hasattr(response, "error"):
        ans = response.choices[0].message.content
        if is_string:
            return ans
        else:
            cleaned_text = ans.strip("`json\n").strip("`\n").strip("```\n")
            ans = json.loads(cleaned_text)
            return ans
    else:
        raise Exception(response.error.message)