"""
Karyawan AI — Agent Registry
Central registry untuk semua Karyawan AI.
"""

from agents.arif import arif
from agents.budi import budi
from agents.citra import citra
from agents.dewi import dewi
from agents.eka import eka
from agents.fajar import fajar
from agents.gita import gita
from agents.hana import hana
from agents.indra import indra

# Registry: mapping nama karyawan → agent instance
AGENTS = {
    "arif": arif,
    "budi": budi,
    "citra": citra,
    "dewi": dewi,
    "eka": eka,
    "fajar": fajar,
    "gita": gita,
    "hana": hana,
    "indra": indra,
}


def get_agent(name: str):
    """
    Mengambil agent berdasarkan nama.

    Args:
        name: Nama karyawan (lowercase).

    Returns:
        BaseAgent instance atau None jika tidak ditemukan.
    """
    return AGENTS.get(name.lower())


def get_all_agents() -> dict:
    """Return semua agent yang terdaftar."""
    return AGENTS
