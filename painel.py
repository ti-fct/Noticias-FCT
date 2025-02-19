from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.carousel import Carousel
from kivy.properties import StringProperty, ListProperty
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.config import Config
from kivy.uix.image import AsyncImage  # Necessário para AsyncImage

import feedparser
from bs4 import BeautifulSoup
import logging
import locale
from datetime import datetime
from urllib.parse import urljoin
import qrcode
import os

# Configuração inicial para tela cheia
Config.set('graphics', 'fullscreen', 'auto')

# Configurações gerais
logging.basicConfig(level=logging.INFO)
try:
    locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
except locale.Error as e:
    logging.warning("Locale pt_BR.UTF-8 não está disponível, usando configuração padrão.")

# Definição do RootWidget (necessário para o arquivo KV)
class RootWidget(BoxLayout):
    pass

# -----------------------------------------------------------
# Classe para cada item de notícia no carrossel
# -----------------------------------------------------------
class NewsItem(BoxLayout):
    title = StringProperty('')
    content = StringProperty('')
    image_source = StringProperty('')
    pub_date = StringProperty('')
    qr_code = StringProperty('')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Clock.schedule_once(self._finalizar_inicializacao)

    def _finalizar_inicializacao(self, dt):
        """Carrega imagem padrão se necessário"""
        if not self.image_source:
            self.image_source = 'assets/placeholder.png'

# -----------------------------------------------------------
# Classe principal do carrossel de notícias
# -----------------------------------------------------------
class NewsCarousel(Carousel):
    news_items = ListProperty([])
    BASE_URL = 'https://fct.ufg.br'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.direction = 'right'
        self.loop = True
        self.qr_dir = 'qrcodes'
        
        # Garante a criação do diretório para QR codes
        os.makedirs(self.qr_dir, exist_ok=True)
        
        # Agenda atualizações automáticas
        Clock.schedule_once(self.carregar_noticias)
        Clock.schedule_interval(self.carregar_noticias, 300)
        Clock.schedule_interval(self.passar_slide_automatico, 10)

    def passar_slide_automatico(self, dt):
        """Passa os slides automaticamente a cada 10 segundos"""
        if self.slides:
            self.load_next(mode='next')

    def gerar_qr_code(self, url, news_id):
        """Gera e salva QR code para a URL da notícia"""
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(url)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white")
            caminho_qr = os.path.join(self.qr_dir, f'qr_{news_id}.png')
            qr_img.save(caminho_qr)
            return caminho_qr
        except Exception as e:
            logging.error(f"Erro no QR code: {e}")
            return ''

    def formatar_data(self, data_str):
        """Formata a data para o padrão brasileiro"""
        try:
            data = datetime.strptime(data_str, '%a, %d %b %Y %H:%M:%S %z')
            return data.strftime('%d de %B de %Y às %H:%M')
        except Exception as e:
            logging.error(f"Erro na formatação: {e}")
            return data_str

    def corrigir_url_imagem(self, url):
        """Garante URLs absolutas para as imagens e corrige URL malformadas"""
        if not url:
            return 'assets/placeholder.png'
        # Se a URL estiver malformada, removendo o prefixo redundante
        if url.startswith("http://fct.ufg.brhttps://"):
            url = url.replace("http://fct.ufg.br", "")
        if not url.startswith(('http://', 'https://')):
            return urljoin(self.BASE_URL, url)
        return url

    def extrair_conteudo_principal(self, html):
        """Processa o HTML para extrair texto e imagem principal"""
        soup = BeautifulSoup(html, 'html.parser')
        img_tag = soup.find('img')
        img_url = self.corrigir_url_imagem(img_tag['src']) if img_tag else None
        
        # Aumentar para 5 parágrafos e 1000 caracteres
        texto_principal = [
            p.get_text().strip() for p in soup.find_all('p') 
            if p.get_text().strip() and not any(m in p.get_text().lower() for m in ['texto:', 'foto:'])
        ]
        
        conteudo = ' '.join(texto_principal[:5])  # Alterado de 3 para 5 parágrafos
        if len(conteudo) > 1000:  # Aumentado de 600 para 1000 caracteres
            conteudo = conteudo[:1000] + '...'
        return conteudo, img_url

    def carregar_noticias(self, *args):
        """Busca e processa as notícias do feed RSS"""
        try:
            feed = feedparser.parse('https://fct.ufg.br/feed')
            noticias_processadas = []
            
            for idx, entrada in enumerate(feed.entries[:5]):  # Limita a 5 notícias
                conteudo, img_url = self.extrair_conteudo_principal(entrada.get('description', ''))
                titulo = entrada.title if len(entrada.title) <= 80 else entrada.title[:80] + '...'
                pub_date = self.formatar_data(entrada.published) if 'published' in entrada else ''
                noticias_processadas.append({
                    'title': titulo,
                    'content': conteudo,
                    'image_source': img_url or 'assets/placeholder.png',
                    'pub_date': pub_date,
                    'qr_code': self.gerar_qr_code(entrada.link, idx)
                })
            
            self.news_items = noticias_processadas
            self._criar_slides()
            
        except Exception as e:
            logging.error(f"Erro ao carregar notícias: {e}")

    def _criar_slides(self):
        """Atualiza os slides do carrossel"""
        self.clear_widgets()
        for item in self.news_items:
            self.add_widget(NewsItem(**item))

# -----------------------------------------------------------
# Classe principal da aplicação
# -----------------------------------------------------------
class NewsPanel(App):
    clock_text = StringProperty('')
    
    def build(self):
        """Inicializa a aplicação"""
        self.title = 'Painel FCT/UFG'
        Clock.schedule_interval(self.atualizar_relogio, 1)
        # Certifique-se de que o arquivo KV esteja nomeado corretamente (painel.kv)
        return Builder.load_file('painel.kv')
    
    def atualizar_relogio(self, dt):
        """Atualiza o relógio digital"""
        self.clock_text = datetime.now().strftime("%H:%M:%S")

if __name__ == '__main__':
    NewsPanel().run()
