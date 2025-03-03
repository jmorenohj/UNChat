from dotenv import load_dotenv
from langchain.chat_models import ChatOpenAI 
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain.prompts import ChatPromptTemplate
import os
import logging
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Ruta donde se almacena la base de datos Chroma
CHROMA_PATH = os.path.join(BASE_DIR, "database")

PROMPT_TEMPLATE = """
Responde a la siguiente pregunta basado en el siguiente contexto:
{context}
 - -
Responde la pregunta basada en el contexto anterior: {question}
"""

def query_rag(query_text):
  """
  Consulta un sistema de Generación con Recuperación Aumentada (RAG) utilizando la base de datos Chroma y OpenAI.
  Args:
    - query_text (str): El texto de la consulta o pregunta.
  Returns:
    - formatted_response (str): Respuesta formateada que incluye el texto generado y las fuentes.
    - response_text (str): El texto generado por el modelo.
  """
  logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
  embedding_function = OpenAIEmbeddings()
  db = Chroma(persist_directory=CHROMA_PATH, embedding_function=embedding_function)

  # Buscar fragmentos similares en la base de datos
  results = db.similarity_search_with_relevance_scores(query_text, k=5)

  if not results:
      
      return "No se encontraron documentos relevantes en la base de datos.", ""

  # Filtrar documentos que no sean relevantes (score < 0.7) y evitar "derogados"
  filtered_results = [
      (doc, score) for doc, score in results
      if doc.metadata.get("derogado", "No") != "Sí" and score >= 0.7
  ]

  if not filtered_results:
      logging.info("No se encontraron documentos relevantes después de filtrar contenido derogado.")
      return "No se encontraron documentos relevantes después de filtrar contenido derogado.", ""

  # Construir el contexto usando solo los fragmentos permitidos
  context_text = "\n\n - -\n\n".join([doc.page_content for doc, _ in filtered_results])

  # Mostrar en logs los documentos recuperados
  logging.info(f"🔍 Documentos encontrados para '{query_text}': {len(filtered_results)}")
  for i, (doc, score) in enumerate(filtered_results):
      logging.info(f"📄 Doc {i+1} - Score: {score:.2f}\n{doc.page_content[:200]}...")

  # Crear el prompt con el contexto de los documentos
  prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
  prompt = prompt_template.format(context=context_text, question=query_text)

  # Generar respuesta con OpenAI
  model = ChatOpenAI()
  response_text = model.predict(prompt)

  # Formatear respuesta con fuentes
  sources = [doc.metadata.get("source", "Desconocido") for doc, _ in filtered_results]
  formatted_response = f"Respuesta basada en documentos:\n\n{response_text}\n\n📚 Fuentes: {sources}"

  logging.info(f"Respuesta generada: {response_text}")
  return formatted_response, response_text

