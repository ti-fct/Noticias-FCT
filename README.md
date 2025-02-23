# 📰 Notícias FCT/UFG - Aplicativo de Feed de Notícias Interativo 

Um aplicativo em Python/Kivy para exibir notícias do feed RSS da FCT/UFG com visual moderno e recursos interativos!

## 🚀 Funcionalidades Principais

- **🔄 Atualização Automática**: Busca novas notícias a cada 1 hora
- **🎠 Carrossel Interativo**: Deslize entre as notícias com gestos ou automaticamente (10s/slide)
- **📸 Visual Rico**: Exibe imagens das notícias com fallback para placeholder
- **📲 QR Code Instantâneo**: Gera QR Codes clicáveis para links completos das matérias
- **🧹 Conteúdo Limpo**: Remove HTML e formata textos automaticamente
- **🎨 UI Responsiva**: Layout adaptável para diferentes telas e orientações
- **⏳ Tela de Carregamento**: Animação de progresso durante atualizações
- **🕒 Controle de Atualização**: Sistema inteligente de verificação periódica

## 💻 Tecnologias Utilizadas

- Python 3
- Framework Kivy para GUI
- BeautifulSoup4 para limpeza de HTML
- Feedparser para consumo de RSS
- QRCode para geração de códigos
- Pillow para manipulação de imagens

## 📥 Instalação e Uso

```bash
# Instalar dependências
pip install -r requirements.txt

# Executar aplicativo
python noticias_app.py

# Parametros
FEED_URL = "https://fct.ufg.br/feed"  # 📡 Altere o feed RSS
TITLE_LIMIT = 80                      # 🔠 Tamanho máximo do título
DESC_LIMIT = 600                      # 📏 Tamanho máximo da descrição
UPDATE_INTERVAL = 3600                # ⏰ Intervalo de atualização (segundos)
