import streamlit as st, base64

st.set_page_config(page_title="Facilita NF", page_icon="🧾", layout="wide")

def img_b64(p):
    try:
        return base64.b64encode(open(p, "rb").read()).decode()
    except FileNotFoundError:
        st.error(f"Erro: Arquivo não encontrado em '{p}'.")
        return ""

LOGO = img_b64("static/logo.png")
HERO = img_b64("static/hero.png")
FOOTER_LOGO = img_b64("static/logo_footer.png")

# ----------------------- CSS -----------------------
st.markdown(f"""
<style>
html, body, #root {{
  height: 100%;
}}
.stApp {{
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}}
[data-testid="stAppViewContainer"] > .main {{
  flex: 1 0 auto;
}}

html,body {{
  background:#0F1116;
  color:#E6E8F2;
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Inter", Roboto, "Segoe UI", sans-serif;
}}

.full-bleed{{ width:100vw; margin-left:calc(50% - 50vw); }}
.app-header{{ position:sticky; top:3.6rem; z-index:1000; background:#0B2A4A; border-bottom:2px solid #2F4F75; }}
.app-header .inner{{ max-width:1100px; margin:0 auto; padding:32px 16px; display:flex; align-items:center; justify-content:center; }}
.app-header .brand{{ display:flex; align-items:center; gap:.6rem; color:#fff; font-weight:700; }}
.app-header img{{ height:55px; }}
.app-header a{{ color:#fff; text-decoration:none; margin-left:24px; font-weight:600; opacity:.9; }}
.app-header a:hover{{ opacity:1; text-decoration:underline; }}

/* FOOTER */
.app-footer.full-bleed {{
  width: 100vw;
  margin-left: calc(50% - 50vw);
  
  padding: 40px 16px;
  margin-top: 50px;
}}
.footer-inner {{
  max-width: 1100px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100px;
}}
.footer-logo img {{
  height: 48px;
  width: auto;
  object-fit: contain;
  filter: brightness(1) saturate(1);
}}

/* HERO */
.box-wrap {{
  margin: 40px auto;
  padding: 0 16px;
  max-width: 1100px;
}}
.canvas-box {{
  width: 100%;
  height: 388px;
  background: #0E2D5D;
  border-radius: 20px;
  box-shadow: 0 10px 20px rgba(0,0,0,.15);
  color: #fff;
  position: relative;
  overflow: hidden;
  display: grid;
  grid-template-columns: 560px 1fr;
  gap: 24px;
  padding: 0;
}}
.canvas-img {{
  height: 170%;
  margin-top: -12%;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  overflow: hidden;
}}
.canvas-img img {{
  height: 100%;
  width: auto;
  object-fit: contain;
  object-position: left center;
  border-top-left-radius: 20px;
  border-bottom-left-radius: 20px;
}}
.canvas-copy {{
  display: flex;
  flex-direction: column;
  justify-content: center;
  color: #fff;
  padding: 32px;
  max-width: 500px;
}}
.canvas-copy h2 {{
  margin: 0 0 .75rem;
  font-size: 2rem;
  line-height: 1.2;
  color: #fff;
  font-weight: 600;
  text-align: left;
}}
.canvas-copy p {{
  margin: 0 0 1rem;
  opacity: .95;
  font-size: 1rem;
  line-height: 1.5;
  text-align: left;
}}

/* COMO FUNCIONA */
.feature-title-wrap {{
  max-width: 1100px;
  margin: 60px auto 32px auto;
  padding: 0 16px;
}}
.feature-title-wrap h2 {{
  color: #ffffff;
  font-size: 2rem;
  font-weight: 700;
  margin: 0;
  line-height: 1.25;
}}
.bottom-cards-wrap {{
  max-width: 1100px;
  margin: 0 auto;
  padding: 0 10px;
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 24px;
}}
.small-card {{
  flex: 1 1 0;
  min-width: 200px;
  max-width: 340px;
  height: 105px;
  display: flex;
  align-items: stretch;
  position: relative;
}}
.small-card .pill-yellow {{
  background: #F7C62F;
  border-radius: 20px;
  flex: 0 0 20%;
  height: 100%;
}}
.small-card .pill-blue {{
  background: #0E2D5D;
  border-radius: 20px;
  flex: 1 1 auto;
  height: 100%;
  margin-left: -40px;
  padding: 20px 24px;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  font-size: 0.95rem;
  line-height: 1.5;
  font-weight: 500;
  box-shadow: 0 10px 24px rgba(0,0,0,.25);
}}

/* CTA button central */
.center-wrap {{
  justify-content: center;
  margin-top: 24px;
}}
.center-wrap .stButton>button {{
  font-weight: 7.15rem ;
  padding: 0.75rem 6.5rem;
  border-radius: 8px;
}}


</style>
""", unsafe_allow_html=True)

# ----------------------- HEADER -----------------------
st.markdown(f"""
<div class="app-header full-bleed">
  <div class="inner">
    <div class="brand">
      <img src="data:image/png;base64,{LOGO}" alt="Facilita NF"/>
    </div>
  </div>
</div>

""", unsafe_allow_html=True)


# ----------------------- HERO + CTA -----------------------
st.markdown(f"""
<div class="box-wrap">
  <div class="canvas-box">
    <div class="canvas-img">
      <img src="data:image/png;base64,{HERO}" alt="hero"/>
    </div>
    <div class="canvas-copy">
      <h2>O Seu Agente Pessoal<br/>para NF Perfeita!</h2>
      <p>
        Elimine a dor de cabeça do preenchimento incorreto e dos arredondamentos:
        automatize a conformidade fiscal e evite que seu negócio faça parte
        dos 60% de empresas com divergências em NF.
      </p>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ----------------------- CTA centralizado -----------------------
def cta_validar(key="cta"):
    col1, col2, col3 = st.columns([1.90, 0.50, 1.90])
    with col2:
        try:
            if st.button("🧾 Validar agora", key=key):
                st.switch_page("pages/1_Valide_sua_nota.py")
        except Exception:
            st.page_link("pages/1_Valide_sua_nota.py", label="🧾 Validar agora")


cta_validar(key="cta-top")

# ----------------------- COMO FUNCIONA -----------------------
st.markdown("""
<div class="feature-title-wrap">
  <h2>Veja como funciona:</h2>
</div>

<div class="bottom-cards-wrap">
  <div class="small-card">
    <div class="pill-yellow"></div>
    <div class="pill-blue">
      <p>Suba seu arquivo PDF e XML da NF-e<br/>para análise instantânea.</p>
    </div>
  </div>
  <div class="small-card">
    <div class="pill-yellow"></div>
    <div class="pill-blue">
      <p>Fazemos a validação dos dados fiscais e cálculos automáticos.</p>
    </div>
  </div>
  <div class="small-card">
    <div class="pill-yellow"></div>
    <div class="pill-blue">
      <p>Você recebe um relatório apontando as inconsistências encontradas.</p>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ----------------------- FOOTER -----------------------
st.markdown(f"""
<div class="app-footer full-bleed">
  <div class="footer-inner">
    <div class="footer-logo">
      <img src="data:image/png;base64,{FOOTER_LOGO}" alt="BRCH Logo"/>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)
