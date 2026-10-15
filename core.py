"""Regras e geração dos comandos SABRE de emissão parcelada (portado da planilha)."""
from __future__ import annotations
import re
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Optional

# Companhia -> (código IATA usado no comando, parcelas pré-definidas sem juros)
CIAS = {"TAP": ("TP", 10), "AZUL": ("AD", 10), "LATAM": ("JJ", 4)}
# Bandeira -> (código SABRE, dígitos do cartão, dígitos do código de segurança)
BANDEIRAS = {"Mastercard": ("CA", 16, 3), "Visa": ("VI", 16, 3), "Amex": ("AX", 15, 4)}
PASSAGEIROS = [str(i) for i in range(1, 10)]
LINK_FINANCIAMENTOS = "https://www.elitravel.com.br/financiamentos.php"

OK = "OK"
CAMPOS_ETAPA1 = ["cia", "bandeira", "cartao", "cvv", "tarifa", "taxa", "pax"]
CAMPOS_ETAPA2 = ["autorizacao"]


def _s(v) -> str:
    return "" if v is None else str(v).strip()


def parse_valor(txt) -> Optional[Decimal]:
    """Aceita '1111,11', '1111.11' ou '1.111,11'. None se inválido."""
    t = _s(txt).replace(" ", "")
    if not t:
        return None
    if re.fullmatch(r"\d{1,3}(\.\d{3})+(,\d+)?", t):
        t = t.replace(".", "").replace(",", ".")
    else:
        t = t.replace(",", ".")
    if not re.fullmatch(r"\d+(\.\d+)?|\.\d+", t):
        return None
    try:
        return Decimal(t)
    except InvalidOperation:
        return None


def digitos(v) -> str:
    """Remove espaços e hífens (cartão digitado com separadores)."""
    return re.sub(r"[\s-]", "", _s(v))


# ---------- validações ----------
def valida_cia(v):
    return "Selecione a companhia" if not _s(v) else (OK if v in CIAS else "Companhia inválida")


def valida_bandeira(v):
    return "Selecione a bandeira" if not _s(v) else (OK if v in BANDEIRAS else "Bandeira inválida")


def valida_cartao(v, bandeira=None):
    n = digitos(v)
    if not n:
        return "Insira o número do cartão"
    if not n.isdigit():
        return "Somente números"
    if bandeira not in BANDEIRAS:
        return "Selecione a bandeira"
    qt = BANDEIRAS[bandeira][1]
    return OK if len(n) == qt else f"Deve ter {qt} dígitos ({len(n)} informados)"


def valida_cvv(v, bandeira=None):
    n = _s(v)
    if not n:
        return "Insira o código de segurança"
    if not n.isdigit():
        return "Somente números"
    if bandeira not in BANDEIRAS:
        return "Selecione a bandeira"
    qt = BANDEIRAS[bandeira][2]
    return OK if len(n) == qt else f"Deve ter {qt} dígitos"


def _valida_dinheiro(v, nome):
    if not _s(v):
        return f"Insira {nome}"
    n = parse_valor(v)
    if n is None or n <= 0:
        return "Informe um valor maior que zero"
    return OK


def valida_tarifa(v): return _valida_dinheiro(v, "a tarifa")
def valida_taxa(v): return _valida_dinheiro(v, "a taxa")


def valida_pax(v):
    return "Selecione a quantidade" if not _s(v) else (OK if _s(v) in PASSAGEIROS else "Use de 1 a 9")


def valida_autorizacao(v):
    n = _s(v)
    if not n:
        return "Insira o número da autorização"
    return OK if n.isdigit() else "Somente números"


def validar(d: dict) -> dict:
    b = d.get("bandeira")
    return {
        "cia": valida_cia(d.get("cia")),
        "bandeira": valida_bandeira(b),
        "cartao": valida_cartao(d.get("cartao"), b),
        "cvv": valida_cvv(d.get("cvv"), b),
        "tarifa": valida_tarifa(d.get("tarifa")),
        "taxa": valida_taxa(d.get("taxa")),
        "pax": valida_pax(d.get("pax")),
        "autorizacao": valida_autorizacao(d.get("autorizacao")),
    }


def etapa1_ok(d: dict) -> bool:
    st = validar(d)
    return all(st[k] == OK for k in CAMPOS_ETAPA1)


def etapa2_ok(d: dict) -> bool:
    st = validar(d)
    return etapa1_ok(d) and all(st[k] == OK for k in CAMPOS_ETAPA2)


# ---------- cálculos (mesmas fórmulas da planilha) ----------
def parcelas_da_cia(cia) -> Optional[int]:
    return CIAS[cia][1] if cia in CIAS else None


def _arred(x: Decimal, casas: int) -> Decimal:
    """Arredondamento do Excel (meio para cima), ignorando ruído de ponto flutuante."""
    x = x.quantize(Decimal("1e-10"), rounding=ROUND_HALF_UP)
    return x.quantize(Decimal(1).scaleb(-casas), rounding=ROUND_HALF_UP)


def calcular(d: dict) -> Optional[dict]:
    """total individual, valor da parcela e valor residual; None se faltar dado."""
    tarifa, taxa = parse_valor(d.get("tarifa")), parse_valor(d.get("taxa"))
    n, pax = parcelas_da_cia(d.get("cia")), _s(d.get("pax"))
    if tarifa is None or taxa is None or n is None or pax not in PASSAGEIROS:
        return None
    pax = Decimal(pax)
    total = (tarifa + taxa) * pax            # B7
    parcela = tarifa / Decimal(n) * pax      # B12
    residual = tarifa - (parcela / pax)      # B13
    return {"total": total, "parcela": parcela, "residual": residual, "n": n}


def fmt2(x: Decimal) -> str:
    return f"{_arred(x, 2):f}"  # 2 casas, ponto decimal


def fmt_br(x: Decimal) -> str:
    return fmt2(x).replace(".", ",")


# ---------- comandos ----------
def comando_autorizacao(d: dict) -> str:
    """Etapa 1: CK*<bandeira><cartão>/<cvv>/BRL<total>/<cia>"""
    if not etapa1_ok(d):
        return ""
    c = calcular(d)
    cod_cia, cod_band = CIAS[d["cia"]][0], BANDEIRAS[d["bandeira"]][0]
    return f"CK*{cod_band}{digitos(d['cartao'])}/{_s(d['cvv'])}/BRL{fmt2(c['total'])}/{cod_cia}"


def comando_emissao(d: dict) -> str:
    """Etapa 2: precisa da autorização."""
    if not etapa2_ok(d):
        return ""
    c = calcular(d)
    cod_cia, cod_band = CIAS[d["cia"]][0], BANDEIRAS[d["bandeira"]][0]
    n = f"{c['n']:02d}"
    centavos = int(_arred(c["parcela"] * 100, 0))
    return (f"W¥PQ1¥A{cod_cia}¥KP0¥FMP{cod_band}{digitos(d['cartao'])}/{_s(d['cvv'])}"
            f"*Z{_s(d['autorizacao'])}*MSPL{n}X{cod_cia}{n}X{centavos}//{fmt2(c['residual'])}")
