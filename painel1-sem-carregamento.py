import re
from bs4 import BeautifulSoup  # Biblioteca para manipulação e limpeza de HTML
import qrcode                # Biblioteca para gerar QR codes
from io import BytesIO       # Para manipulação de fluxos de bytes
from PIL import Image        # Biblioteca de processamento de imagens

import feedparser            # Biblioteca para ler feeds RSS
from kivy.app import App      # Classe base para aplicativos Kivy
from kivy.clock import Clock  # Permite agendar eventos (ex.: troca de slide)
from kivy.core.window import Window  # Configurações da janela do app
from kivy.graphics import Color, Rectangle  # Elementos gráficos
from kivy.uix.boxlayout import BoxLayout  # Layout em caixa
from kivy.uix.carousel import Carousel  # Componente de slides
from kivy.uix.image import AsyncImage, Image as KivyImage  # Imagens assíncronas e sincronas no Kivy
from kivy.uix.label import Label  # Rótulos de texto
from kivy.metrics import dp  # Para definição de medidas independentes de densidade
from kivy.uix.scrollview import ScrollView  # Permite rolagem de conteúdo
from kivy.core.image import Image as CoreImage  # Para criar texturas a partir de imagens

# URL do feed RSS e limites de caracteres para título e descrição
FEED_URL = "https://fct.ufg.br/feed"
TITLE_LIMIT = 80  # Limite de caracteres para o título
DESC_LIMIT = 600  # Limite de caracteres para a descrição

def create_qr_code(url):
    """
    Cria um QR code para a URL fornecida e retorna como textura Kivy.
    """
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(url)
    qr.make(fit=True)
    
    # Gera a imagem do QR code utilizando PIL
    img_pil = qr.make_image(fill_color="black", back_color="white")
    
    # Converte a imagem para um buffer de bytes em formato PNG
    buffer = BytesIO()
    img_pil.save(buffer, format='PNG')
    buffer.seek(0)
    
    # Cria uma textura Kivy a partir do buffer
    return CoreImage(BytesIO(buffer.read()), ext='png').texture

def clean_text(html_content):
    """
    Limpa e formata o texto HTML usando BeautifulSoup.
    Remove tags desnecessárias e espaços extras.
    """
    if not html_content:
        return ""
    
    # Converte o conteúdo HTML para um objeto BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Remove as tags <script> e <style>
    for script in soup(["script", "style"]):
        script.decompose()
    
    # Extrai o texto, separando elementos com um espaço
    text = soup.get_text(separator=' ', strip=True)
    
    # Remove espaços extras e quebras de linha usando regex
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def truncate_text(text, limit):
    """
    Trunca o texto mantendo palavras completas.
    Se o texto excede o limite, corta até o último espaço e adiciona reticências.
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
    Se encontrada, corrige a URL com fix_image_url.
    """
    soup = BeautifulSoup(description, 'html.parser')
    img_tag = soup.find('img')
    if img_tag and img_tag.get('src'):
        return fix_image_url(img_tag['src'])
    return None

class Header(BoxLayout):
    """
    Classe que define o cabeçalho do aplicativo.
    Exibe o título "Notícias FCT/UFG" com fundo azul.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint_y = None
        self.height = dp(60)
        self.padding = [dp(20), 0]
        
        # Desenha um retângulo azul como fundo do cabeçalho
        with self.canvas.before:
            Color(0.1, 0.1, 0.8, 1)
            self.rect = Rectangle(pos=self.pos, size=self.size)
        
        # Atualiza a posição e tamanho do retângulo quando o layout muda
        self.bind(pos=self.update_rect, size=self.update_rect)
        
        # Cria e configura o rótulo do título
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
        Atualiza a posição e tamanho do retângulo de fundo conforme o layout.
        """
        self.rect.pos = self.pos
        self.rect.size = self.size

class NewsSlide(BoxLayout):
    """
    Classe que representa um slide de notícia.
    Organiza a imagem e o texto (título, descrição, link e QR code) em dois containers.
    """
    def __init__(self, entry, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "horizontal"
        self.padding = [dp(20), dp(20)]
        self.spacing = dp(20)
        
        # Container da imagem (lado esquerdo)
        image_container = BoxLayout(
            orientation='vertical',
            size_hint_x=0.4
        )
        
        # Extrai a URL da imagem da notícia
        image_url = extract_image(entry.get("description", ""))
        if image_url:
            # Exibe a imagem de forma assíncrona para evitar bloqueio da interface
            img = AsyncImage(
                source=image_url,
                size_hint=(1, 1),
                fit_mode='contain'
            )
            image_container.add_widget(img)
        else:
            # Se não houver imagem, exibe um placeholder com texto informativo
            placeholder = Label(
                text="Sem imagem disponível",
                color=(0.5, 0.5, 0.5, 1)
            )
            image_container.add_widget(placeholder)
        
        self.add_widget(image_container)
        
        # Container de texto (lado direito) com rolagem vertical
        text_container = ScrollView(
            size_hint_x=0.6,
            do_scroll_x=False,
            do_scroll_y=False
        )
        
        # Layout interno do container de texto
        text_layout = BoxLayout(
            orientation='vertical',
            spacing=dp(15),
            size_hint_y=None,
            padding=[0, 0, 0, dp(120)]  # Padding inferior para espaço extra
        )
        text_layout.bind(minimum_height=text_layout.setter('height'))
        
        # Título da notícia, processado e truncado
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
        
        # Descrição da notícia, processada e truncada
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
        
        # Espaçador para separar visualmente os elementos
        spacer = BoxLayout(size_hint_y=None, height=dp(20))
        text_layout.add_widget(spacer)
        
        # Se houver link, adiciona o container com "Leia mais" e QR code
        link = entry.get("link", "")
        if link:
            bottom_container = BoxLayout(
                orientation='horizontal',
                size_hint_y=None,
                height=dp(100),
                spacing=dp(6),
                pos_hint={'right': 1}  # Alinha à direita
            )
            
            # Container para exibir o texto "Leia mais em:" e o link
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
            
            # Gera o QR code e cria a imagem correspondente
            qr_texture = create_qr_code(link)
            qr_image = KivyImage(
                texture=qr_texture,
                size_hint_x=0.4
            )
            
            # Adiciona o container com o link e o QR code ao layout inferior
            bottom_container.add_widget(read_more_container)
            bottom_container.add_widget(qr_image)
            text_layout.add_widget(bottom_container)
        
        text_container.add_widget(text_layout)
        self.add_widget(text_container)

class NoticiasApp(App):
    """
    Classe principal do aplicativo.
    Responsável por construir a interface e carregar as notícias.
    """
    def build(self):
        # Configura a janela: cor de fundo e modo de tela cheia
        Window.clearcolor = (0.95, 0.95, 0.95, 1)
        Window.fullscreen = True

        # Cria o layout principal (vertical)
        root = BoxLayout(orientation="vertical")
        root.add_widget(Header())

        # Cria o Carousel para exibir os slides de notícias
        self.carousel = Carousel(
            direction='right',
            loop=True,
            size_hint=(1, 1)
        )
        root.add_widget(self.carousel)

        try:
            # Carrega o feed RSS
            feed = feedparser.parse(FEED_URL)
            entries = feed.entries

            if not entries:
                # Se não houver notícias, exibe uma mensagem informativa
                self.carousel.add_widget(Label(
                    text="Nenhuma notícia disponível no momento.",
                    font_size=dp(32),
                    color=(0, 0, 0, 1)
                ))
            else:
                # Para cada notícia, cria um slide e adiciona ao carousel
                for entry in entries:
                    self.carousel.add_widget(NewsSlide(entry))
        except Exception as e:
            # Em caso de erro, exibe uma mensagem de erro
            self.carousel.add_widget(Label(
                text=f"Erro ao carregar notícias: {str(e)}",
                font_size=dp(32),
                color=(0, 0, 0, 1)
            ))

        # Agenda a troca automática de slides a cada 10 segundos
        Clock.schedule_interval(self.switch_slide, 10)
        return root

    def switch_slide(self, dt):
        """
        Callback que troca para o próximo slide do carousel.
        """
        self.carousel.load_next()

if __name__ == '__main__':
    NoticiasApp().run()
