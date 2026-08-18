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
        print(f"DDGS API Error: {api_err}. Beralih ke Fallback API (Wikipedia / StackOverflow)...")
        # Percobaan 2: Fallback ke Public APIs yang tidak di-block (Wikipedia & StackOverflow)
        import urllib.parse
        results = []
        query_lower = query.lower()
        
        # Jika query berbau coding/error, gunakan StackOverflow API
        if any(kw in query_lower for kw in ['error', 'exception', 'bug', 'python', 'javascript', 'php', 'java', 'c++']):
            try:
                so_url = f"https://api.stackexchange.com/2.3/search/advanced?order=desc&sort=relevance&q={urllib.parse.quote(query)}&site=stackoverflow&filter=withbody"
                res = requests.get(so_url, timeout=10)
                if res.status_code == 200:
                    items = res.json().get('items', [])[:3]
                    for item in items:
                        title = item.get('title', '')
                        link = item.get('link', '')
                        body = item.get('body', '')[:200] # Potong agar tidak kepanjangan
                        results.append(f"- [StackOverflow] {title}\nURL: {link}\nSnippet: {body}...\n")
            except Exception as e:
                print(f"StackOverflow Fallback Error: {e}")
                
        # Jika bukan coding atau StackOverflow kosong, gunakan Wikipedia API
        if not results:
            try:
                wiki_url = f"https://id.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(query)}&utf8=&format=json"
                res = requests.get(wiki_url, timeout=10)
                if res.status_code == 200:
                    items = res.json().get('query', {}).get('search', [])[:3]
                    for item in items:
                        title = item.get('title', '')
                        snippet = item.get('snippet', '')
                        # Bersihkan tag HTML sederhana dari snippet Wikipedia
                        import re
                        snippet_clean = re.sub('<[^<]+>', '', snippet)
                        link = f"https://id.wikipedia.org/wiki/{urllib.parse.quote(title)}"
                        results.append(f"- [Wikipedia] {title}\nURL: {link}\nSnippet: {snippet_clean}...\n")
            except Exception as e:
                print(f"Wikipedia Fallback Error: {e}")
                
        if not results:
            return {"success": False, "error": f"Pencarian diblokir (Rate limit). API alternatif (SO/Wiki) tidak menemukan kecocokan untuk: '{query}'"}
            
        return {
            "success": True,
            "data": "\n".join(results)
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
