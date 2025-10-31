# extrair.py — XML NF-e (seguro, sem PDFs)
from __future__ import annotations

from defusedxml import ElementTree as ET
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

# Validador unificado de IE (usa regras Sintegra por UF)
# espere um módulo validadores/__init__.py expondo `valida_ie(uf, ie)`
from validadores import valida_ie


# ==========================
# Helpers de string / números
# ==========================
def only_digits(s: Optional[str]) -> str:
    if not s:
        return ""
    return "".join(ch for ch in s if ch.isdigit())


def to_decimal(s: Optional[str]) -> Optional[Decimal]:
    if s is None:
        return None
    s = s.strip()
    if not s:
        return None
    try:
        # Normaliza vírgula para ponto, se vier em alguns layouts
        s = s.replace(",", ".")
        return Decimal(s)
    except InvalidOperation:
        return None


def text(el: Optional[ET.Element], default: str = "") -> str:
    return (el.text or "").strip() if (el is not None and el.text) else default


# =================================
# Navegação por local-name (sem NS)
# =================================
def localname(tag: str) -> str:
    # "{ns}Tag" -> "Tag"
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def child(el: ET.Element, name: str) -> Optional[ET.Element]:
    """Filho imediato com local-name == name (ignorando namespace)."""
    for c in el:
        if localname(c.tag) == name:
            return c
    return None


def children(el: ET.Element, name: str) -> List[ET.Element]:
    """Lista de filhos imediatos com local-name == name."""
    return [c for c in el if localname(c.tag) == name]


def find_first(el: ET.Element, *names: str) -> Optional[ET.Element]:
    """Procura recursivamente pelo primeiro nó cujo local-name case com 'names' na ordem."""
    if not names:
        return el
    name0, *rest = names
    for node in el.iter():
        if localname(node.tag) == name0:
            if not rest:
                return node
            # desce usando sequência restante a partir desse node
            return _descend(node, rest)
    return None


def _descend(root: ET.Element, names_rest: List[str]) -> Optional[ET.Element]:
    cur = root
    for nm in names_rest:
        cur = child(cur, nm) if cur is not None else None
        if cur is None:
            return None
    return cur


# ==========================
# Validações (CNPJ / Chave)
# ==========================
def valida_cnpj(cnpj: str) -> bool:
    """Validação canônica de CNPJ (14 dígitos, 2 DV)."""
    c = only_digits(cnpj)
    if len(c) != 14 or len(set(c)) == 1:
        return False

    def calc_dv(nums: str) -> str:
        pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        pesos2 = [6] + pesos1
        soma1 = sum(int(d) * pesos1[i] for i, d in enumerate(nums[:12]))
        r1 = soma1 % 11
        dv1 = 0 if r1 < 2 else 11 - r1
        soma2 = sum(int(d) * pesos2[i] for i, d in enumerate(nums[:12] + str(dv1)))
        r2 = soma2 % 11
        dv2 = 0 if r2 < 2 else 11 - r2
        return f"{dv1}{dv2}"

    return c[-2:] == calc_dv(c)


def valida_chave_acesso(chave: str) -> bool:
    """Validação da chave de acesso (44 dígitos; DV mod 11)."""
    c = only_digits(chave)
    if len(c) != 44:
        return False
    # DV: pesos 2..9 à direita
    pesos = [2, 3, 4, 5, 6, 7, 8, 9]
    soma = 0
    for i, d in enumerate(reversed(c[:-1])):
        soma += int(d) * pesos[i % 8]
    dv = 11 - (soma % 11)
    if dv >= 10:
        dv = 0
    return dv == int(c[-1])


# ==========================
# Parsing principal
# ==========================
def _find_infNFe(root: ET.Element) -> Optional[ET.Element]:
    """
    Tenta localizar o nó <infNFe> independentemente de estar dentro de <nfeProc> ou diretamente em <NFe>.
    """
    # Cenário comum: nfeProc/ NFe / infNFe
    nfe_proc = find_first(root, "nfeProc")
    if nfe_proc is not None:
        nfe = child(nfe_proc, "NFe")
        if nfe is not None:
            inf = child(nfe, "infNFe")
            if inf is not None:
                return inf

    # Cenário: NFe / infNFe
    nfe = find_first(root, "NFe")
    if nfe is not None:
        inf = child(nfe, "infNFe")
        if inf is not None:
            return inf

    # fallback: procurar em qualquer lugar pelo primeiro infNFe
    return find_first(root, "infNFe")


def _parse_ide(inf: ET.Element) -> Dict[str, Any]:
    ide = child(inf, "ide")
    if ide is None:
        return {}
    return {
        "cUF":     text(child(ide, "cUF")),
        "cNF":     text(child(ide, "cNF")),
        "natOp":   text(child(ide, "natOp")),
        "mod":     text(child(ide, "mod")),     # modelo
        "serie":   text(child(ide, "serie")),
        "nNF":     text(child(ide, "nNF")),
        "dhEmi":   text(child(ide, "dhEmi") or child(ide, "dEmi")),
        "tpNF":    text(child(ide, "tpNF")),
        "idDest":  text(child(ide, "idDest")),
        "cMunFG":  text(child(ide, "cMunFG")),
        "tpImp":   text(child(ide, "tpImp")),
        "tpEmis":  text(child(ide, "tpEmis")),
        "cDV":     text(child(ide, "cDV")),
        "tpAmb":   text(child(ide, "tpAmb")),
        "finNFe":  text(child(ide, "finNFe")),
        "indFinal":text(child(ide, "indFinal")),
        "indPres": text(child(ide, "indPres")),
        "procEmi": text(child(ide, "procEmi")),
        "verProc": text(child(ide, "verProc")),
    }


def _parse_endereco(el: Optional[ET.Element]) -> Dict[str, Any]:
    if el is None:
        return {}
    return {
        "xLgr":   text(child(el, "xLgr")),
        "nro":    text(child(el, "nro")),
        "xCpl":   text(child(el, "xCpl")),
        "xBairro":text(child(el, "xBairro")),
        "cMun":   text(child(el, "cMun")),
        "xMun":   text(child(el, "xMun")),
        "UF":     text(child(el, "UF")),
        "CEP":    text(child(el, "CEP")),
        "cPais":  text(child(el, "cPais")),
        "xPais":  text(child(el, "xPais")),
        "fone":   text(child(el, "fone")),
    }


def _parse_emit(inf: ET.Element) -> Dict[str, Any]:
    el = child(inf, "emit")
    if el is None:
        return {}
    doc = only_digits(text(child(el, "CNPJ")))
    if not doc:
        doc = only_digits(text(child(el, "CPF")))
    return {
        "CNPJ": doc if len(doc) == 14 else "",
        "CPF":  doc if len(doc) == 11 else "",
        "xNome": text(child(el, "xNome")),
        "xFant": text(child(el, "xFant")),
        "IE":    text(child(el, "IE")),
        "IEST":  text(child(el, "IEST")),  # Substituto Tributário
        "IM":    text(child(el, "IM")),
        "CNAE":  text(child(el, "CNAE")),
        "CRT":   text(child(el, "CRT")),
        "enderEmit": _parse_endereco(child(el, "enderEmit")),
    }


def _parse_dest(inf: ET.Element) -> Dict[str, Any]:
    el = child(inf, "dest")
    if el is None:
        return {}
    cnpj = only_digits(text(child(el, "CNPJ")))
    cpf  = only_digits(text(child(el, "CPF")))
    return {
        "CNPJ": cnpj if len(cnpj) == 14 else "",
        "CPF":  cpf if len(cpf) == 11 else "",
        "xNome": text(child(el, "xNome")),
        "IE":    text(child(el, "IE")),
        "IEST":  text(child(el, "IEST")),  # se presente em alguns layouts
        "indIEDest": text(child(el, "indIEDest")),
        "ISUF":  text(child(el, "ISUF")),
        "email": text(child(el, "email")),
        "enderDest": _parse_endereco(child(el, "enderDest")),
    }


def _parse_icms(el_imposto: ET.Element) -> Dict[str, Any]:
    icms = child(el_imposto, "ICMS")
    if icms is None:
        return {}
    # Dentro de <ICMS> sempre vem um sub-nó: ICMS00, ICMS20, ICMS40, ICMS60, ICMS90, ICMS10, ICMSPart, ICMSST, etc.
    sub = None
    for c in icms:
        sub = c
        break
    out = {}
    if sub is not None:
        out["orig"] = text(child(sub, "orig"))
        # CST (regime normal) ou CSOSN (Simples)
        cst = text(child(sub, "CST"))
        csosn = text(child(sub, "CSOSN"))
        if cst:
            out["CST"] = cst
        if csosn:
            out["CSOSN"] = csosn
        # Base e valores
        out["modBC"]   = text(child(sub, "modBC"))
        out["vBC"]     = to_decimal(text(child(sub, "vBC")) or None)
        out["pICMS"]   = to_decimal(text(child(sub, "pICMS")) or None)
        out["vICMS"]   = to_decimal(text(child(sub, "vICMS")) or None)
        out["vBCST"]   = to_decimal(text(child(sub, "vBCST")) or None)
        out["pICMSST"] = to_decimal(text(child(sub, "pICMSST")) or None)
        out["vICMSST"] = to_decimal(text(child(sub, "vICMSST")) or None)
        out["pRedBC"]  = to_decimal(text(child(sub, "pRedBC")) or None)
    return {k: v for k, v in out.items() if v not in ("", None)}


def _parse_ipi(el_imposto: ET.Element) -> Dict[str, Any]:
    ipi = child(el_imposto, "IPI")
    if ipi is None:
        return {}
    out = {
        "cEnq": text(child(ipi, "cEnq")),
    }
    # IPITrib ou IPINT
    trib = child(ipi, "IPITrib")
    if trib is not None:
        out.update({
            "CST":  text(child(trib, "CST")),
            "vBC":  to_decimal(text(child(trib, "vBC")) or None),
            "pIPI": to_decimal(text(child(trib, "pIPI")) or None),
            "vIPI": to_decimal(text(child(trib, "vIPI")) or None),
        })
    else:
        ipint = child(ipi, "IPINT")
        if ipint is not None:
            out["CST"] = text(child(ipint, "CST"))
    return {k: v for k, v in out.items() if v not in ("", None)}


def _parse_pis(el_imposto: ET.Element) -> Dict[str, Any]:
    pis = child(el_imposto, "PIS")
    if pis is None:
        return {}
    # Pode ser PISAliq, PISQtde, PISNT, PISOutr
    for tag in ("PISAliq", "PISQtde", "PISNT", "PISOutr"):
        node = child(pis, tag)
        if node is not None:
            out = {"tipo": tag, "CST": text(child(node, "CST"))}
            # campos possíveis
            out["vBC"]   = to_decimal(text(child(node, "vBC")) or None)
            out["pPIS"]  = to_decimal(text(child(node, "pPIS")) or None)
            out["vPIS"]  = to_decimal(text(child(node, "vPIS")) or None)
            out["qBCProd"] = to_decimal(text(child(node, "qBCProd")) or None)
            out["vAliqProd"] = to_decimal(text(child(node, "vAliqProd")) or None)
            return {k: v for k, v in out.items() if v not in ("", None)}
    return {}


def _parse_cofins(el_imposto: ET.Element) -> Dict[str, Any]:
    cofins = child(el_imposto, "COFINS")
    if cofins is None:
        return {}
    for tag in ("COFINSAliq", "COFINSQtde", "COFINSNT", "COFINSOutr"):
        node = child(cofins, tag)
        if node is not None:
            out = {"tipo": tag, "CST": text(child(node, "CST"))}
            out["vBC"]   = to_decimal(text(child(node, "vBC")) or None)
            out["pCOFINS"]  = to_decimal(text(child(node, "pCOFINS")) or None)
            out["vCOFINS"]  = to_decimal(text(child(node, "vCOFINS")) or None)
            out["qBCProd"]  = to_decimal(text(child(node, "qBCProd")) or None)
            out["vAliqProd"] = to_decimal(text(child(node, "vAliqProd")) or None)
            return {k: v for k, v in out.items() if v not in ("", None)}
    return {}


def _parse_impostos(el_imposto: Optional[ET.Element]) -> Dict[str, Any]:
    if el_imposto is None:
        return {}
    out = {
        "ICMS": _parse_icms(el_imposto),
        "IPI":  _parse_ipi(el_imposto),
        "PIS":  _parse_pis(el_imposto),
        "COFINS": _parse_cofins(el_imposto),
    }
    return {k: v for k, v in out.items() if v}


def _parse_det_items(inf: ET.Element) -> List[Dict[str, Any]]:
    items = []
    for det in children(inf, "det"):
        prod = child(det, "prod")
        imposto = child(det, "imposto")

        item: Dict[str, Any] = {
            "nItem": (det.get("nItem") or "").strip(),
            "prod": {},
            "imposto": {},
        }

        if prod is not None:
            item["prod"] = {
                "cProd":   text(child(prod, "cProd")),
                "cEAN":    text(child(prod, "cEAN")),
                "xProd":   text(child(prod, "xProd")),
                "NCM":     text(child(prod, "NCM")),
                "CEST":    text(child(prod, "CEST")),
                "CFOP":    text(child(prod, "CFOP")),
                "uCom":    text(child(prod, "uCom")),
                "qCom":    to_decimal(text(child(prod, "qCom")) or None),
                "vUnCom":  to_decimal(text(child(prod, "vUnCom")) or None),
                "vProd":   to_decimal(text(child(prod, "vProd")) or None),
                "uTrib":   text(child(prod, "uTrib")),
                "qTrib":   to_decimal(text(child(prod, "qTrib")) or None),
                "vUnTrib": to_decimal(text(child(prod, "vUnTrib")) or None),
                "indTot":  text(child(prod, "indTot")),
                "xPed":    text(child(prod, "xPed")),
                "nItemPed":text(child(prod, "nItemPed")),
            }
            # remove None/""
            item["prod"] = {k: v for k, v in item["prod"].items() if v not in ("", None)}

        item["imposto"] = _parse_impostos(imposto)
        if not item["imposto"]:
            del item["imposto"]

        items.append(item)
    return items


def _parse_totais(inf: ET.Element) -> Dict[str, Any]:
    total = child(inf, "total")
    if total is None:
        return {}
    icms_tot = child(total, "ICMSTot")
    if icms_tot is None:
        return {}
    out = {
        "vBC":       to_decimal(text(child(icms_tot, "vBC")) or None),
        "vICMS":     to_decimal(text(child(icms_tot, "vICMS")) or None),
        "vICMSDeson":to_decimal(text(child(icms_tot, "vICMSDeson")) or None),
        "vFCP":      to_decimal(text(child(icms_tot, "vFCP")) or None),
        "vBCST":     to_decimal(text(child(icms_tot, "vBCST")) or None),
        "vST":       to_decimal(text(child(icms_tot, "vST")) or None),
        "vFCPST":    to_decimal(text(child(icms_tot, "vFCPST")) or None),
        "vFCPSTRet": to_decimal(text(child(icms_tot, "vFCPSTRet")) or None),
        "vProd":     to_decimal(text(child(icms_tot, "vProd")) or None),
        "vFrete":    to_decimal(text(child(icms_tot, "vFrete")) or None),
        "vSeg":      to_decimal(text(child(icms_tot, "vSeg")) or None),
        "vDesc":     to_decimal(text(child(icms_tot, "vDesc")) or None),
        "vII":       to_decimal(text(child(icms_tot, "vII")) or None),
        "vIPI":      to_decimal(text(child(icms_tot, "vIPI")) or None),
        "vIPIDevol": to_decimal(text(child(icms_tot, "vIPIDevol")) or None),
        "vPIS":      to_decimal(text(child(icms_tot, "vPIS")) or None),
        "vCOFINS":   to_decimal(text(child(icms_tot, "vCOFINS")) or None),
        "vOutro":    to_decimal(text(child(icms_tot, "vOutro")) or None),
        "vNF":       to_decimal(text(child(icms_tot, "vNF")) or None),
        "vTotTrib":  to_decimal(text(child(icms_tot, "vTotTrib")) or None),
    }
    return {k: v for k, v in out.items() if v is not None}


def _parse_protocolo(root: ET.Element) -> Dict[str, Any]:
    """Tenta capturar nProt, dhRecbto etc. quando existir <protNFe>."""
    prot = find_first(root, "protNFe")
    if prot is None:
        return {}
    infp = child(prot, "infProt")
    if infp is None:
        return {}
    return {
        "tpAmb":  text(child(infp, "tpAmb")),
        "verAplic": text(child(infp, "verAplic")),
        "chNFe": text(child(infp, "chNFe")),
        "dhRecbto": text(child(infp, "dhRecbto")),
        "nProt": text(child(infp, "nProt")),
        "digVal": text(child(infp, "digVal")),
        "cStat": text(child(infp, "cStat")),
        "xMotivo": text(child(infp, "xMotivo")),
    }


# ==========================================
# API principal: extrair de XML de NF-e
# ==========================================
def extract_from_nfe_xml(xml_bytes: bytes) -> Dict[str, Any]:
    """
    Extrai campos relevantes de uma NF-e (XML) ignorando namespaces.
    Retorna um dicionário estruturado e JSON-friendly após aplicar to_jsonable no chamador.
    """
    # Parse seguro (defusedxml)
    try:
        root = ET.fromstring(xml_bytes)
    except Exception as e:
        raise ValueError(f"XML inválido: {e}")

    inf = _find_infNFe(root)
    if inf is None:
        raise ValueError("Não foi possível localizar <infNFe>.")

    # Chave de acesso (vem em @Id = 'NFe{44d}')
    chave = ""
    inf_id = (inf.get("Id") or "").strip()
    if inf_id.upper().startswith("NFE"):
        chave = only_digits(inf_id[3:])
    else:
        # às vezes vem em outras tags também
        ide = child(inf, "ide")
        if ide is not None:
            # Não é a chave oficial, mas mantém retrocompatibilidade de busca
            chave = only_digits(text(child(ide, "cNF")))

    out: Dict[str, Any] = {
        "chave_acesso": chave if len(chave) == 44 else "",
        "ide":   _parse_ide(inf),
        "emit":  _parse_emit(inf),
        "dest":  _parse_dest(inf),
        "itens": _parse_det_items(inf),
        "totais": _parse_totais(inf),
        "protocolo": _parse_protocolo(root),
        "modelo": text(child(child(inf, "ide") or ET.Element("x"), "mod")),  # redundante, ajuda no resumo
    }

    # ==========================
    # Validações automáticas de IE por UF (emitente/destinatário)
    # ==========================
    try:
        emit_uf  = (out.get("emit", {}).get("enderEmit", {}) or {}).get("UF", "")
        dest_uf  = (out.get("dest", {}).get("enderDest", {}) or {}).get("UF", "")
        emit_ie  = (out.get("emit", {}) or {}).get("IE", "")
        dest_ie  = (out.get("dest", {}) or {}).get("IE", "")

        out["validacoes"] = {
            "IE_emit": valida_ie(emit_uf, emit_ie),
            "IE_dest": valida_ie(dest_uf, dest_ie),
        }
    except Exception as e:
        # Mantém robustez: se algo der errado, não quebra a extração
        out["validacoes"] = {"erro_ie": f"Falha ao validar IE: {e}"}

    return out


# ==========================
# Serialização JSON-friendly
# ==========================
def _jsonable(v: Any) -> Any:
    if isinstance(v, Decimal):
        # Preserva exato (sem notação científica)
        return format(v, 'f')
    if isinstance(v, dict):
        return {k: _jsonable(val) for k, val in v.items()}
    if isinstance(v, list):
        return [_jsonable(x) for x in v]
    return v


def to_jsonable(obj: Any) -> Any:
    """Converte recursivamente Decimals em strings (e deixa o restante como está)."""
    return _jsonable(obj)
