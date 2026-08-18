"""
Karyawan AI — Web Tools
Alat untuk melakukan pencarian di internet dan membaca halaman web.
"""

from duckduckgo_search import DDGS
import requests
from bs4 import BeautifulSoup

def search_web(query: str, max_results: int = 5) -> dict:
    """
    Melakukan pencarian di internet menggunakan DuckDuckGo dengan fallback.
    """
    try:
        # Percobaan 1: Menggunakan pustaka resmi duckduckgo_search
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            
        if not results:
            raise Exception("No results found via API")
            
        formatted_results = []
        for i, res in enumerate(results):
            formatted_results.append(f"{i+1}. {res.get('title')}\nURL: {res.get('href')}\nSnippet: {res.get('body')}\n")
            
        return {
            "success": True,
            "data": "\n".join(formatted_results)
        }
    except Exception as api_err:
        print(f"DDGS API Error: {api_err}. Mencoba fallback HTML scraping...")
        # Percobaan 2: Fallback manual scraping jika Rate Limit
        try:
            import urllib.parse
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
            }
            res = requests.get(f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}", headers=headers, timeout=15)
            soup = BeautifulSoup(res.text, 'html.parser')
            
            results = []
            for a in soup.find_all('a', class_='result__url', limit=max_results):
                url = a.get('href')
                if url:
                    # Parse title from sibling or parent
                    title_elem = a.find_parent('div', class_='result__body').find('a', class_='result__snippet')
                    title = a.get_text(strip=True)
                    snippet = title_elem.get_text(strip=True) if title_elem else ""
                    results.append(f"- URL: {url}\nSnippet: {snippet}\n")
            
            if not results:
                return {"success": False, "error": f"Rate limit API & Fallback tidak menemukan data. Pesan asli: {api_err}"}
                
            return {
                "success": True,
                "data": "\n".join(results)
            }
        except Exception as fb_err:
            return {
                "success": False,
                "error": f"API Error: {api_err} | Fallback Error: {fb_err}"
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
