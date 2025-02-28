import pickle
import warnings
import json
import os
import time
import random
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from tqdm import tqdm
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException

# Ocultar warnings innecesarios
warnings.filterwarnings("ignore", category=UserWarning, module="requests")
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=ResourceWarning)

# Cargar IDs desde el archivo pickle
with open("ids.pkl", "rb") as f:
    ids_dict = pickle.load(f)

# Crear directorio para guardar archivos de texto
if not os.path.exists("documentos"):
    os.makedirs("documentos")

# URL base
BASE_URL = "https://legal.unal.edu.co/rlunal/home/doc.jsp?d_i={}&tmt={}&subtm="

# Función para iniciar Selenium con o sin headless
def iniciar_driver(headless=False):
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless")  # Solo activar si es necesario
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920x1080")
    options.add_argument("--log-level=3")  # Oculta warnings de Selenium
    print("🌐 Iniciando ChromeDriver... (headless =", headless, ")")  # Debug
    return webdriver.Chrome(options=options)

# Función para manejar captchas
def resolver_captcha(driver):
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CLASS_NAME, "ui-dialog ui-corner-all ui-widget ui-widget-content ui-front ui-draggable ui-resizable"))
        )
        print("\n🚨 ¡Captcha detectado! Cerrando navegador y reabriéndolo para resolver...")

        captcha_url = driver.current_url
        driver.quit()

        driver = iniciar_driver(headless=False)
        driver.get(captcha_url)

        input("🔑 Resuelve el captcha en el navegador y presiona Enter aquí para continuar...")

        return driver
    except:
        return driver

# Función para obtener HTML con Selenium y manejar `stale element reference`
def obtener_html_selenium(d_i, tmt):
    url = BASE_URL.format(d_i, tmt)
    driver = iniciar_driver(headless=False)
    driver.get(url)

    driver = resolver_captcha(driver)

    try:
        # Intentar obtener el contenido con reintentos
        for _ in range(3):  # Reintentar hasta 3 veces en caso de `stale element`
            try:
                body = driver.find_element(By.TAG_NAME, "body")
                for _ in range(3):  # Hacer scroll varias veces
                    body.send_keys(Keys.PAGE_DOWN)
                    time.sleep(2)

                # Esperar hasta que el div tenga texto
                WebDriverWait(driver, 30).until(
                    lambda d: d.find_element(By.ID, "nor_texto").text.strip() != ""
                )

                # Obtener el HTML final
                html = driver.page_source
                break  # Si no hay error, salir del bucle
            except StaleElementReferenceException:
                print("🔄 Elemento cambiado, reintentando extracción...")
                time.sleep(3)  # Espera antes de reintentar
                continue
        else:
            html = None  # Si después de 3 intentos sigue fallando, devolver None

    except TimeoutException:
        print(f"⚠ Tiempo de espera agotado para {url}")
        html = None

    driver.quit()
    return html

# Función para extraer contenido del div
def extraer_html_completo(html):
    soup = BeautifulSoup(html, "html.parser")
    div = soup.find('div', id='nor_texto')
    text = div.get_text(separator=' ', strip=True)
    print(text)
    return text if text else "⚠ No se pudo obtener el contenido."

# Iniciar scraping
total_documentos = sum(len(id_tuples) for id_tuples in ids_dict.values())
resultados = {}

print(f"🔍 Iniciando scraping de {total_documentos} documentos...\n")

with open("visited.pkl", "rb") as f:
    visited = pickle.load(f)

with tqdm(total=total_documentos, desc="Procesando", unit="doc", leave=False, ncols=80) as pbar:
    for categoria, id_tuples in ids_dict.items():
        resultados[categoria] = {}

        for d_i, tmt in id_tuples:
            print(f"📄 Accediendo a d_i: {d_i}, tmt: {tmt}")

            html = obtener_html_selenium(d_i, tmt)
            contenido_html = extraer_html_completo(html) if html else "⚠ No se pudo obtener el contenido."
            resultados[categoria][(d_i, tmt)] = contenido_html

            filename = f"documentos/{categoria}-{d_i}-{tmt}.txt"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(contenido_html)
            visited.add(id_tuples)
            with open('visited.pkl', 'wb') as file:
                pickle.dump(visited, file)
            print(f"✅ Guardado en {filename}")
            pbar.update(1)
            time.sleep(random.uniform(2, 5))

with open("resultados.json", "w", encoding="utf-8") as f:
    json.dump(resultados, f, ensure_ascii=False, indent=4)

print("\n🎉 Scraping completado y datos guardados en la carpeta 'documentos/' y en resultados.json")