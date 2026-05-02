# import os
# from openai import OpenAI
#
# client = OpenAI(
#     api_key="sk-eb1bd9283635456b9f9956dd05c9f40d",
#     base_url="https://api.xiaomimimo.com/v1"
# )
#
# completion = client.chat.completions.create(
#     model="mimo-v2.5-pro",
#     messages=[
#         {
#             "role": "system",
#             "content": "You are MiMo, an AI assistant developed by Xiaomi. Today is date: Tuesday, December 16, 2025. Your knowledge cutoff date is December 2024."
#         },
#         {
#             "role": "user",
#             "content": "please introduce yourself"
#         }
#     ],
#     max_completion_tokens=1024,
#     temperature=1.0,
#     top_p=0.95,
#     stream=False,
#     stop=None,
#     frequency_penalty=0,
#     presence_penalty=0,
#     extra_body={
#         "thinking": {"type": "disabled"}
#     }
# )
#
# print(completion.model_dump_json())


import os
from openai import OpenAI

client = OpenAI(
    # 若没有配置环境变量，请用阿里云百炼API Key将下行替换为：api_key="sk-xxx",
    # 各地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
    api_key="sk-eb1bd9283635456b9f9956dd05c9f40d",
    # 各地域配置不同，请根据实际地域修改
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

completion = client.chat.completions.create(
    model="qwen3.6-plus", # 此处以qwen3.6-plus为例，可按需更换模型名称。模型列表：https://help.aliyun.com/zh/model-studio/models
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20241022/emyrja/dog_and_girl.jpeg"
                    },
                },
                {"type": "text", "text": "图中描绘的是什么景象?"},
            ],
        },
    ],
)
print(completion.choices[0].message.content)