# core/capitulos.py
from __future__ import annotations
import re
from typing import Dict, Optional

# -----------------------
# Mapa "Capítulo -> Título"
# -----------------------
_CHAPTER_NAME: Dict[int, str] = {}

def load_chapter_names_from_text(raw: str) -> dict[int, str]:
    """
    Varre um texto contendo linhas do tipo:
        "Capítulo 92   Instrumentos musicais; suas partes e acessórios."
    e constrói um dicionário {92: "Instrumentos musicais; suas partes e acessórios"}.
    """
    mapping: dict[int, str] = {}
    for m in re.finditer(r"Cap[ií]tulo\s+(\d{2})\s+(.+?)(?:\.\s*|$)",
                         raw, flags=re.IGNORECASE | re.DOTALL):
        cap = int(m.group(1))
        name = re.sub(r"\s+", " ", m.group(2)).strip(" .")
        mapping[cap] = name
    return mapping

def set_chapter_names(mapping: dict[int, str]) -> None:
    global _CHAPTER_NAME
    _CHAPTER_NAME = dict(mapping or {})

def ncm_to_capitulo(ncm: str | int | None) -> Optional[int]:
    """
    Extrai o capítulo (2 primeiros dígitos) de um NCM.
    Retorna int entre 1..97 ou None.
    """
    if ncm is None:
        return None
    s = str(ncm)
    s = re.sub(r"\D+", "", s)
    if len(s) < 2:
        return None
    try:
        cap = int(s[:2])
    except ValueError:
        return None
    return cap if 1 <= cap <= 97 else None

def cap_label(cap: Optional[int]) -> str:
    """
    Retorna um rótulo bonito: "Cap. 92 — Instrumentos musicais; suas partes e acessórios"
    """
    if not isinstance(cap, int):
        return ""
    title = _CHAPTER_NAME.get(cap, f"Capítulo {cap}")
    return f"Cap. {cap} — {title}"

# ================== Texto-base (o que você me passou) ==================
CAPITULOS_RAW = """
Seção I - ANIMAIS VIVOS E PRODUTOS DO REINO ANIMAL
Capítulo 01   Animais vivos.
Capítulo 02   Carnes e miudezas, comestíveis.
Capítulo 03   Peixes e crustáceos, moluscos e outros invertebrados aquáticos.
Capítulo 04   Leite e laticínios; ovos de aves; mel natural; produtos comestíveis de origem animal, não especificados nem compreendidos noutros Capítulos.
Capítulo 05   Outros produtos de origem animal, não especificados nem compreendidos noutros Capítulos.

Seção II - PRODUTOS DO REINO VEGETAL
Capítulo 06   Plantas vivas e produtos de floricultura.
Capítulo 07   Produtos hortícolas, plantas, raízes e tubérculos, comestíveis.
Capítulo 08   Fruta; cascas de citros (citrinos) e de melões.
Capítulo 09   Café, chá, mate e especiarias.
Capítulo 10   Cereais.
Capítulo 11   Produtos da indústria de moagem; malte; amidos e féculas; inulina; glúten de trigo.
Capítulo 12   Sementes e frutos oleaginosos; grãos, sementes e frutos diversos; plantas industriais ou medicinais; palhas e forragens.
Capítulo 13   Gomas, resinas e outros sucos e extratos vegetais.
Capítulo 14   Matérias para entrançar e outros produtos de origem vegetal, não especificados nem compreendidos noutros Capítulos.

Seção III - GORDURAS E ÓLEOS ANIMAIS, VEGETAIS OU DE ORIGEM MICROBIANA E PRODUTOS DA SUA DISSOCIAÇÃO; GORDURAS ALIMENTÍCIAS ELABORADAS; CERAS DE ORIGEM ANIMAL OU VEGETAL
Capítulo 15   Gorduras e óleos animais, vegetais ou de origem microbiana e produtos da sua dissociação; gorduras alimentícias elaboradas; ceras de origem animal ou vegetal.

Seção IV - PRODUTOS DAS INDÚSTRIAS ALIMENTARES; BEBIDAS, LÍQUIDOS ALCOÓLICOS E VINAGRES; TABACO E SEUS SUCEDÂNEOS MANUFATURADOS; PRODUTOS, MESMO COM NICOTINA, DESTINADOS À INALAÇÃO SEM COMBUSTÃO; OUTROS PRODUTOS QUE CONTENHAM NICOTINA DESTINADOS À ABSORÇÃO DA NICOTINA PELO CORPO HUMANO
Capítulo 16   Preparações de carne, peixes, crustáceos, moluscos, outros invertebrados aquáticos ou de insetos.
Capítulo 17   Açúcares e produtos de confeitaria.
Capítulo 18   Cacau e suas preparações.
Capítulo 19   Preparações à base de cereais, farinhas, amidos, féculas ou leite; produtos de pastelaria.
Capítulo 20   Preparações de produtos hortícolas, fruta ou de outras partes de plantas.
Capítulo 21   Preparações alimentícias diversas.
Capítulo 22   Bebidas, líquidos alcoólicos e vinagres.
Capítulo 23   Resíduos e desperdícios das indústrias alimentares; alimentos preparados para animais.
Capítulo 24   Tabaco e seus sucedâneos manufaturados; produtos, mesmo com nicotina, destinados à inalação sem combustão; outros produtos que contenham nicotina destinados à absorção da nicotina pelo corpo humano.

Seção V - PRODUTOS MINERAIS
Capítulo 25   Sal; enxofre; terras e pedras; gesso, cal e cimento.
Capítulo 26   Minérios, escórias e cinzas.
Capítulo 27   Combustíveis minerais, óleos minerais e produtos da sua destilação; matérias betuminosas; ceras minerais.

Seção VI - PRODUTOS DAS INDÚSTRIAS QUÍMICAS OU DAS INDÚSTRIAS CONEXAS
Capítulo 28   Produtos químicos inorgânicos; compostos inorgânicos ou orgânicos de metais preciosos, de elementos radioativos, de metais das terras raras ou de isótopos.
Capítulo 29   Produtos químicos orgânicos.
Capítulo 30   Produtos farmacêuticos.
Capítulo 31   Adubos (fertilizantes).
Capítulo 32   Extratos tanantes e tintoriais; taninos e seus derivados; pigmentos e outras matérias corantes; tintas e vernizes; mástiques; tintas de escrever.
Capítulo 33   Óleos essenciais e resinoides; produtos de perfumaria ou de toucador preparados e preparações cosméticas.
Capítulo 34   Sabões, agentes orgânicos de superfície, preparações para lavagem, preparações lubrificantes, ceras artificiais, ceras preparadas, produtos de conservação e limpeza, velas e artigos semelhantes, massas ou pastas para modelar, "ceras para odontologia" e composições para odontologia à base de gesso.
Capítulo 35   Matérias albuminoides; produtos à base de amidos ou de féculas modificados; colas; enzimas.
Capítulo 36   Pólvoras e explosivos; artigos de pirotecnia; fósforos; ligas pirofóricas; matérias inflamáveis.
Capítulo 37   Produtos para fotografia e cinematografia.
Capítulo 38   Produtos diversos das indústrias químicas.

Seção VII - PLÁSTICO E SUAS OBRAS; BORRACHA E SUAS OBRAS
Capítulo 39   Plástico e suas obras.
Capítulo 40   Borracha e suas obras.

Seção VIII - PELES, COUROS, PELES COM PELO E OBRAS DESTAS MATÉRIAS; ARTIGOS DE CORREEIRO OU DE SELEIRO; ARTIGOS DE VIAGEM, BOLSAS E ARTIGOS SEMELHANTES; OBRAS DE TRIPA
Capítulo 41   Peles, exceto as peles com pelo, e couros.
Capítulo 42   Obras de couro; artigos de correeiro ou de seleiro; artigos de viagem, bolsas e artigos semelhantes; obras de tripa.
Capítulo 43   Peles com pelo e suas obras; peles com pelo artificiais.

Seção IX - MADEIRA, CARVÃO VEGETAL E OBRAS DE MADEIRA; CORTIÇA E SUAS OBRAS; OBRAS DE ESPARTARIA OU DE CESTARIA
Capítulo 44   Madeira, carvão vegetal e obras de madeira.
Capítulo 45   Cortiça e suas obras.
Capítulo 46   Obras de espartaria ou de cestaria.

Seção X - PASTAS DE MADEIRA OU DE OUTRAS MATÉRIAS FIBROSAS CELULÓSICAS; PAPEL OU CARTÃO PARA RECICLAR (DESPERDÍCIOS E RESÍDUOS); PAPEL OU CARTÃO E SUAS OBRAS
Capítulo 47   Pastas de madeira ou de outras matérias fibrosas celulósicas; papel ou cartão para reciclar (desperdícios e resíduos).
Capítulo 48   Papel e cartão; obras de pasta de celulose, papel ou de cartão.
Capítulo 49   Livros, jornais, gravuras e outros produtos das indústrias gráficas; textos manuscritos ou datilografados, planos e plantas.

Seção XI - MATÉRIAS TÊXTEIS E SUAS OBRAS
Capítulo 50   Seda.
Capítulo 51   Lã, pelos finos ou grosseiros; fios e tecidos de crina.
Capítulo 52   Algodão.
Capítulo 53   Outras fibras têxteis vegetais; fios de papel e tecidos de fios de papel.
Capítulo 54   Filamentos sintéticos ou artificiais; lâminas e formas semelhantes de matérias têxteis sintéticas ou artificiais.
Capítulo 55   Fibras sintéticas ou artificiais, descontínuas.
Capítulo 56   Pastas (ouates), feltros e falsos tecidos (tecidos não tecidos); fios especiais; cordéis, cordas e cabos; artigos de cordoaria.
Capítulo 57   Tapetes e outros revestimentos para pisos (pavimentos), de matérias têxteis.
Capítulo 58   Tecidos especiais; tecidos tufados; rendas; tapeçarias; passamanarias; bordados.
Capítulo 59   Tecidos impregnados, revestidos, recobertos ou estratificados; artigos para usos técnicos de matérias têxteis.
Capítulo 60   Tecidos de malha.
Capítulo 61   Vestuário e seus acessórios, de malha.
Capítulo 62   Vestuário e seus acessórios, exceto de malha.
Capítulo 63   Outros artigos têxteis confeccionados; sortidos; artigos de matérias têxteis e artigos de uso semelhante, usados; trapos.

Seção XII - CALÇADO, CHAPÉUS E ARTIGOS DE USO SEMELHANTE, GUARDA-CHUVAS, GUARDA-SÓIS, BENGALAS, CHICOTES, E SUAS PARTES; PENAS PREPARADAS E SUAS OBRAS; FLORES ARTIFICIAIS; OBRAS DE CABELO
Capítulo 64   Calçado, polainas e artigos semelhantes; suas partes.
Capítulo 65   Chapéus e artigos de uso semelhante, e suas partes.
Capítulo 66   Guarda-chuvas, sombrinhas, guarda-sóis, bengalas, bengalas-assentos, chicotes, pingalins, e suas partes.
Capítulo 67   Penas e penugem preparadas e suas obras; flores artificiais; obras de cabelo.

Seção XIII - OBRAS DE PEDRA, GESSO, CIMENTO, AMIANTO, MICA OU DE MATÉRIAS SEMELHANTES; PRODUTOS CERÂMICOS; VIDRO E SUAS OBRAS
Capítulo 68   Obras de pedra, gesso, cimento, amianto, mica ou de matérias semelhantes.
Capítulo 69   Produtos cerâmicos.
Capítulo 70   Vidro e suas obras.

Seção XIV - PÉROLAS NATURAIS OU CULTIVADAS, PEDRAS PRECIOSAS OU SEMIPRECIOSAS E SEMELHANTES, METAIS PRECIOSOS, METAIS FOLHEADOS OU CHAPEADOS DE METAIS PRECIOSOS (PLAQUÊ), E SUAS OBRAS; BIJUTERIAS; MOEDAS
Capítulo 71   Pérolas naturais ou cultivadas, pedras preciosas ou semipreciosas e semelhantes, metais preciosos, metais folheados ou chapeados de metais preciosos (plaquê), e suas obras; bijuterias; moedas.

Seção XV - METAIS COMUNS E SUAS OBRAS
Capítulo 72   Ferro fundido, ferro e aço.
Capítulo 73   Obras de ferro fundido, ferro ou aço.
Capítulo 74   Cobre e suas obras.
Capítulo 75   Níquel e suas obras.
Capítulo 76   Alumínio e suas obras.
Capítulo 78   Chumbo e suas obras.
Capítulo 79   Zinco e suas obras.
Capítulo 80   Estanho e suas obras.
Capítulo 81   Outros metais comuns; cermets; obras dessas matérias.
Capítulo 82   Ferramentas, artigos de cutelaria e talheres, e suas partes, de metais comuns.
Capítulo 83   Obras diversas de metais comuns.

Seção XVI - MÁQUINAS E APARELHOS, MATERIAL ELÉTRICO, E SUAS PARTES; APARELHOS DE GRAVAÇÃO OU DE REPRODUÇÃO DE SOM, APARELHOS DE GRAVAÇÃO OU DE REPRODUÇÃO DE IMAGENS E DE SOM EM TELEVISÃO, E SUAS PARTES E ACESSÓRIOS
Capítulo 84   Reatores nucleares, caldeiras, máquinas, aparelhos e instrumentos mecânicos, e suas partes.
Capítulo 85   Máquinas, aparelhos e materiais elétricos, e suas partes; aparelhos de gravação ou de reprodução de som, aparelhos de gravação ou de reprodução de imagens e de som em televisão, e suas partes e acessórios.

Seção XVII - MATERIAL DE TRANSPORTE
Capítulo 86   Veículos e material para vias férreas ou semelhantes, e suas partes; aparelhos mecânicos (incluindo os eletromecânicos) de sinalização para vias de comunicação.
Capítulo 87   Veículos automóveis, tratores, ciclos e outros veículos terrestres, suas partes e acessórios.
Capítulo 88   Aeronaves e aparelhos espaciais, e suas partes.
Capítulo 89   Embarcações e estruturas flutuantes.

Seção XVIII - INSTRUMENTOS E APARELHOS DE ÓPTICA, DE FOTOGRAFIA, DE CINEMATOGRAFIA, DE MEDIDA, DE CONTROLE OU DE PRECISÃO; INSTRUMENTOS E APARELHOS MÉDICO-CIRÚRGICOS; ARTIGOS DE RELOJOARIA; INSTRUMENTOS MUSICAIS; SUAS PARTES E ACESSÓRIOS
Capítulo 90   Instrumentos e aparelhos de óptica, de fotografia, de cinematografia, de medida, de controle ou de precisão; instrumentos e aparelhos médico-cirúrgicos; suas partes e acessórios.
Capítulo 91   Artigos de relojoaria.
Capítulo 92   Instrumentos musicais; suas partes e acessórios.

Seção XIX - ARMAS E MUNIÇÕES; SUAS PARTES E ACESSÓRIOS
Capítulo 93   Armas e munições; suas partes e acessórios.

Seção XX - MERCADORIAS E PRODUTOS DIVERSOS
Capítulo 94   Móveis; mobiliário médico-cirúrgico; colchões, almofadas e semelhantes; luminárias e aparelhos de iluminação não especificados nem compreendidos noutros Capítulos; anúncios, cartazes ou tabuletas e placas indicadoras, luminosos e artigos semelhantes; construções pré-fabricadas.
Capítulo 95   Brinquedos, jogos, artigos para divertimento ou para esporte; suas partes e acessórios.
Capítulo 96   Obras diversas.

Seção XXI - OBJETOS DE ARTE, DE COLEÇÃO E ANTIGUIDADES
Capítulo 97   Objetos de arte, de coleção e antiguidades.
""".strip()

# Inicializa o dicionário global com TODOS os capítulos
set_chapter_names(load_chapter_names_from_text(CAPITULOS_RAW))
