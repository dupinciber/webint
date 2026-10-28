# DUPIN WEBINT — Herramienta CLI de inteligencia de sitios web, impulsada por un agente de IA autónomo

Entra un objetivo, sale una investigación completa: hallazgos, entidades y reporte escrito.
Sin servidor ni API: solo una herramienta de línea de comandos.

[![Licencia: DUPIN Source-Available](https://img.shields.io/badge/licencia-DUPIN%20Source--Available-blue)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB)](https://www.python.org/)
[![Hecho por DUPIN](https://img.shields.io/badge/por-DUPIN%20Ciberseguridad-0b1f3a)](https://dupin.com.ar)

> DUPIN WEBINT se publica como un regalo a la comunidad por [DUPIN Ciberseguridad](https://dupin.com.ar) — la firma de ciberseguridad (pentesting, red/purple team, respuesta a incidentes). Este repo es solo la herramienta CLI WEBINT.
> Código visible (source-available): podés leerlo, ejecutarlo e instalarlo, pero no modificarlo. Ver [LICENSE](LICENSE).

---

## ¿Qué es DUPIN WEBINT?

DUPIN WEBINT es el motor de investigación OSINT de sitios web de DUPIN Ciberseguridad.
Le das un dominio, una IP o un `host:puerto` y corre una investigación completa y
autónoma:

1. **Pre-recon determinista (batch):** DNS, certificate transparency, seguridad
   de email (SPF/DKIM/DMARC), RDAP, descubrimiento de subdominios, Shodan,
   Wayback, probing web, Swagger/GraphQL, minería de JavaScript, fingerprinting
   de vendors, exposición de Docker/Kubernetes, `ffuf` y `nuclei` — en paralelo.
2. **Agente de IA autónomo:** tu propio agente de IA (cualquier proveedor y
   modelo compatible OpenAI que configures) recibe el resumen del pre-recon y
   decide solo qué investigar después, paso a paso, con presupuesto de pasos y
   tiempo. No es un checklist fijo.
3. **Aspiradora de entidades:** emails, personas y empresas se extraen
   automáticamente de cada salida y se correlacionan en un grafo.
4. **Auto-enriquecimiento:** las entidades se enriquecen solas.
5. **Reporte:** `findings.jsonl` + `entities.json` + un `report.md` escrito.

> Los resultados varían entre corridas: el agente decide su propio camino y
> las consultas a CT/Wayback se cachean 24 horas por target.

## Características

- **Autónomo, no guionado** — la IA elige su camino dentro del presupuesto.
- **Traé tu propia IA** — funciona con cualquier proveedor compatible OpenAI
  (OpenAI, DeepSeek, Groq, Mistral, xAI, OpenRouter, Ollama, vLLM...). La
  primera vez te pide la key y la guarda **local, fuera de este repositorio**.
- **Pre-recon en paralelo** — decenas de sondas en batch con rate limiting.
- **60+ patrones de secretos** — `.env`, keys, tokens y connection strings, con
  redacción automática antes de que nada llegue al modelo.
- **Grafo de entidades** — emails, personas y empresas vinculados a sus fuentes.
- **Resiliente** — checkpoint/resume, cache con TTL, anti-loop y techos de tiempo.
- **Conexión directa** — sin VPN ni network namespace.

## Requisitos

- Python **3.10+**
- Paquetes Python: `requests`, `urllib3`, `pyyaml` (`pip install -r requirements.txt`)
- Herramientas externas opcionales (se usan si están): `subfinder`, `nuclei`,
  `ffuf`, `curl`, `dig`, `whois`
- Una **API key de IA** de cualquier proveedor compatible OpenAI
- Opcional: **Shodan API key** y **Hunter.io keys** para fuentes extra

## Quickstart

```bash
git clone https://github.com/dupinciber/webint.git
cd webint
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python3 dupin.py example.com --perfil rapido
```

La primera vez que necesita IA, el CLI te pide la key **sin mostrarla** y la
guarda localmente en:

```
~/.config/dupinciber/webint.env   (0600, fuera del repositorio)
```

También podés dársela vos con `DUPIN_AI_API_KEY` en tu entorno o en un `.env`
local (nunca se commitea). Para usar otro proveedor, cambiá su base URL y los
nombres de modelo (ver [`.env.example`](.env.example)):

```bash
export DUPIN_AI_BASE_URL=https://openrouter.ai/api/v1
export DUPIN_AI_MODEL_FLASH=openai/gpt-4o-mini
export DUPIN_AI_MODEL_PRO=anthropic/claude-3.5-sonnet
```

Perfiles: `rapido` (~3–5 min), `medio` (~6–9 min), `profundo` (~8–18 min).

## Configuración

Todo se configura en `.env` (ver [`.env.example`](.env.example)):

| Variable | Default | Descripción |
|---|---|---|
| `DUPIN_AI_API_KEY` | — | Key de IA (alternativa: entorno o pregunta del primer uso) |
| `DUPIN_AI_BASE_URL` | `https://api.deepseek.com` | Cualquier base URL compatible OpenAI |
| `DUPIN_AI_MODEL_FLASH` | `deepseek-v4-flash` | Modelo ejecutor (loop del agente) |
| `DUPIN_AI_MODEL_PRO` | `deepseek-v4-pro` | Modelo analista/reporte |
| `DUPIN_AI_REASONING_EFFORT` | auto | Esfuerzo de razonamiento (DeepSeek `high`; otros opt-in) |
| `DUPIN_INSECURE_TLS` | `0` | Desactiva verificación TLS (solo proveedores locales/self-signed) |
| `DUPIN_RPS` | perfil | Límite global de requests por segundo |
| `SHODAN_API_KEY` | — | Shodan key opcional |
| `HUNTER_API_KEY_1..N` | — | Hunter.io keys opcionales (round-robin) |
| `DUPIN_AUTONOMO` | `1` | Modo agente totalmente autónomo |
| `DUPIN_ANTILOOP` | `8` | Umbral de llamadas repetidas |
| `DUPIN_FORCE_CLOSE` | `0` | Activar cierre por falta de progreso |

## Salida

Cada investigación crea `reports/<target>_<timestamp>/`:

```
report.md          # reporte escrito (resumen ejecutivo + hallazgos)
findings.jsonl     # un finding JSON por línea (severidad, evidencia, módulo)
entities.json      # emails, personas, empresas + fuentes
entities.csv       # lo mismo, para planilla
assets.json        # activos descubiertos
run-log.jsonl      # cada paso del agente y llamada a herramienta
evidence/          # capturas de evidencia cruda
```

## Uso responsable

DUPIN WEBINT hace reconocimiento activo. **Usalo únicamente contra sistemas,
dominios y activos que sean tuyos o para los que tengas autorización escrita
explícita.** Usarlo contra terceros sin permiso puede ser ilegal en tu
jurisdicción. Sos el único responsable del uso que le des.

Ver [SECURITY.md](SECURITY.md) para reportar vulnerabilidades.

## Licencia

**Licencia DUPIN Source-Available (sin derivados).** Podés leer, ejecutar e
instalar DUPIN WEBINT gratis. **No** podés modificarlo ni redistribuir versiones
modificadas. El uso comercial requiere autorización escrita de DUPIN.

© 2026 [DUPIN Ciberseguridad](https://dupin.com.ar) — Buenos Aires, Argentina.

---

🇺🇸 [Read in English](README.md)
