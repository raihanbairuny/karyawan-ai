"""
Karyawan AI — Base Agent
Kelas dasar untuk semua Karyawan AI.
Menggunakan Google Gemini API sebagai otak.
"""

import google.generativeai as genai
from config import settings

# Configure Gemini API
genai.configure(api_key=settings.GEMINI_API_KEY)


class BaseAgent:
    """
    Base class untuk semua Karyawan AI.

    Setiap agent memiliki:
    - name: Nama karyawan (lowercase, untuk routing)
    - display_name: Nama tampilan (capitalized)
    - role: Jabatan/peran
    - emoji: Emoji representasi
    - system_prompt: Instruksi khusus untuk AI
    """

    def __init__(
        self,
        name: str,
        role: str,
        emoji: str,
        system_prompt: str,
    ):
        self.name = name
        self.display_name = name.capitalize()
        self.role = role
        self.emoji = emoji
        self.system_prompt = system_prompt
        self.model = genai.GenerativeModel(settings.GEMINI_MODEL)

    def think(self, prompt: str, context: str = None, json_mode: bool = False) -> str:
        """
        Mengirim prompt ke Gemini API dan mengembalikan hasil pemikiran.

        Args:
            prompt: Perintah dari user.
            context: Konteks tambahan (opsional).
            json_mode: Memaksa respons menjadi format JSON string.

        Returns:
            Hasil pemikiran AI dalam bentuk string (atau JSON string).
        """
        full_prompt = self.system_prompt + "\n\n"

        if context:
            full_prompt += f"=== KONTEKS TAMBAHAN ===\n{context}\n\n"

        full_prompt += f"=== PERINTAH DARI USER ===\n{prompt}"
        
        # Tambahkan instruksi JSON murni jika mode aktif
        if json_mode:
            full_prompt += "\n\nKEMBALIKAN OUTPUT HANYA DALAM BENTUK JSON (Tanpa blok markdown ```json)."

        try:
            config = genai.types.GenerationConfig(
                temperature=0.4 if json_mode else 0.7,
                max_output_tokens=4096,
            )
            if json_mode:
                config.response_mime_type = "application/json"
                
            response = self.model.generate_content(
                full_prompt,
                generation_config=config,
            )
            return response.text
        except Exception as e:
            raise Exception(
                f"{self.emoji} {self.display_name} gagal memproses: {str(e)}"
            )

    def get_info(self) -> dict:
        """Return informasi agent untuk API response."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "role": self.role,
            "emoji": self.emoji,
        }
