import pandas as pd
from rouge import Rouge
import json
import logging
from rag import query_rag
import numpy as np
import json
import pandas as pd
from evaluate import load
from sentence_transformers import SentenceTransformer, util


def rouge_score():
    # Cargar el archivo JSON
    with open('./eval_docs/test.json', "r", encoding="utf-8") as file:
        data = json.load(file)

    rouge = Rouge()
    results = []

    # Calcular ROUGE para cada par de respuestas
    for item in data["test_data"]:
        answer = item["answer"]
        generated_answer = item["generated_answer"]

        scores = rouge.get_scores(generated_answer, answer, avg=True)

        results.append({
            "id": item["id"],
            "question": item["question"],
            "rouge-1": scores["rouge-1"]["f"],
            "rouge-2": scores["rouge-2"]["f"],
            "rouge-l": scores["rouge-l"]["f"]
        })

    # Convertir resultados en un DataFrame de Pandas
    df = pd.DataFrame(results)

    # Calcular estadísticas generales
    stats = df[["rouge-1", "rouge-2", "rouge-l"]].agg(["mean", "min", "max", "std"])

    # Mostrar estadísticas generales
    print("\n📊 Estadísticas Generales de ROUGE:")
    print(stats)

    # Mostrar primeros 5 registros para referencia
    print("\n📋 Primeros 5 registros con ROUGE:")
    print(df.head())
    
    # Convertir las estadísticas a diccionario
    stats_dict = stats.to_dict()

    # Guardar los resultados en JSON
    output_json = {
        "individual_scores": results,
        "summary_statistics": stats_dict
    }

    # Guardar los resultados en un archivo JSON
    with open('./eval_docs/rouge_results.json', "w", encoding="utf-8") as file:
        json.dump(output_json, file, ensure_ascii=False, indent=4)

def paraphrase_score():
    # Cargar el modelo paraphrase-multilingual-MiniLM-L12-v2
    model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

    # Cargar el archivo JSON con las respuestas
    with open('./eval_docs/test.json', "r", encoding="utf-8") as file:
        data = json.load(file)

    results = []

    # Calcular similitud para cada par de respuestas
    for item in data["test_data"]:
        answer = item["answer"]
        generated_answer = item["generated_answer"]

        # Obtener embeddings
        embedding1 = model.encode(answer, convert_to_tensor=True)
        embedding2 = model.encode(generated_answer, convert_to_tensor=True)

        # Calcular similitud del coseno
        similarity = util.cos_sim(embedding1, embedding2).item()

        results.append({
            "id": item["id"],
            "question": item["question"],
            "similarity": similarity
        })

    # Convertir resultados en un DataFrame
    df = pd.DataFrame(results)

    # Calcular estadísticas generales
    stats = df["similarity"].agg(["mean", "min", "max", "std"])

    # Guardar los resultados en un archivo JSON
    output_json = {
        "individual_scores": results,
        "summary_statistics": stats.to_dict()
    }

    with open("./eval_docs/paraphrase_similarity.json", "w", encoding="utf-8") as json_file:
        json.dump(output_json, json_file, indent=4, ensure_ascii=False)

    print("\n✅ Resultados guardados en 'paraphrase_similarity.json'")
    print("\n📊 Estadísticas Generales:")
    print(stats)

def bert_score():

    bertscore = load("bertscore")
    # Cargar el archivo JSON con las respuestas
    with open('./eval_docs/test.json', "r", encoding="utf-8") as file:
        data = json.load(file)

    # Extraer respuestas reales y generadas
    references = [item["answer"] for item in data["test_data"]]
    candidates = [item["generated_answer"] for item in data["test_data"]]

    # Calcular BERTScore con un modelo multilingüe (para español)
    results = bertscore.compute(predictions=candidates, references=references, model_type="bert-base-multilingual-cased")

    # Convertir a DataFrame
    df = pd.DataFrame({
        "id": [item["id"] for item in data["test_data"]],
        "question": [item["question"] for item in data["test_data"]],
        "bert_precision": results["precision"],
        "bert_recall": results["recall"],
        "bert_f1": results["f1"]
    })

    # Calcular estadísticas generales
    stats = df[["bert_precision", "bert_recall", "bert_f1"]].agg(["mean", "min", "max", "std"])

    # Guardar los resultados en un archivo JSON
    output_json = {
        "individual_scores": df.to_dict(orient="records"),
        "summary_statistics": stats.to_dict()
    }

    with open("./eval_docs/bert_score_hf.json", "w", encoding="utf-8") as json_file:
        json.dump(output_json, json_file, indent=4, ensure_ascii=False)

    print("\n✅ Resultados guardados en 'bert_score_hf.json'")
    print("\n📊 Estadísticas Generales:")
    print(stats)

def test_questions():
    with open('./eval_docs/test.json', 'r', encoding='utf-8') as file:
        data = json.load(file)

    for i in range(len(data['test_data'])):
        logging.info(f"Consulta recibida: {data['test_data'][i]['question']}")
        try:
            _, data['test_data'][i]['generated_answer'] = query_rag(data['test_data'][i]['question'])

        except Exception as e:
            logging.error(f"Error: {str(e)}")
            return "Error consultando la base de datos"
        
    with open('./eval_docs/test.json', 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

def scores():
    rouge_score()
    paraphrase_score()
    bert_score()