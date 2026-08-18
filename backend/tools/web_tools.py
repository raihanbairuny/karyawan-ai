"""
Karyawan AI — Web Tools
Alat untuk melakukan pencarian di internet dan membaca halaman web.
"""

from duckduckgo_search import DDGS
import requests
from bs4 import BeautifulSoup

def search_web(query: str, max_results: int = 5) -> dict:
    """
    Melakukan pencarian di internet menggunakan DuckDuckGo.
    """
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            
        formatted_results = []
        for i, res in enumerate(results):
            formatted_results.append(f"{i+1}. {res.get('title')}\nURL: {res.get('href')}\nSnippet: {res.get('body')}\n")
            
        return {
            "success": True,
            "data": "\n".join(formatted_results)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def read_url_content(url: str) -> dict:
    """
    Membaca dan mengekstrak teks dari sebuah URL.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Hapus script dan style
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.extract()
            
        text = soup.get_text(separator='\n', strip=True)
        
        # Batasi panjang teks agar tidak over limit token
        if len(text) > 10000:
            text = text[:10000] + "\n... (Teks dipotong karena terlalu panjang)"
            
        return {
            "success": True,
            "data": text
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
