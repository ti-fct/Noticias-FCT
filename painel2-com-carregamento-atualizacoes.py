import re
from bs4 import BeautifulSoup  
import qrcode                
from io import BytesIO       
from PIL import Image        
import feedparser            
from kivy.app import App      
from kivy.clock import Clock  
from kivy.core.window import Window  
from kivy.graphics import Color, Rectangle  
from kivy.uix.boxlayout import BoxLayout  
from kivy.uix.carousel import Carousel  
from kivy.uix.image import AsyncImage, Image as KivyImage  
from kivy.uix.label import Label  
from kivy.metrics import dp  
from kivy.uix.scrollview import ScrollView  
from kivy.core.image import Image as CoreImage
from kivy.uix.progressbar import ProgressBar
from kivy.animation import Animation
from kivy.properties import ObjectProperty
from datetime import datetime

# Constantes
FEED_URL = "https://fct.ufg.br/feed"
TITLE_LIMIT = 80  
DESC_LIMIT = 600  
UPDATE_INTERVAL = 3600  # 1 hora em segundos

def create_qr_code(url):
    """
    Cria um QR code para a URL fornecida e retorna como textura Kivy.
    """
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(url)
    qr.make(fit=True)
    
    img_pil = qr.make_image(fill_color="black", back_color="white")
    
    buffer = BytesIO()
    img_pil.save(buffer, format='PNG')
    buffer.seek(0)
    
    return CoreImage(BytesIO(buffer.read()), ext='png').texture

def clean_text(html_content):
    """
    Limpa e formata o texto HTML usando BeautifulSoup.
    Remove tags desnecessárias e espaços extras.
    """
    if not html_content:
        return ""
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    for script in soup(["script", "style"]):
        script.decompose()
    
    text = soup.get_text(separator=' ', strip=True)
    
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def truncate_text(text, limit):
    """
    Trunca o texto mantendo palavras completas.
    """
    if len(text) <= limit:
        return text
    
    truncated = text[:limit]
    last_space = truncated.rfind(' ')
    if last_space > 0:
        truncated = truncated[:last_space]
    return truncated + '...'

def fix_image_url(url):
    """
    Corrige URLs de imagem que estejam concatenadas incorretamente com o domínio.
    """
    if url.startswith(("http://fct.ufg.brhttps:", "https://fct.ufg.brhttps:")):
        return url.replace("http://fct.ufg.br", "").replace("https://fct.ufg.br", "")
    return url

def extract_image(description):
    """
    Extrai a primeira imagem válida da descrição usando BeautifulSoup.
    """
    soup = BeautifulSoup(description, 'html.parser')
    img_tag = soup.find('img')
    if img_tag and img_tag.get('src'):
        return fix_image_url(img_tag['src'])
    return None

class LoadingScreen(BoxLayout):
    """
    Tela de carregamento com barra de progresso animada e mensagem.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = [dp(20), dp(20)]
        self.spacing = dp(30)
        
        content = BoxLayout(
            orientation='vertical',
            spacing=dp(20),
            size_hint=(0.8, None),
            height=dp(150),
            pos_hint={'center_x': 0.5, 'center_y': 0.5}
        )
        
        self.loading_label = Label(
            text="Atualizando notícias...",
            font_size=dp(32),
            color=(0.1, 0.1, 0.8, 1),
            size_hint_y=None,
            height=dp(50)
        )
        
        self.progress_bar = ProgressBar(
            max=100,
            value=0,
            size_hint_y=None,
            height=dp(20)
        )
        
        content.add_widget(self.loading_label)
        content.add_widget(self.progress_bar)
        self.add_widget(content)
        
        self.start_progress_animation()
    
    def start_progress_animation(self):
        """
        Anima a barra de progresso de 0 a 100%.
        """
        anim = Animation(value=100, duration=2)
        anim.start(self.progress_bar)

class Header(BoxLayout):
    """
    Classe que define o cabeçalho do aplicativo.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint_y = None
        self.height = dp(60)
        self.padding = [dp(20), 0]
        
        with self.canvas.before:
            Color(0.1, 0.1, 0.8, 1)
            self.rect = Rectangle(pos=self.pos, size=self.size)
        
        self.bind(pos=self.update_rect, size=self.update_rect)
        
        title_label = Label(
            text="Notícias FCT/UFG",
            color=(1, 1, 1, 1),
            bold=True,
            font_size=dp(32),
            size_hint_x=1,
            halign='center',
            valign='middle'
        )
        title_label.bind(size=lambda *_: setattr(title_label, 'text_size', title_label.size))
        self.add_widget(title_label)

    def update_rect(self, *args):
        """
        Atualiza a posição e tamanho do retângulo de fundo.
        """
        self.rect.pos = self.pos
        self.rect.size = self.size

class NewsSlide(BoxLayout):
    """
    Classe que representa um slide de notícia.
    """
    def __init__(self, entry, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "horizontal"
        self.padding = [dp(20), dp(20)]
        self.spacing = dp(20)
        
        # Container da imagem
        image_container = BoxLayout(
            orientation='vertical',
            size_hint_x=0.4
        )
        
        image_url = extract_image(entry.get("description", ""))
        if image_url:
            img = AsyncImage(
                source=image_url,
                size_hint=(1, 1),
                fit_mode='contain'
            )
            image_container.add_widget(img)
        else:
            placeholder = Label(
                text="Sem imagem disponível",
                color=(0.5, 0.5, 0.5, 1)
            )
            image_container.add_widget(placeholder)
        
        self.add_widget(image_container)
        
        # Container de texto
        text_container = ScrollView(
            size_hint_x=0.6,
            do_scroll_x=False,
            do_scroll_y=False
        )
        
        text_layout = BoxLayout(
            orientation='vertical',
            spacing=dp(15),
            size_hint_y=None,
            padding=[0, 0, 0, dp(120)]
        )
        text_layout.bind(minimum_height=text_layout.setter('height'))
        
        title_text = truncate_text(clean_text(entry.get("title", "")), TITLE_LIMIT)
        title_label = Label(
            text=title_text,
            font_size=dp(28),
            bold=True,
            color=(0, 0, 0, 1),
            size_hint_y=None,
            height=dp(80),
            halign='justify',
            valign='middle'
        )
        title_label.bind(size=lambda *_: setattr(title_label, 'text_size', (title_label.width, None)))
        text_layout.add_widget(title_label)
        
        desc_text = truncate_text(clean_text(entry.get("description", "")), DESC_LIMIT)
        desc_label = Label(
            text=desc_text,
            font_size=dp(26),
            color=(0, 0, 0, 0.8),
            size_hint_y=None,
            halign='justify',
            valign='top'
        )
        desc_label.bind(
            size=lambda *_: setattr(desc_label, 'text_size', (desc_label.width, None)),
            texture_size=lambda *_: setattr(desc_label, 'height', desc_label.texture_size[1])
        )
        text_layout.add_widget(desc_label)
        
        spacer = BoxLayout(size_hint_y=None, height=dp(20))
        text_layout.add_widget(spacer)
        
        link = entry.get("link", "")
        if link:
            bottom_container = BoxLayout(
                orientation='horizontal',
                size_hint_y=None,
                height=dp(100),
                spacing=dp(6),
                pos_hint={'right': 1}
            )
            
            read_more_container = BoxLayout(
                orientation='vertical',
                size_hint_x=3.5
            )
            
            read_more_label = Label(
                text="Leia mais em:",
                font_size=dp(22),
                color=(0.1, 0.1, 0.8, 1),
                size_hint_y=None,
                height=dp(30),
                halign='right',
                valign='bottom'
            )
            read_more_label.bind(size=lambda *_: setattr(read_more_label, 'text_size', (read_more_label.width, None)))
            
            link_label = Label(
                text=link,
                font_size=dp(16),
                color=(0.1, 0.1, 0.8, 1),
                size_hint_y=None,
                height=dp(70),
                halign='right',
                valign='top'
            )
            link_label.bind(size=lambda *_: setattr(link_label, 'text_size', (link_label.width, None)))
            
            read_more_container.add_widget(read_more_label)
            read_more_container.add_widget(link_label)
            
            qr_texture = create_qr_code(link)
            qr_image = KivyImage(
                texture=qr_texture,
                size_hint_x=0.4
            )
            
            bottom_container.add_widget(read_more_container)
            bottom_container.add_widget(qr_image)
            text_layout.add_widget(bottom_container)
        
        text_container.add_widget(text_layout)
        self.add_widget(text_container)

class NewsContainer(BoxLayout):
    """
    Container principal para as notícias.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.current_widget = None
        
        self.add_widget(Header())
        
        self.show_loading_screen()
    
    def show_loading_screen(self):
        """
        Exibe a tela de carregamento.
        """
        if self.current_widget:
            self.remove_widget(self.current_widget)
        self.current_widget = LoadingScreen()
        self.add_widget(self.current_widget)
    
    def show_carousel(self, carousel):
        """
        Exibe o carousel de notícias.
        """
        if self.current_widget:
            self.remove_widget(self.current_widget)
        self.current_widget = carousel
        self.add_widget(self.current_widget)

class NoticiasApp(App):
    """
    Classe principal do aplicativo.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.carousel = None
        self.container = None
        self.last_update = None
    
    def build(self):
        Window.clearcolor = (0.95, 0.95, 0.95, 1)
        Window.fullscreen = True
        
        self.container = NewsContainer()
        
        Clock.schedule_once(self.update_news, 2)
        
        Clock.schedule_interval(self.check_for_updates, 60)
        
        return self.container
    
    def create_carousel(self):
        """
        Cria um novo carousel com as notícias.
        """
        carousel = Carousel(
            direction='right',
            loop=True,
            size_hint=(1, 1)
        )
        
        try:
            feed = feedparser.parse(FEED_URL)
            entries = feed.entries
            
            if not entries:
                carousel.add_widget(Label(
                    text="Nenhuma notícia disponível no momento.",
                    font_size=dp(32),
                    color=(0, 0, 0, 1)
                ))
            else:
                for entry in entries:
                    carousel.add_widget(NewsSlide(entry))
            
            Clock.schedule_interval(lambda dt: carousel.load_next(), 10)
            
        except Exception as e:
            carousel.add_widget(Label(
                text=f"Erro ao carregar notícias: {str(e)}",
                font_size=dp(32),
                color=(0, 0, 0, 1)
            ))
        
        return carousel
    
    def update_news(self, dt):
        """
        Atualiza as notícias.
        """
        self.container.show_loading_screen()
        
        Clock.schedule_once(self.finish_update, 2)
        
        self.last_update = datetime.now()
    
    def finish_update(self, dt):
        """
        Finaliza a atualização.
        """
        self.carousel = self.create_carousel()
        self.container.show_carousel(self.carousel)
    
    def check_for_updates(self, dt):
        """
        Verifica se é hora de atualizar as notícias.
        """
        if self.last_update:
            time_diff = (datetime.now() - self.last_update).total_seconds()
            if time_diff >= UPDATE_INTERVAL:
                self.update_news(None)

if __name__ == '__main__':
    NoticiasApp().run()