"""Ejecucion de comandos y HTTP directo desde el host.

Todo el trafico sale directo por la interfaz del host. HTTP con requests.Session
(keep-alive, TLS verificado por defecto); comandos y DNS via subprocess directo.
"""
import json
import os
import subprocess
import threading
import time

import requests

try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass

_session_direct = None
_session_lock = threading.Lock()

# DNS cache (memoria + disco)
_DNS_CACHE = {}
_dns_lock = threading.Lock()


def tls_verify():
    """Verificacion TLS ON por defecto; DUPIN_INSECURE_TLS=1 la desactiva
    (solo para proveedores locales con certificado self-signed)."""
    return os.getenv("DUPIN_INSECURE_TLS", "0").lower() not in ("1", "true", "yes")


def _direct_session():
    """Session con keep-alive para llamadas directas. Reusa TLS."""
    global _session_direct
    if _session_direct is None:
        with _session_lock:
            if _session_direct is None:
                s = requests.Session()
                s.headers.update({"User-Agent": "dupin/2.0"})
                _session_direct = s
    return _session_direct


# ---------------- comandos ----------------

def run_cmd(cmd, timeout=60):
    """Corre un comando (lista de args) directo desde el host."""
    try:
        p = subprocess.run(list(cmd), capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except FileNotFoundError:
        return 127, "", "binario no encontrado"


def run_cmd_stream(cmd, timeout=300, idle_timeout=90, on_line=None):
    """Corre un comando streameando lineas. Si no hay output en idle_timeout
    segundos, mata el proceso y devuelve lo acumulado. on_line(line) opcional."""
    import select
    try:
        p = subprocess.Popen(list(cmd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, bufsize=1)
    except FileNotFoundError:
        return 127, "", "binario no encontrado"
    out_lines = []
    t0 = time.time()
    last = t0
    try:
        fd = p.stdout.fileno()
        while True:
            r, _, _ = select.select([fd], [], [], 1.0)
            now = time.time()
            if r:
                line = p.stdout.readline()
                if not line:
                    break
                last = now
                line = line.rstrip("\n")
                out_lines.append(line)
                if on_line:
                    try:
                        on_line(line)
                    except Exception:
                        pass
                continue
            if p.poll() is not None:
                break
            if (now - t0) > timeout:
                p.kill()
                out_lines.append(f"[!] TIMEOUT global ({timeout}s) — proceso cortado")
                break
            if (now - last) > idle_timeout:
                p.kill()
                out_lines.append(f"[!] Sin output en {idle_timeout}s — seguí con otra técnica")
                break
        try:
            p.wait(timeout=3)
        except Exception:
            p.kill()
    finally:
        rc = p.returncode if p.returncode is not None else 124
    return rc, "\n".join(out_lines), ""


# ---------------- DNS ----------------

def _dns_cache_path():
    from . import config
    return config.BASE_DIR / "cache" / "dns.json"


def _dns_cache_get(key, ttl=3600):
    with _dns_lock:
        if key in _DNS_CACHE:
            ts, vals = _DNS_CACHE[key]
            if time.time() - ts < ttl:
                return vals
    try:
        p = _dns_cache_path()
        if p.exists():
            data = json.loads(p.read_text())
            if key in data and time.time() - data[key]["ts"] < ttl:
                with _dns_lock:
                    _DNS_CACHE[key] = (data[key]["ts"], data[key]["vals"])
                return data[key]["vals"]
    except Exception:
        pass
    return None


def _dns_cache_put(key, vals):
    with _dns_lock:
        _DNS_CACHE[key] = (time.time(), vals)
    try:
        p = _dns_cache_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        if p.exists():
            data = json.loads(p.read_text())
        data[key] = {"ts": time.time(), "vals": vals}
        p.write_text(json.dumps(data))
    except Exception:
        pass


def resolve(host, rtype="A", timeout=15):
    """Resuelve un host. Usa cache (TTL 1h). Devuelve lista de respuestas cortas."""
    host = host.rstrip(".").lower()
    cached = _dns_cache_get(f"{rtype}:{host}")
    if cached is not None:
        return cached
    rc, out, err = run_cmd(["dig", "+short", rtype, host], timeout=timeout)
    vals = [l.strip() for l in out.splitlines() if l.strip() and not l.strip().startswith(";")]
    if rc == 0:
        _dns_cache_put(f"{rtype}:{host}", vals)
    return vals


def resolve_full(host, rtype="A", timeout=20):
    """Resuelve sin +short (para TXT multilinea). Devuelve stdout crudo."""
    rc, out, err = run_cmd(["dig", rtype, host], timeout=timeout)
    return out


def resolve_many(hosts, rtype="A", workers=24, timeout=90):
    """Resuelve una lista de hosts en paralelo. Devuelve dict host->[vals].
    rtype=A/AAAA usa getaddrinfo en 1 subprocess; otros tipos (TXT/MX/CNAME)
    usan dig en hilos."""
    hosts = [h for h in hosts if h]
    out = {}
    missing = []
    for h in hosts:
        cached = _dns_cache_get(f"{rtype}:{h.rstrip('.').lower()}")
        if cached is not None:
            out[h] = cached
        else:
            missing.append(h)
    if not missing:
        return out
    if rtype not in ("A", "AAAA"):
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def dig_one(h):
            rc, o, e = run_cmd(["dig", "+short", rtype, h], timeout=8)
            vals = [l.strip() for l in o.splitlines() if l.strip() and not l.strip().startswith(";")]
            return h, vals

        with ThreadPoolExecutor(max_workers=max(1, min(workers, len(missing)))) as ex:
            futs = [ex.submit(dig_one, h) for h in missing]
            for f in as_completed(futs):
                try:
                    h, vals = f.result()
                    out[h] = vals
                except Exception:
                    pass
        for h, vals in out.items():
            _dns_cache_put(f"{rtype}:{h.rstrip('.').lower()}", vals)
        return out
    script = r'''
import json, socket, sys
from concurrent.futures import ThreadPoolExecutor
hosts = json.loads(sys.stdin.read() or "[]")
def r(h):
    try:
        socket.setdefaulttimeout(4)
        return sorted({i[4][0] for i in socket.getaddrinfo(h, None)})
    except Exception:
        return []
with ThreadPoolExecutor(max_workers=32) as ex:
    res = dict(zip(hosts, ex.map(r, hosts)))
print(json.dumps(res))
'''
    try:
        p = subprocess.run(["python3", "-c", script], input=json.dumps(missing),
                           capture_output=True, text=True, timeout=timeout)
        data = json.loads(p.stdout or "{}")
    except Exception:
        data = {}
    for h, ips in data.items():
        out[h] = ips
        _dns_cache_put(f"{rtype}:{h.rstrip('.').lower()}", ips)
    return out


# ---------------- HTTP ----------------

def _norm_reqs(reqs):
    """Asegura formato id/method/url/headers/body/timeout."""
    out = []
    for i, r in enumerate(reqs):
        out.append({
            "id": r.get("id", i),
            "method": (r.get("method") or "GET").upper(),
            "url": r["url"],
            "headers": r.get("headers") or {},
            "body": r.get("body"),
            "timeout": float(r.get("timeout") or 10),
        })
    return out


def batch_http(reqs, workers=14, rps=None, timeout=120):
    """Corre una lista de requests HTTP en paralelo, directo desde el host."""
    reqs = _norm_reqs(reqs)
    if not reqs:
        return []
    return _batch_direct(reqs, workers=workers, rps=rps)


def _batch_direct(reqs, workers=14, rps=None):
    """Batch directo: Session del host con keep-alive."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    sess = _direct_session()
    rlock = threading.Lock()
    rlast = [0.0]

    def wait_rate():
        if not rps:
            return
        min_gap = 1.0 / rps
        with rlock:
            now = time.time()
            gap = min_gap - (now - rlast[0])
            if gap > 0:
                time.sleep(gap)
                now = time.time()
            rlast[0] = now

    def one(req):
        try:
            wait_rate()
            t = req.get("timeout") or 10
            if req["method"] == "POST":
                r = sess.post(req["url"], data=req.get("body"), headers=req["headers"],
                              timeout=t, verify=tls_verify())
            elif req["method"] == "HEAD":
                r = sess.head(req["url"], headers=req["headers"], timeout=t,
                              verify=tls_verify(), allow_redirects=True)
            else:
                r = sess.get(req["url"], headers=req["headers"], timeout=t,
                             verify=tls_verify(), allow_redirects=True)
            return {"id": req["id"], "status": r.status_code, "headers": dict(r.headers),
                    "body": r.text[:16384]}
        except Exception as e:
            return {"id": req["id"], "status": 0, "headers": {}, "body": "",
                    "err": str(e)[:200]}

    out = [None] * len(reqs)
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(reqs)))) as ex:
        futs = {ex.submit(one, r): i for i, r in enumerate(reqs)}
        for f in as_completed(futs):
            out[futs[f]] = f.result()
    return out


def http_get(url, timeout=15, headers=None, follow=True):
    """GET HTTP directo. Devuelve (status, headers_dict, body)."""
    try:
        r = _direct_session().get(url, headers=headers, timeout=timeout,
                                  verify=tls_verify(), allow_redirects=follow)
        return r.status_code, dict(r.headers), r.text
    except Exception:
        return 0, {}, ""


def http_post(url, data=None, headers=None, timeout=15):
    """POST HTTP directo."""
    try:
        r = _direct_session().post(url, data=data, headers=headers, timeout=timeout,
                                   verify=tls_verify())
        return r.status_code, dict(r.headers), r.text
    except Exception:
        return 0, {}, ""


def http_head(url, timeout=10):
    try:
        r = _direct_session().head(url, timeout=timeout, verify=tls_verify(),
                                   allow_redirects=True)
        return r.status_code, dict(r.headers), ""
    except Exception:
        return 0, {}, ""


def http_get_json(url, timeout=15, headers=None):
    """GET y parsea JSON. Devuelve (status, data_or_None, raw_body)."""
    st, h, body = http_get(url, timeout=timeout, headers=headers)
    try:
        return st, json.loads(body), body
    except Exception:
        return st, None, body
