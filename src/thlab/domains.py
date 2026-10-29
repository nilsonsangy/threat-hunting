"""thlab.domains — listas de domínios suspeitos e classificação de URL.

Duas categorias de navegação acusam risco de insider no laboratório (R4):

- **Emprego** — sites de busca de vaga/recolocação (indeed, linkedin jobs,
  glassdoor, etc.). Sinalizam intenção de saída da empresa.
- **Nuvem pessoal** — serviços de armazenamento pessoal (dropbox, Google Drive,
  OneDrive, etc.). Sinalizam possível exfiltração para fora do perímetro.

O núcleo é puro e offline: apenas casamento de substring sobre a URL, sem
qualquer acesso de rede.
"""

from __future__ import annotations

from urllib.parse import urlparse

# Fragmentos de domínio/caminho que caracterizam busca de emprego.
# Casados por substring (case-insensitive) contra a URL completa, de modo que
# "www.indeed.com/jobs" e "indeed.com" batam no mesmo fragmento "indeed.com".
DOMINIOS_EMPREGO: tuple[str, ...] = (
    "indeed.com",
    "linkedin.com/jobs",
    "glassdoor.com",
    "monster.com",
    "ziprecruiter.com",
    "dice.com",
    "catho.com",
    "vagas.com",
    "infojobs.com",
    "gupy.io",
)

# Fragmentos que caracterizam nuvem de armazenamento pessoal.
DOMINIOS_NUVEM: tuple[str, ...] = (
    "dropbox.com",
    "drive.google.com",
    "docs.google.com",
    "onedrive.live.com",
    "1drv.ms",
    "box.com",
    "mega.nz",
    "mega.io",
    "wetransfer.com",
    "icloud.com",
    "pcloud.com",
)


def _normaliza(url: str) -> str:
    """Normaliza a URL para casamento por substring.

    Junta host + caminho em minúsculas para que fragmentos como
    ``linkedin.com/jobs`` possam ser casados mesmo quando o esquema
    (``https://``) ou o ``www.`` estão presentes.
    """
    if url is None:
        return ""
    texto = str(url).strip().lower()
    if not texto:
        return ""
    # Garante um esquema para o urlparse separar host/caminho corretamente.
    parseavel = texto if "://" in texto else f"//{texto}"
    try:
        partes = urlparse(parseavel)
        host = (partes.netloc or "").removeprefix("www.")
        return f"{host}{partes.path}"
    except ValueError:
        # Em caso de URL malformada, cai para a string crua minúscula.
        return texto.removeprefix("https://").removeprefix("http://").removeprefix("www.")


def eh_dominio_emprego(url: str) -> bool:
    """True se a URL aponta para um site de busca de emprego."""
    alvo = _normaliza(url)
    return any(frag in alvo for frag in DOMINIOS_EMPREGO)


def eh_dominio_nuvem(url: str) -> bool:
    """True se a URL aponta para um serviço de nuvem pessoal."""
    alvo = _normaliza(url)
    return any(frag in alvo for frag in DOMINIOS_NUVEM)


def classifica_url(url: str) -> str | None:
    """Classifica uma URL como navegação suspeita.

    Retorna ``"emprego"``, ``"nuvem"`` ou ``None`` quando a URL não casa com
    nenhuma das listas. Emprego tem precedência sobre nuvem quando ambos casam.
    """
    if eh_dominio_emprego(url):
        return "emprego"
    if eh_dominio_nuvem(url):
        return "nuvem"
    return None


def eh_suspeita(url: str) -> bool:
    """True se a URL é de emprego OU de nuvem pessoal (navegação suspeita)."""
    return classifica_url(url) is not None
