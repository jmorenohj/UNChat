import os
import base64
from dotenv import load_dotenv
from openai import OpenAI
import gradio as gr


load_dotenv()
os.environ['OPENAI_API_KEY'] = os.getenv('OPENAI_API_KEY')

system_message = 'Responde de forma grosera todo lo que te digan. Siempre que puedas búrlate de Juan Eduardo a pesar de que no lo conozcas.'

client = OpenAI()

def chat(message, history):
    print(f'User message received: ',message)
    messages = [{"role":"system","content":system_message}]
    for user_message, assistant_message in history:
        messages.append({"role":"user","content": user_message})
        messages.append({"role":"assistant","content": assistant_message})
    messages.append({"role":"user","content":message})
    
    stream = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        stream = True
    )
    response = ""
    for chunk in stream:
        response +=chunk.choices[0].delta.content or ''
        yield response


gr.ChatInterface(fn=chat).launch(share=True)

