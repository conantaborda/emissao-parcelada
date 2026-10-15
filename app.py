import streamlit as st
from core import (CIAS, BANDEIRAS, PASSAGEIROS, LINK_FINANCIAMENTOS, OK, validar, calcular, fmt_br,
                  parcelas_da_cia, comando_autorizacao, comando_emissao, etapa1_ok, etapa2_ok)

st.set_page_config(page_title="Emissão parcelada SABRE", page_icon="💳", layout="wide")
st.markdown(
    """<style>
    .block-container {padding-top: 3.2rem; padding-bottom: 1rem;}
    div[data-testid="stVerticalBlock"] {gap: 0.35rem;}
    div[data-testid="stCaptionContainer"] {margin-top: -0.3rem;}
    </style>""",
    unsafe_allow_html=True,
)

# Nada é gravado em arquivo/banco/log: os dados vivem só no st.session_state de cada sessão.
CHAVES = ["cia", "bandeira", "cartao", "cvv", "tarifa", "taxa", "pax", "autorizacao"]
K = {k: f"w_{k}" for k in CHAVES + ["parcelas", "total", "vparcela", "residual"]}
RESETA_NONE = ("cia", "bandeira", "pax")


def _limpar():
    for k in CHAVES:
        st.session_state[K[k]] = None if k in RESETA_NONE else ""


def _fmt_status(s):
    if s == OK:
        return ":green[✓ OK]"
    if s.startswith(("Insira", "Selecione")):
        return f":blue[{s}]"
    return f":red[{s}]"


def _pre_calculo():
    """Atualiza os campos calculados/pré-definidos antes de criar os widgets."""
    d = {k: st.session_state.get(K[k]) for k in CHAVES}
    n = parcelas_da_cia(d["cia"])
    c = calcular(d)
    st.session_state[K["parcelas"]] = f"{n}x sem juros" if n else ""
    st.session_state[K["total"]] = fmt_br(c["total"]) if c else ""
    st.session_state[K["vparcela"]] = fmt_br(c["parcela"]) if c else ""
    st.session_state[K["residual"]] = fmt_br(c["residual"]) if c else ""


_pre_calculo()

t1, t2, t3 = st.columns([4, 2, 1], vertical_alignment="bottom")
t1.markdown("### Emissão parcelada SABRE")
t2.link_button("Consultar financiamentos das cias", LINK_FINANCIAMENTOS, use_container_width=True)
t3.button("Limpar campos", on_click=_limpar, use_container_width=True)

dados, slots = {}, {}


def campo(key, label, tipo="text", opcoes=None, placeholder="", disabled=False, max_chars=None):
    if tipo == "select":
        dados[key] = st.selectbox(label, opcoes, index=None, key=K[key], placeholder="Selecione")
    else:
        dados[key] = st.text_input(label, key=K[key], placeholder=placeholder,
                                   disabled=disabled, max_chars=max_chars)
    slots[key] = st.empty()


def calculado(key, label):
    st.text_input(label, key=K[key], disabled=True)


esq, dir_ = st.columns(2, gap="large")

# ---------------- Etapa 1 ----------------
with esq:
    st.markdown("**Etapa 1 — Comando de autorização**")
    saida1 = st.empty()
    a, b = st.columns(2)
    with a: campo("cia", "Companhia", "select", list(CIAS))
    with b: campo("bandeira", "Bandeira do cartão", "select", list(BANDEIRAS))
    a, b = st.columns(2)
    with a: campo("cartao", "Número do cartão", placeholder="15 (Amex) ou 16 dígitos", max_chars=19)
    with b: campo("cvv", "Código de segurança", placeholder="3 dígitos (Amex: 4)", max_chars=4)
    a, b = st.columns(2)
    with a: campo("tarifa", "Tarifa (por passageiro)", placeholder="0,00")
    with b: campo("taxa", "Taxa (por passageiro)", placeholder="0,00")
    a, b = st.columns(2)
    with a: campo("pax", "Quantidade de passageiros", "select", PASSAGEIROS)
    with b: calculado("total", "Total da passagem individual")

# ---------------- Etapa 2 ----------------
with dir_:
    st.markdown("**Etapa 2 — Comando de emissão** (preencha após obter a autorização)")
    saida2 = st.empty()
    a, b = st.columns(2)
    with a: campo("autorizacao", "Número da autorização", placeholder="somente números")
    with b: st.text_input("Parcelas (definido pela cia)", key=K["parcelas"], disabled=True)
    a, b = st.columns(2)
    with a: calculado("vparcela", "Valor da parcela")
    with b: calculado("residual", "Valor residual")

for key, status in validar(dados).items():
    if key in slots:
        slots[key].caption(_fmt_status(status))

with saida1.container():
    cmd1 = comando_autorizacao(dados)
    if cmd1:
        st.code(cmd1, language=None)  # botão de copiar embutido
    else:
        st.info("Preencha os campos da etapa 1 para gerar o comando.")

with saida2.container():
    cmd2 = comando_emissao(dados)
    if cmd2:
        st.code(cmd2, language=None)
    elif not etapa1_ok(dados):
        st.info("Conclua a etapa 1 primeiro.")
    else:
        st.info("Informe a autorização para gerar o comando de emissão.")
