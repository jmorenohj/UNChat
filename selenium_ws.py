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

SELENIUM_DRIVER = ""
BASE_URL = ""

def init_driver(headless: bool =False):
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless")  # Solo activar si es necesario
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920x1080")
    options.add_argument("--log-level=3")  # Oculta warnings de Selenium
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36")
    print("🌐 Iniciando ChromeDriver... (headless =", headless, ")")  # Debug
    driver = webdriver.Chrome(options=options)
    return driver




def obtener_html_selenium(d_i, tmt, driver, cookie2=None):
    url = BASE_URL.format(d_i, tmt)
    driver.execute_script("window.open('', '_blank');")
    driver.switch_to.window(driver.window_handles[-1])

    if cookie2 is None:
        driver.get(url)
        cookie2 = driver.get_cookie('JSESSIONID')
    else:
        driver.get(url)
        driver.add_cookie(cookie2)

    try:
        WebDriverWait(driver, 20).until(
            lambda d: d.find_element(By.ID, "nor_texto").text.strip() != ""
        )
        html = driver.page_source
    except TimeoutException:
        print(f"⚠ Tiempo de espera agotado para {url}")
        html = None

    # driver.close()
    driver.switch_to.window(driver.window_handles[0])
    
    
    return html, cookie2  # Devolver también la cookie actualizada


SELENIUM_DRIVER = init_driver()

BASE_URL = "https://legal.unal.edu.co/rlunal/home/doc.jsp?d_i={}&tmt={}&subtm="

SELENIUM_DRIVER.close()
SELENIUM_DRIVER.quit()