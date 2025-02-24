import sys
import math
import re
import threading
from datetime import datetime
from io import BytesIO
import requests
from bs4 import BeautifulSoup
import qrcode
import feedparser
from PIL import Image as PILImage

from PyQt6.QtCore import QUrl, QTimer, Qt, QDateTime, QPointF, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QKeySequence, QPainter, QPolygonF, QColor, QFont, QPixmap, QImage
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                           QLabel, QScrollArea, QGridLayout, QFrame)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

# Constantes para o feed de notícias
FEED_URL = "https://fct.ufg.br/feed"
TITLE_LIMIT = 80
DESC_LIMIT = 800  # Reduzido para garantir que o limite funcione
UPDATE_INTERVAL = 3600  # 1 hora em segundos

# Constantes para dimensões de imagem
IMAGE_WIDTH = 600  # A largura da imagem
IMAGE_HEIGHT = 700  # Altura para proporção 3:4

class NewsDownloader(QThread):
    """Thread para baixar notícias sem bloquear a interface"""
    news_ready = pyqtSignal(list)
    
    def run(self):
        try:
            feed = feedparser.parse(FEED_URL)
            processed_entries = []
            
            for entry in feed.entries:
                processed_entry = {
                    'title': self.truncate_text(self.clean_text(entry.get('title', '')), TITLE_LIMIT),
                    'description': self.truncate_text(self.clean_text(entry.get('description', '')), DESC_LIMIT),
                    'link': entry.get('link', ''),
                    'image_url': self.extract_image(entry.get('description', ''))
                }
                processed_entries.append(processed_entry)
                
            self.news_ready.emit(processed_entries)
        except Exception as e:
            print(f"Erro ao obter notícias: {str(e)}")
            self.news_ready.emit([])
    
    def clean_text(self, html_content):
        """Limpa e formata o texto HTML usando BeautifulSoup"""
        if not html_content:
            return ""
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        for script in soup(["script", "style"]):
            script.decompose()
        
        text = soup.get_text(separator=' ', strip=True)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def truncate_text(self, text, limit):
        """Trunca o texto mantendo palavras completas"""
        if len(text) <= limit:
            return text
        
        truncated = text[:limit]
        last_space = truncated.rfind(' ')
        if last_space > 0:
            truncated = truncated[:last_space]
        return truncated + '...'
    
    def fix_image_url(self, url):
        """Corrige URLs de imagem que estejam concatenadas incorretamente com o domínio"""
        if url.startswith(("http://fct.ufg.brhttps:", "https://fct.ufg.brhttps:")):
            return url.replace("http://fct.ufg.br", "").replace("https://fct.ufg.br", "")
        return url
    
    def extract_image(self, description):
        """Extrai a primeira imagem válida da descrição usando BeautifulSoup"""
        soup = BeautifulSoup(description, 'html.parser')
        img_tag = soup.find('img')
        if img_tag and img_tag.get('src'):
            return self.fix_image_url(img_tag['src'])
        return None

class ImageDownloader(QThread):
    """Thread para baixar imagens sem bloquear a interface"""
    image_ready = pyqtSignal(QPixmap)
    
    def __init__(self, url, parent=None):
        super().__init__(parent)
        self.url = url
    
    def run(self):
        try:
            response = requests.get(self.url, timeout=10)
            if response.status_code == 200:
                img_data = response.content
                qimage = QImage.fromData(img_data)
                pixmap = QPixmap.fromImage(qimage)
                self.image_ready.emit(pixmap)
            else:
                self.image_ready.emit(QPixmap())
        except Exception as e:
            print(f"Erro ao baixar imagem: {str(e)}")
            self.image_ready.emit(QPixmap())

def create_qr_code(url, size=150):
    """Cria um QR code para a URL fornecida e retorna como QPixmap"""
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(url)
    qr.make(fit=True)
    
    img_pil = qr.make_image(fill_color="black", back_color="white")
    
    buffer = BytesIO()
    img_pil.save(buffer, format='PNG')
    buffer.seek(0)
    
    qimage = QImage.fromData(buffer.getvalue())
    pixmap = QPixmap.fromImage(qimage)
    return pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio)

class NewsCarousel(QWidget):
    """Widget que exibe notícias em um carrossel"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.news_entries = []
        self.current_index = 0
        self.current_image_downloader = None
        
        self.layout = QVBoxLayout(self)
        self.setStyleSheet("""
            QWidget { background-color: #f0f0f0; }
            QLabel#title { font-size: 24px; font-weight: bold; color: #1a237e; }
            QLabel#desc { font-size: 18px; color: #333; }
            QLabel#link { font-size: 16px; color: #1976d2; }
        """)
        
        # Layout principal para notícias
        self.news_container = QWidget()
        self.news_layout = QHBoxLayout(self.news_container)
        
        # Área de imagem
        self.image_container = QWidget()
        self.image_layout = QVBoxLayout(self.image_container)
        self.image_label = QLabel("Carregando imagem...")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setFixedSize(IMAGE_WIDTH, IMAGE_HEIGHT)  # Proporção 3:4
        self.image_label.setStyleSheet("background-color: #e0e0e0; border: 1px solid #cccccc;")
        self.image_layout.addWidget(self.image_label)
        self.image_layout.addStretch()
        
        # Área de texto
        self.text_container = QWidget()
        self.text_layout = QVBoxLayout(self.text_container)
        
        self.title_label = QLabel("Carregando notícias...")
        self.title_label.setObjectName("title")
        self.title_label.setWordWrap(True)
        
        self.desc_label = QLabel()
        self.desc_label.setObjectName("desc")
        self.desc_label.setWordWrap(True)
        
        self.link_container = QWidget()
        self.link_layout = QHBoxLayout(self.link_container)
        
        self.link_info = QWidget()
        self.link_info_layout = QVBoxLayout(self.link_info)
        self.read_more_label = QLabel("Leia mais em:")
        self.link_label = QLabel()
        self.link_label.setObjectName("link")
        self.link_label.setWordWrap(True)
        self.link_info_layout.addWidget(self.read_more_label)
        self.link_info_layout.addWidget(self.link_label)
        
        self.qr_label = QLabel()
        self.qr_label.setFixedSize(150, 150)
        
        self.link_layout.addWidget(self.link_info)
        self.link_layout.addWidget(self.qr_label)
        
        self.text_layout.addWidget(self.title_label)
        self.text_layout.addWidget(self.desc_label)
        self.text_layout.addWidget(self.link_container)
        self.text_layout.addStretch()
        
        # Adicionar os contêineres ao layout principal
        self.news_layout.addWidget(self.image_container)
        self.news_layout.addWidget(self.text_container, 2)  # 2:1 proporção
        
        self.layout.addWidget(self.news_container)
        
        # Timer para alternar notícias
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.next_news)
        
        # Iniciar o downloader
        self.downloader = NewsDownloader()
        self.downloader.news_ready.connect(self.on_news_ready)
        self.downloader.start()
    
    def on_news_ready(self, entries):
        """Chamado quando as notícias são baixadas"""
        self.news_entries = entries
        if entries:
            self.current_index = 0
            self.update_display()
            self.timer.start(10000)  # Alterna a cada 10 segundos
        else:
            self.title_label.setText("Não foi possível carregar as notícias.")
    
    def update_display(self):
        """Atualiza a exibição com a notícia atual"""
        if not self.news_entries:
            return
        
        entry = self.news_entries[self.current_index]
        
        self.title_label.setText(entry['title'])
        self.desc_label.setText(entry['description'])
        
        if entry['link']:
            self.link_label.setText(entry['link'])
            self.qr_label.setPixmap(create_qr_code(entry['link']))
            self.link_container.setVisible(True)
        else:
            self.link_container.setVisible(False)
        
        # Carregar a imagem de forma assíncrona
        if entry['image_url']:
            self.image_label.setText("Carregando imagem...")
            
            # Cancelar qualquer download anterior, se existir
            if self.current_image_downloader is not None and self.current_image_downloader.isRunning():
                self.current_image_downloader.terminate()
            
            # Iniciar um novo download
            self.current_image_downloader = ImageDownloader(entry['image_url'])
            self.current_image_downloader.image_ready.connect(self.on_image_ready)
            self.current_image_downloader.start()
        else:
            self.image_label.setText("Sem imagem disponível")
    
    def on_image_ready(self, pixmap):
        """Chamado quando a imagem é baixada"""
        if not pixmap.isNull():
            # Calcular a proporção ideal de 3:4 mantendo o aspecto original
            image_pixmap = pixmap.scaled(
                IMAGE_WIDTH, 
                IMAGE_HEIGHT,
                Qt.AspectRatioMode.KeepAspectRatio,  # Mantém a proporção
                Qt.TransformationMode.SmoothTransformation  # Qualidade alta
            )
            
            # Criar um pixmap de fundo com tamanho e proporção exatos (3:4)
            background = QPixmap(IMAGE_WIDTH, IMAGE_HEIGHT)
            background.fill(QColor("#e0e0e0"))  # Cor de fundo cinza claro
            
            # Criar um painter para desenhar a imagem centralizada no fundo
            painter = QPainter(background)
            # Calcular a posição para centralizar a imagem
            x = (IMAGE_WIDTH - image_pixmap.width()) // 2
            y = (IMAGE_HEIGHT - image_pixmap.height()) // 2
            painter.drawPixmap(x, y, image_pixmap)
            painter.end()
            
            # Definir o pixmap combinado no label
            self.image_label.setPixmap(background)
            # Evitar distorção 
            self.image_label.setScaledContents(False)
        else:
            self.image_label.setText("Não foi possível carregar a imagem")
    
    def next_news(self):
        """Avança para a próxima notícia"""
        if self.news_entries:
            self.current_index = (self.current_index + 1) % len(self.news_entries)
            self.update_display()
    
    def refresh_news(self):
        """Atualiza as notícias"""
        self.downloader = NewsDownloader()
        self.downloader.news_ready.connect(self.on_news_ready)
        self.downloader.start()

class OverlayWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.hex_size = 400
        self.setFixedSize(self.hex_size, self.hex_size)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)  # Permite eventos passarem
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet("background: transparent;")  # Fundo transparente
        self.pos_x = 100
        self.pos_y = 100
        self.dx = 2
        self.dy = 2

        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self.update_position)
        self.anim_timer.start(30)

    def update_position(self):
        self.pos_x += self.dx
        self.pos_y += self.dy

        if self.parent():
            parent_width = self.parent().width()
            parent_height = self.parent().height()
        else:
            parent_width, parent_height = 800, 600

        if self.pos_x <= 0 or self.pos_x + self.hex_size >= parent_width:
            self.dx = -self.dx
            self.pos_x = max(0, min(self.pos_x, parent_width - self.hex_size))
        if self.pos_y <= 0 or self.pos_y + self.hex_size >= parent_height:
            self.dy = -self.dy
            self.pos_y = max(0, min(self.pos_y, parent_height - self.hex_size))

        self.move(self.pos_x, self.pos_y)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        radius = self.hex_size / 2
        center_x, center_y = self.hex_size / 2, self.hex_size / 2
        hexagon = QPolygonF()
        for i in range(6):
            angle_deg = 60 * i - 30
            x = center_x + radius * math.cos(math.radians(angle_deg))
            y = center_y + radius * math.sin(math.radians(angle_deg))
            hexagon.append(QPointF(x, y))

        painter.setBrush(QColor("#1976d2"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(hexagon)

        font = QFont("Arial", 25)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor("white"))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Olá,\nUtilize o mouse\n para navegar\n em nosso \npainel interativo.")


class FullScreenApp(QMainWindow):
    def __init__(self):
        super().__init__()

        # No construtor
        QGuiApplication.instance().installEventFilter(self)
        self.setWindowTitle("Painel Interativo FCT")
        self.showFullScreen()
        self.setMouseTracking(True)  # Ativar rastreamento do mouse

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        menu = QWidget()
        menu_layout = QHBoxLayout(menu)
        menu_layout.setSpacing(20)
        menu.setFixedHeight(60)

        self.btn_home = QPushButton("Notícias FCT")  # Alterado para Notícias
        self.btn_campus = QPushButton("Conheca o Campus")
        self.btn_horarios = QPushButton("Horários de Aulas")
        self.btn_fct_pessoas = QPushButton("Conheça a FCT - Pessoas")
        self.btn_fct_extensao = QPushButton("Conheça a FCT - Ações de Extensão")
        
        for btn in [self.btn_home, self.btn_campus, self.btn_horarios, self.btn_fct_pessoas, self.btn_fct_extensao]:
            menu_layout.addWidget(btn)

        self.content_area = QStackedWidget()
        
        # Painel de notícias
        self.news_carousel = NewsCarousel()
        
        # Área para webview
        self.webview = QWebEngineView()
        
        self.content_area.addWidget(self.news_carousel)
        self.content_area.addWidget(self.webview)
        
        layout.addWidget(menu)
        layout.addWidget(self.content_area)

        self.setStyleSheet("""
            QWidget { background-color: #1a237e; }
            QPushButton {
                background-color: #1976d2; color: white; border: none;
                padding: 10px 20px; font-size: 20px; border-radius: 2px;
            }
            QPushButton:hover { background-color: #2196f3; }
        """)

        self.btn_home.clicked.connect(self.show_news)
        self.btn_campus.clicked.connect(lambda: self.carregar_url("https://prezi.com/view/MZjulFdzyMstq9zoDLVX/"))
        self.btn_horarios.clicked.connect(lambda: self.carregar_url("https://ti-fct.github.io/horariosFCT/"))
        self.btn_fct_pessoas.clicked.connect(lambda: self.carregar_url("https://app.powerbi.com/view?r=eyJrIjoiNjUzMDMzOWUtNzViNS00NGYyLTk1YTYtMWY5MWE5OGI1YzAzIiwidCI6ImIxY2E3YTgxLWFiZjgtNDJlNS05OGM2LWYyZjJhOTMwYmEzNiJ9"))
        self.btn_fct_extensao.clicked.connect(lambda: self.carregar_url("https://app.powerbi.com/view?r=eyJrIjoiMDcyZWQ2NWMtZTVkMy00YzMyLTkyYjQtNzFmMjQ1MzVjZDcwIiwidCI6ImIxY2E3YTgxLWFiZjgtNDJlNS05OGM2LWYyZjJhOTMwYmEzNiJ9"))

        # Mostrar notícias como página inicial
        self.show_news()
        
        self.overlay = OverlayWidget(self)
        self.overlay.hide()  # Inicialmente oculto

        self.lastActivity = QDateTime.currentDateTime()
        self.idle_timer = QTimer(self)
        self.idle_timer.timeout.connect(self.updateOverlayVisibility)
        self.idle_timer.start(1000)  # Verifica a cada segundo

        # Adicionar um filtro de eventos global
        self.installEventFilter(self)
        
        # Timer para atualizar notícias
        self.news_update_timer = QTimer(self)
        self.news_update_timer.timeout.connect(self.refresh_news)
        self.news_update_timer.start(UPDATE_INTERVAL * 1000)  # Converter para milissegundos

    def show_news(self):
        """Mostra o painel de notícias"""
        self.content_area.setCurrentWidget(self.news_carousel)
    
    def show_web(self):
        """Mostra o painel web"""
        self.content_area.setCurrentWidget(self.webview)
    
    def refresh_news(self):
        """Atualiza as notícias"""
        self.news_carousel.refresh_news()

    def eventFilter(self, source, event):
        if event.type() == event.Type.MouseMove:
            self.lastActivity = QDateTime.currentDateTime()
            if self.overlay.isVisible():
                self.overlay.hide()
        return super().eventFilter(source, event)

    def carregar_url(self, url: str):
        """Carrega uma URL no webview e mostra a visualização web"""
        self.webview.load(QUrl(url))
        self.show_web()

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.Close):
           event.ignore()

    def mouseMoveEvent(self, event):
        self.lastActivity = QDateTime.currentDateTime()
        if self.overlay.isVisible():
            self.overlay.hide()
        super().mouseMoveEvent(event)

    def updateOverlayVisibility(self):
        agora = QDateTime.currentDateTime()
        idle_time = self.lastActivity.secsTo(agora)

        if idle_time >= 300:  # 5 minutos
            if not self.overlay.isVisible():
                self.overlay.show()
        else:
            if self.overlay.isVisible():
                self.overlay.hide()

# Classe para gerenciar várias páginas
class QStackedWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.widgets = []
        self.current_index = -1
    
    def addWidget(self, widget):
        """Adiciona um widget à pilha"""
        if self.widgets:
            self.widgets[self.current_index].setVisible(False)
        
        self.widgets.append(widget)
        self.layout.addWidget(widget)
        self.current_index = len(self.widgets) - 1
        widget.setVisible(True)
    
    def setCurrentWidget(self, widget):
        """Define o widget visível atual"""
        if widget in self.widgets:
            if self.current_index >= 0:
                self.widgets[self.current_index].setVisible(False)
            
            self.current_index = self.widgets.index(widget)
            self.widgets[self.current_index].setVisible(True)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FullScreenApp()
    window.show()
    sys.exit(app.exec())