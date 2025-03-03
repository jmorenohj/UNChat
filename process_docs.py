from langchain.schema import Document
from langchain.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from dotenv import load_dotenv
import os
import shutil
import unicodedata
import logging

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Directorio donde están los archivos .txt
DATA_PATH = os.path.join(BASE_DIR, "documentos")

# Directorio donde se guardará la base de datos Chroma
CHROMA_PATH = os.path.join(BASE_DIR, "database")

# Crear los directorios si no existen
os.makedirs(DATA_PATH, exist_ok=True)
os.makedirs(CHROMA_PATH, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def normalize_filename(filename):
    """Convierte caracteres con tildes a su versión sin tilde."""
    normalized = unicodedata.normalize("NFKD", filename).encode("ASCII", "ignore").decode("ASCII")
    return normalized

def load_documents():
    """
    Carga documentos de texto desde el directorio especificado.
    
    Returns:
        List[Document]: Documentos cargados representados como objetos de LangChain.
    """
    logging.info(f"Comenzando carga de documentos desde: {DATA_PATH}")
    documents = []
    
    # Verificar que el directorio existe
    if not os.path.exists(DATA_PATH):
        logging.error(f"El directorio {DATA_PATH} no existe. Creándolo...")
        os.makedirs(DATA_PATH, exist_ok=True)
    
    # Listar todos los archivos en el directorio
    files = os.listdir(DATA_PATH)
    logging.info(f"Archivos encontrados en el directorio: {files}")
    
    # Recorre todos los archivos en el directorio
    for filename in files:
        if filename.endswith(".txt"):
            file_path = os.path.join(DATA_PATH, filename)
            logging.info(f"Procesando archivo: {filename}")
            
            # Verificar que el archivo existe y es accesible
            if not os.path.isfile(file_path):
                logging.error(f"El archivo {file_path} no es un archivo válido")
                continue
                
            # Verificar tamaño del archivo
            file_size = os.path.getsize(file_path)
            logging.info(f"Tamaño del archivo {filename}: {file_size} bytes")
            
            if file_size == 0:
                logging.warning(f"El archivo {filename} está vacío, saltándolo")
                continue
            
            # Normalizar el nombre del archivo
            normalized_filename = normalize_filename(filename)
            normalized_path = os.path.join(DATA_PATH, normalized_filename)

            # Si el nombre original y el normalizado son diferentes, renombrar el archivo
            if filename != normalized_filename:
                logging.info(f"Normalizando nombre de archivo: {filename} -> {normalized_filename}")
                os.rename(file_path, normalized_path)
                file_path = normalized_path  # Usar la nueva ruta normalizada

            try:
                logging.info(f"Cargando contenido de {file_path}...")
                
                # Intentar abrir el archivo para verificar contenido
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    logging.info(f"Contenido leído: {len(content)} caracteres")
                    if not content.strip():
                        logging.warning(f"El archivo {filename} tiene contenido vacío")
                
                loader = TextLoader(file_path, encoding="utf-8")  # Forzar UTF-8
                loaded_docs = loader.load()
                logging.info(f"Documentos cargados de {filename}: {len(loaded_docs)}")
                documents.extend(loaded_docs)
            except UnicodeDecodeError as e:
                logging.error(f"Error de codificación en {filename}: {str(e)}")
                # Intentar con otra codificación
                try:
                    loader = TextLoader(file_path, encoding="latin-1")
                    loaded_docs = loader.load()
                    logging.info(f"Cargado con latin-1: {len(loaded_docs)} documentos")
                    documents.extend(loaded_docs)
                except Exception as e2:
                    logging.error(f"Segundo intento fallido: {str(e2)}")
            except Exception as e:
                logging.error(f"Error cargando {filename}: {str(e)}", exc_info=True)
    
    logging.info(f"Total de documentos cargados: {len(documents)}")
    return documents

def split_text(documents: list[Document]):
    """
    Divide los documentos en fragmentos más pequeños y añade un metadato "derogado" si el texto contiene esa palabra.
    
    Args:
        documents (list[Document]): Lista de objetos Document.
    
    Returns:
        list[Document]: Lista de fragmentos de texto con metadatos.
    """
    logging.info(f"Iniciando división de {len(documents)} documentos")
    
    if not documents:
        logging.warning("No hay documentos para dividir")
        return []
    
    # Inspeccionar los documentos recibidos
    for i, doc in enumerate(documents[:3]):  # Mostrar hasta 3 documentos
        logging.info(f"Documento {i+1}: {len(doc.page_content)} caracteres, metadatos: {doc.metadata}")
    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,  
        chunk_overlap=200,  
        length_function=len,  
        add_start_index=True,  
    )

    logging.info("Dividiendo documentos en fragmentos...")
    chunks = text_splitter.split_documents(documents)
    logging.info(f"Documentos divididos en {len(chunks)} fragmentos")

    # Agregar metadato "derogado" si aparece en el texto
    derogados = 0
    for chunk in chunks:
        is_derogado = "derogado" in chunk.page_content.lower()
        chunk.metadata["derogado"] = "Sí" if is_derogado else "No"
        if is_derogado:
            derogados += 1

    logging.info(f"Total fragmentos: {len(chunks)}, Derogados: {derogados}")

    # Inspeccionar los primeros fragmentos
    for i, chunk in enumerate(chunks[:3]):  # Mostrar hasta 3 fragmentos
        logging.info(f"Fragmento {i+1}: {len(chunk.page_content)} caracteres")
        logging.info(f"Contenido: {chunk.page_content[:100]}...")
        logging.info(f"Metadatos: {chunk.metadata}")

    return chunks

def save_to_chroma(chunks: list[Document]):
    """
    Guarda la lista de objetos Document en una base de datos Chroma.

    Args:
    chunks (list[Document]): Lista de objetos Document que representan los fragmentos de texto a guardar.
    """
    logging.info(f"Iniciando guardado de {len(chunks)} fragmentos en Chroma")
    
    if not chunks:
        logging.error("No hay fragmentos para guardar en Chroma")
        return
    
    # Verificar API key de OpenAI
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        logging.error("No se encontró la API Key de OpenAI")
        return
    logging.info("API Key de OpenAI encontrada")

    # Eliminar el directorio de la base de datos Chroma si ya existe
    if os.path.exists(CHROMA_PATH):
        logging.info(f"Eliminando directorio existente: {CHROMA_PATH}")
        shutil.rmtree(CHROMA_PATH)
    
    try:
        logging.info("Creando embeddings con OpenAI...")
        embeddings = OpenAIEmbeddings()
        
        logging.info("Inicializando Chroma con los documentos...")
        db = Chroma.from_documents(
            chunks,
            embeddings,
            persist_directory=CHROMA_PATH
        )
        
        # Verificar que la base de datos contiene los documentos
        collection = db._collection
        count = collection.count()
        logging.info(f"Chroma reporta {count} documentos almacenados")
        
        # Guardar la base de datos en disco
        logging.info("Persistiendo base de datos en disco...")
        # db.persist()
        logging.info(f"Base de datos guardada exitosamente en {CHROMA_PATH}")
        
    except Exception as e:
        logging.error(f"Error al guardar en Chroma: {str(e)}", exc_info=True)

def generate_data_store():
    """
    Función para generar una base de datos de vectores en Chroma a partir de documentos.
    """
    logging.info("Iniciando generación de la base de datos de vectores")
    
    # Cargar variables de entorno desde el archivo .env
    load_dotenv()
    
    # Verificar API key de OpenAI
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        logging.error("No se encontró la API Key de OpenAI en el archivo .env")
        return
    logging.info("API Key de OpenAI encontrada")
    
    # Cargar documentos de texto
    logging.info("Cargando documentos...")
    documents = load_documents()

    if not documents:
        logging.error("No se pudieron cargar documentos")
        return
    
    # Dividir los documentos en fragmentos
    logging.info("Dividiendo documentos en fragmentos...")
    chunks = split_text(documents)
    
    if not chunks:
        logging.error("No se pudieron generar fragmentos")
        return
    
    # Guardar los fragmentos en una base de datos Chroma
    logging.info("Guardando fragmentos en Chroma...")
    save_to_chroma(chunks)
    
    logging.info("Generación de la base de datos completada")