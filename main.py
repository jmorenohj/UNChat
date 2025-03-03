import os
import logging
from dotenv import load_dotenv
from openai import OpenAI
import gradio as gr
from process_docs import generate_data_store
from rag import query_rag
import shutil
import json
from test import scores

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Ruta donde se almacena la base de datos Chroma
CHROMA_PATH = os.path.join(BASE_DIR, "database")
DATA_PATH = os.path.join(BASE_DIR, "documentos")

# Configurar logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

load_dotenv()

# Asegurar que la API key de OpenAI está en el entorno
os.environ['OPENAI_API_KEY'] = os.getenv('OPENAI_API_KEY')

if not os.environ['OPENAI_API_KEY']:
    raise ValueError("No se encontró la API Key de OpenAI. Asegúrate de que el archivo .env contiene OPENAI_API_KEY.")

client = OpenAI()

def diagnose_documents_directory():
    logging.info(f"Diagnóstico del directorio de documentos: {DATA_PATH}")
    if not os.path.exists(DATA_PATH):
        logging.error(f"El directorio {DATA_PATH} no existe")
        return
        
    files = os.listdir(DATA_PATH)
    logging.info(f"Archivos en {DATA_PATH}: {files}")
    
    txt_files = [f for f in files if f.endswith('.txt')]
    logging.info(f"Archivos .txt encontrados: {txt_files}")
    
    for txt_file in txt_files:
        path = os.path.join(DATA_PATH, txt_file)
        size = os.path.getsize(path)
        logging.info(f"Archivo: {txt_file}, Tamaño: {size} bytes")
        
        # Leer primeros caracteres para diagnóstico
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read(100)
                logging.info(f"Primeros 100 caracteres: {content}")
        except Exception as e:
            logging.error(f"Error leyendo {txt_file}: {str(e)}")

# Llamar a la función
#diagnose_documents_directory()

def check_and_generate_data_store():
    """
    Verifica si la base de datos Chroma ya existe. 
    Si no existe, genera la base de datos a partir de los documentos.
    """
    try:
        if not os.path.exists(CHROMA_PATH) or not os.listdir(CHROMA_PATH):
            logging.info("No se encontró una base de datos en Chroma. Generando nueva...")
            generate_data_store()
            logging.info("Base de datos generada exitosamente.")
        else:
            logging.info("La base de datos en Chroma ya existe. No es necesario regenerarla.")
    except Exception as e:
        logging.error(f"Error al verificar o generar la base de datos: {str(e)}")

    # try:
    #     logging.info("Forzando regeneración de la base de datos...")
    #     if os.path.exists(CHROMA_PATH):
    #         shutil.rmtree(CHROMA_PATH)
    #     generate_data_store()
    #     logging.info("Base de datos regenerada exitosamente.")
    # except Exception as e:
    #     logging.error(f"Error al generar la base de datos: {str(e)}")

# Ejecutar la verificación antes de lanzar la aplicación
#check_and_generate_data_store()

try:
    from langchain_openai import OpenAIEmbeddings
    from langchain_chroma import Chroma
    embeddings = OpenAIEmbeddings()
    db = Chroma(persist_directory=CHROMA_PATH, embedding_function=embeddings)
    count = db._collection.count()
    logging.info(f"La base de datos Chroma contiene {count} documentos")
except Exception as e:
    logging.error(f"Error al verificar la base de datos: {str(e)}")

scores()

# Definir función para Gradio que usa RAG
def chat(message, history):
    """
    Recibe una consulta del usuario y usa el sistema RAG para responder.
    Mantiene y muestra el historial de la conversación en Gradio con streaming.
    
    Args:
        message (str): Mensaje del usuario.
        history (list[tuple]): Lista de (mensaje del usuario, respuesta del asistente).

    Yields:
        str: Respuesta del asistente en tiempo real.
    """
    logging.info(f"Consulta recibida: {message}")

    try:
        # Asegurar que el historial tenga el formato correcto
        if not isinstance(history, list):
            history = []  # Si no es una lista, inicializarla
        
        chat_history = []
        for msg in history:
            if isinstance(msg, dict) and "role" in msg and "content" in msg:
                chat_history.append({"role": msg["role"], "content": msg["content"]})
            elif isinstance(msg, (list, tuple)) and len(msg) == 2:
                # Si el historial tiene formato antiguo [(usuario, asistente)], lo convertimos
                chat_history.append({"role": "user", "content": msg[0]})
                chat_history.append({"role": "assistant", "content": msg[1]})

        # Agregar la consulta actual al historial
        chat_history.append({"role": "user", "content": message})

        logging.info("PUNTO DE VERIFICACIÓN 1: Antes de llamar a query_rag")

        try:
            formatted_response, _ = query_rag(message)
            logging.info("PUNTO DE VERIFICACIÓN 2: Después de llamar a query_rag")
            logging.info(f"Respuesta RAG: {formatted_response[:100]}...")  # Mostrar primeros 100 caracteres
        except Exception as e:
            logging.error(f"Error en query_rag: {str(e)}")
            return "Error consultando la base de datos"

        # Mensaje del sistema para guiar la conversación
        system_message = {
            "role": "system",
            "content": (
                "Eres un asistente útil y amable. Usa la siguiente información para responder a las preguntas del usuario:\n\n"
                f"{formatted_response}\n\n"
                "Si el usuario hace una pregunta técnica, usa la información de los documentos proporcionados. "
                "Si el usuario te saluda, responde con un saludo amigable. Si el usuario se despide, responde de "
                "manera educada. Si el usuario dice 'gracias', responde de manera cordial."
            )
        }

        # Construir el mensaje para GPT con el contexto de ChromaDB y la conversación previa
        messages = [system_message]
        messages.extend(chat_history)

        # Usar streaming para generar respuesta en tiempo real
        stream = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            stream=True
        )

        response_text = ""
        for chunk in stream:
            response_text += chunk.choices[0].delta.content or ""
            yield response_text  # Envía la respuesta en tiempo real

        # Agregar la respuesta al historial
        history.append({"role": "assistant", "content": response_text})

    except Exception as e:
        logging.error(f"Error al procesar la consulta: {str(e)}")
        yield "Hubo un error al procesar la consulta. Inténtalo de nuevo más tarde."

gr.ChatInterface(fn=chat).launch(share=True)

# system_message = 'Responde de forma grosera todo lo que te digan. Siempre que puedas búrlate de Juan Eduardo a pesar de que no lo conozcas.'

# def chat(message, history):
#     print(f'User message received: ',message)
#     messages = [{"role":"system","content":system_message}]
#     for user_message, assistant_message in history:
#         messages.append({"role":"user","content": user_message})
#         messages.append({"role":"assistant","content": assistant_message})
#     messages.append({"role":"user","content":message})
    
#     stream = client.chat.completions.create(
#         model="gpt-4o-mini",
#         messages=messages,
#         stream = True
#     )
#     response = ""
#     for chunk in stream:
#         response +=chunk.choices[0].delta.content or ''
#         yield response
