# mini_av.py — Hardened, SOMENTE XML (NF-e)
import io, os, math, zipfile, tarfile
import yara
from defusedxml.ElementTree import fromstring as safe_xml_parse

try:
    import magic
except Exception:
    magic = None

ALLOWED_MIME = {"application/xml", "text/xml"}
MAX_SIZE = 10 * 1024 * 1024
MAX_ARCHIVE_FILES = 200
MAX_ARCHIVE_RATIO = 30.0
MAX_DEPTH = 3
YARA_RULES_PATH = "yara_rules/index.yar"  

# ---------- MIME com fallback ----------
def _mime_with_fallback(b: bytes) -> str:
    m = None
    if magic:
        try:
            m = magic.from_buffer(b, mime=True)
        except Exception:
            m = None
    if m:
        return m
    head = (b[:64] or b"").lstrip()
    if head.startswith(b"<?xml") or head.startswith(b"\xef\xbb\xbf<?xml"):
        return "application/xml"
    return "application/octet-stream"

def _is_pe_elf_macho(b: bytes) -> bool:
    sig2, sig4 = b[:2], b[:4]
    if sig2 == b"MZ": return True
    if sig4 == b"\x7fELF": return True
    if sig4 in (b"\xFE\xED\xFA\xCE", b"\xCE\xFA\xED\xFE", b"\xFE\xED\xFA\xCF", b"\xCF\xFA\xED\xFE",
                b"\xCA\xFE\xBA\xBE", b"\xBE\xBA\xFE\xCA"): return True
    return False

def _looks_script(b: bytes) -> bool:
    h = b[:256].lower()
    return h.startswith(b"#!") or b"<script" in h

def _entropy(b: bytes) -> float:
    if not b: return 0.0
    from collections import Counter
    n = len(b)
    return -sum((c/n)*math.log2(c/n) for c in Counter(b).values())

def _xml_safe(b: bytes):
    safe_xml_parse(b.decode("utf-8", "ignore"))

def _scan_archive(content: bytes, depth=0):
    if depth > MAX_DEPTH: raise ValueError("Profundidade excessiva")
    total = 0
    def chk(name: str):
        if ".." in name or name.startswith(("/", "\\")):
            raise ValueError("Caminho suspeito em compactado (zip-slip)")
    bio = io.BytesIO(content)
    if zipfile.is_zipfile(bio):
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            infos = zf.infolist()
            if len(infos) > MAX_ARCHIVE_FILES: raise ValueError("ZIP com arquivos demais")
            for zi in infos:
                chk(zi.filename)
                if zi.is_dir(): continue
                data = zf.read(zi); total += len(data)
                if zipfile.is_zipfile(io.BytesIO(data)) or tarfile.is_tarfile(io.BytesIO(data)):
                    _scan_archive(data, depth+1)
    elif tarfile.is_tarfile(io.BytesIO(content)):
        with tarfile.open(fileobj=io.BytesIO(content)) as tf:
            members = tf.getmembers()
            if len(members) > MAX_ARCHIVE_FILES: raise ValueError("TAR com arquivos demais")
            for m in members:
                chk(m.name)
                if not m.isfile(): continue
                fobj = tf.extractfile(m)
                if not fobj: continue
                data = fobj.read(); total += len(data)
                if zipfile.is_zipfile(io.BytesIO(data)) or tarfile.is_tarfile(io.BytesIO(data)):
                    _scan_archive(data, depth+1)
    ratio = (total / max(1, len(content)))
    if ratio > MAX_ARCHIVE_RATIO: raise ValueError(f"Taxa de expansão suspeita ({ratio:.1f}x)")

# ---------- YARA opcional ----------
try:
    YARA = yara.compile(filepath=YARA_RULES_PATH) if os.path.exists(YARA_RULES_PATH) else None
except Exception:
    YARA = None

def _yara(b: bytes):
    if not YARA: return []
    try:
        m = YARA.match(data=b, timeout=2)
        return [r.rule for r in m] if m else []
    except yara.TimeoutError:
        return ["YARA_TIMEOUT"]
    except Exception:
        return ["YARA_ENGINE_ERROR"]

def mini_av_scan_detalhado(filename: str, b: bytes) -> dict:
    steps, reasons = [], []
    score = 0
    mime = None

    # tamanho
    if len(b) > MAX_SIZE:
        return {"ok": False, "score": 100, "mime": None,
                "reasons": ["FILE_TOO_LARGE"],
                "steps": [{"name":"Tamanho","ok":False,"detail":"Arquivo acima do limite"}]}

    # MIME
    try:
        mime = _mime_with_fallback(b)
        steps.append({"name":"MIME sniff","ok":True,"detail":mime})
        if mime not in ALLOWED_MIME:
            reasons.append(f"MIME_NOT_ALLOWED:{mime}"); score += 50
    except Exception as e:
        steps.append({"name":"MIME sniff","ok":False,"detail":str(e)})
        reasons.append("MIME_ERROR"); score += 60

    # Validação 
    try:
        if mime in ALLOWED_MIME:
            _xml_safe(b)
            steps.append({"name":"XML seguro","ok":True,"detail":"Parse OK (defusedxml)"})
        else:
            steps.append({"name":"Tipo não previsto","ok":False,"detail":mime})
    except Exception as e:
        steps.append({"name":"Validação de formato","ok":False,"detail":type(e).__name__})
        reasons.append(f"FORMAT_INVALID:{type(e).__name__}"); score += 60


    bin_exec = _is_pe_elf_macho(b)
    script = _looks_script(b)
    steps.append({"name":"Executável/Scripts","ok": not (bin_exec or script),
                  "detail": ("BINARY_EXECUTABLE" if bin_exec else "") + (" SCRIPT_HEADER_OR_TAG" if script else "")})
    if bin_exec:
        reasons.append("BINARY_EXECUTABLE"); score = 100
    if script:
        reasons.append("SCRIPT_HEADER_OR_TAG"); score += 60

    # Compactados (bloqueio de zip-bomb disfarçado)
    try:
        _scan_archive(b); steps.append({"name":"Compactados","ok":True,"detail":"OK"})
    except Exception as e:
        steps.append({"name":"Compactados","ok":False,"detail":type(e).__name__})
        reasons.append(f"ARCHIVE_SUSPECT:{type(e).__name__}"); score += 80

    # Entropia (apenas XML)
    if mime in ALLOWED_MIME:
        H = _entropy(b[:65536]); high = H > 7.0
        steps.append({"name":"Entropia","ok": not high,"detail": f"H={H:.2f}"})
        if high: reasons.append("HIGH_ENTROPY"); score += 20
    else:
        steps.append({"name":"Entropia","ok":True,"detail":"não aplicável"})

    # YARA
    try:
        hits = _yara(b)
        strong = [h for h in hits if h not in ("YARA_TIMEOUT","YARA_ENGINE_ERROR")]
        if strong:
            steps.append({"name":"YARA","ok":False,"detail":", ".join(strong)})
            reasons.append("YARA_MATCH:" + ",".join(strong))
            score += 80
        elif hits:
            steps.append({"name":"YARA","ok":False,"detail":", ".join(hits)})
            reasons.extend(hits)
        else:
            steps.append({"name":"YARA","ok":True,"detail":"sem matches"})
    except Exception as e:
        steps.append({"name":"YARA","ok":False,"detail":f"erro: {e}"})
        reasons.append("YARA_ERROR")

    ok = score < 80 and "BINARY_EXECUTABLE" not in reasons
    return {"ok": ok, "score": min(score,100), "mime": mime, "reasons": reasons, "steps": steps}
