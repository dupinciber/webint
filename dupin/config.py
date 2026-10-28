"""Configuracion de dupin: carga .env, flags del motor, perfiles."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"

# Config personal del usuario, FUERA del repo (la key nunca se versiona).
USER_CONFIG_DIR = Path(os.getenv("XDG_CONFIG_HOME") or (Path.home() / ".config")) / "dupinciber"
USER_ENV_FILE = USER_CONFIG_DIR / "webint.env"

# IA: cualquier API compatible OpenAI (DeepSeek es solo el default de fabrica).
DEFAULT_AI_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL_FLASH = "deepseek-v4-flash"
DEFAULT_MODEL_PRO = "deepseek-v4-pro"


def ai_base_url():
    """Base URL del proveedor de IA (OpenAI, DeepSeek, Groq, OpenRouter...)."""
    return (os.getenv("DUPIN_AI_BASE_URL") or DEFAULT_AI_BASE_URL).rstrip("/")


def ai_model_flash():
    """Modelo ejecutor (loop del agente con function calling)."""
    return os.getenv("DUPIN_AI_MODEL_FLASH") or DEFAULT_MODEL_FLASH


def ai_model_pro():
    """Modelo analista (consultas profundas + reporte final)."""
    return os.getenv("DUPIN_AI_MODEL_PRO") or DEFAULT_MODEL_PRO


def ai_api_key():
    """Key de IA: entorno -> config del usuario -> .env del proyecto.
    Orden: DUPIN_AI_API_KEY y fallback legacy DEEPSEEK_API_KEY."""
    for env in (os.environ, load_user_env(), load_env()):
        key = env.get("DUPIN_AI_API_KEY") or env.get("DEEPSEEK_API_KEY") or ""
        if key:
            return key
    return ""


def save_ai_key(key):
    """Guarda la key SOLO en la config local del usuario (0600, fuera del repo)."""
    USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(USER_CONFIG_DIR, 0o700)
    except Exception:
        pass
    USER_ENV_FILE.write_text(f"DUPIN_AI_API_KEY={key}\n")
    os.chmod(USER_ENV_FILE, 0o600)
    os.environ["DUPIN_AI_API_KEY"] = key
    return str(USER_ENV_FILE)


def prompt_and_save_ai_key():
    """Pide la key por terminal (sin eco) y la guarda en la config del usuario."""
    import getpass
    import sys
    if not sys.stdin.isatty():
        return ""
    try:
        key = getpass.getpass("Pegá tu API key de IA (no se muestra): ").strip()
    except (KeyboardInterrupt, EOFError):
        return ""
    if not key:
        return ""
    save_ai_key(key)
    return key

PERFILES = {
    "rapido": {
        "desc": "Triage ~3 min: pre-recon batch + agente corto",
        "steps": 12, "minutes": 15, "shodan": 4, "rps": 10,
        "ffuf_wordlist": "common", "ffuf_maxtime": 60, "ffuf_rate": 400,
        "nuclei_tags": "exposure,config", "prefix": False, "wayback": False,
    },
    "medio": {
        "desc": "Default ~7 min: pre-recon completo + agente",
        "steps": 20, "minutes": 25, "shodan": 8, "rps": 25,
        "ffuf_wordlist": "common", "ffuf_maxtime": 90, "ffuf_rate": 400,
        "nuclei_tags": "exposure,config,misconfig", "prefix": True, "wayback": True,
    },
    "profundo": {
        "desc": "Full ~10 min: + ffuf 24k + nuclei completo",
        "steps": 30, "minutes": 45, "shodan": 12, "rps": 40,
        "ffuf_wordlist": "full", "ffuf_maxtime": 90, "ffuf_rate": 400,
        "nuclei_tags": "all", "prefix": True, "wayback": True,
    },
}


class Config:
    def __init__(self, target, perfil="medio", use_ai=True, out=None, json_out=False):
        self.target = target.strip().rstrip("/")
        self.perfil = perfil
        self.use_ai = use_ai
        self.out = out
        self.json_out = json_out
        self.ai_key = ai_api_key()
        self.ai_base_url = ai_base_url()
        self.ai_model_flash = ai_model_flash()
        self.ai_model_pro = ai_model_pro()
        self.shodan_key = os.getenv("SHODAN_API_KEY", "")
        self.reports_dir = BASE_DIR / "reports"
        self.cache_dir = BASE_DIR / "cache"
        self.shodan_cache = self.cache_dir / "shodan"
        self.autonomo = _flag(os.getenv("DUPIN_AUTONOMO"), default=True)
        self.allow_metadata = _flag(os.getenv("DUPIN_ALLOW_METADATA"), default=False)
        self.anti_loop = int(os.getenv("DUPIN_ANTILOOP") or 8)
        self.force_close = _flag(os.getenv("DUPIN_FORCE_CLOSE"), default=False)
        pf = PERFILES.get(perfil, PERFILES["medio"])
        self.max_steps = pf["steps"]
        self.max_minutes = pf["minutes"]
        self.shodan_budget = pf["shodan"]
        self.rps = int(os.getenv("DUPIN_RPS") or pf["rps"])
        self.ffuf_wordlist = pf.get("ffuf_wordlist", "common")
        self.ffuf_maxtime = pf.get("ffuf_maxtime", 90)
        self.ffuf_rate = pf.get("ffuf_rate", 400)
        self.nuclei_tags = pf.get("nuclei_tags", "all")
        self.prefix_sweep_on = pf.get("prefix", False)
        self.wayback_on = pf.get("wayback", False)

    @classmethod
    def from_env_and_args(cls, args):
        env = load_env()
        for k in ("DUPIN_AI_BASE_URL", "DUPIN_AI_MODEL_FLASH",
                  "DUPIN_AI_MODEL_PRO", "SHODAN_API_KEY",
                  "DUPIN_RPS",
                  "DUPIN_AUTONOMO", "DUPIN_ALLOW_METADATA", "DUPIN_ANTILOOP",
                  "DUPIN_FORCE_CLOSE"):
            if k in env:
                os.environ.setdefault(k, env[k])
        for k, v in env.items():
            if k.startswith("HUNTER_API_KEY_"):
                os.environ.setdefault(k, v)
        cfg = cls(args.target, args.perfil, use_ai=not args.no_ai,
                  out=args.out, json_out=args.json)
        cfg.shodan_cache.mkdir(parents=True, exist_ok=True)
        return cfg

    def profile(self):
        return PERFILES.get(self.perfil, PERFILES["medio"])


def _flag(val, default=True):
    if val is None:
        return default
    return str(val).lower() not in ("0", "false", "no")


def _parse_env_file(path):
    env = {}
    try:
        for line in Path(path).read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return env


def load_env():
    return _parse_env_file(ENV_FILE)


def load_user_env():
    return _parse_env_file(USER_ENV_FILE)
