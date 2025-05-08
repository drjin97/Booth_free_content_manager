import sys
import os
# import json # 더 이상 필요 없음 (No longer needed)
# import time # 더 이상 필요 없음 (No longer needed)
import subprocess # 더블 클릭 동작에 필요 (Still needed for double-click action)
import multiprocessing
from PySide6.QtCore import Qt, QDir, QModelIndex, QTimer, QRect, QThreadPool, QSize
from PySide6.QtGui import QColor, QPalette, QFont, QFontDatabase
# BoothManager에 필요한 Qt Widgets 컴포넌트 (Qt Widgets components needed by BoothManager)
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QSplitter, QTreeView, QFileSystemModel, QComboBox,
                             QScrollArea, QGridLayout, QPushButton, QLineEdit, QMessageBox,
                             QTabWidget, QProgressBar, QStyleFactory) # QTabWidget 추가 (Added QTabWidget)

# 새로운 모듈에서 위젯 및 상수 가져오기 (Import widgets and constants from the new module)
from widgets import FolderItemWidget, FileItemWidget, ITEM_WIDGET_WIDTH, HIDDEN_FILES
# 새로운 DataManager 가져오기 (Import the new DataManager)
from data_manager import DataManager

# DownloaderWidget 가져오기 (Import the DownloaderWidget)
from downloader_widget import DownloaderWidget

# No longer needed: inline logging config, decorator, and ThumbnailCache class
from logger_config import handle_exceptions, logger
from thumbnail_cache import ThumbnailCache
from ui_builder import UIBuilder
from constants import (FONT_FAMILY, FONT_SIZE, THEME_COLORS, COMMON_STYLES, 
                      PROGRESS_BAR_STYLE, BORDER_WIDTH) # BORDER_WIDTH 임포트 추가

import platform
from PySide6.QtGui import QFont

def get_scaled_font_size(base_size=24):  # constants.py의 FONT_SIZE를 기본값으로 사용
    if platform.system() == 'Windows':
        # Windows의 경우 DPI 설정에 따라 폰트 크기 조정
        from ctypes import windll
        user32 = windll.user32
        user32.SetProcessDPIAware()
        dpi = user32.GetDpiForSystem()
        # DPI가 96(100%)보다 클 때만 크기 조정
        if dpi > 96:
            return int(base_size * (dpi / 96))
    return base_size

# constants.py의 FONT_SIZE를 사용
from constants import FONT_SIZE as BASE_FONT_SIZE
FONT_SIZE = get_scaled_font_size(BASE_FONT_SIZE)

class BoothManager(QMainWindow):
    """
    Booth 아이템 관리 뷰어 메인 윈도우 클래스입니다.
    UI 설정, 이벤트 처리, 데이터 관리자 및 위젯 연결을 담당합니다.
    (Booth item management viewer main window class.
    Responsible for UI settings, event handling, data manager and widget connection.)
    """
    def __init__(self):
        """BoothManager 초기화 메서드 (BoothManager initialization method)"""
        super().__init__()
        self.setWindowTitle("Hakka Crwaler")
        self.setGeometry(100, 100, 1000, 700)

        # 폰트 설정
        font_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "")
        logger.info(f"폰트 파일 경로: {font_path}")
        try:
            if os.path.exists(font_path):
                logger.info("폰트 파일 존재 확인")
                logger.info(f"폰트 파일 크기: {os.path.getsize(font_path)} bytes")
                
                # 폰트 파일 읽기 테스트
                with open(font_path, 'rb') as f:
                    header = f.read(4)
                    logger.info(f"폰트 파일 헤더: {header.hex()}")
                
                font_id = QFontDatabase.addApplicationFont(font_path)
                logger.info(f"폰트 ID: {font_id}")
                
                if font_id != -1:
                    font_families = QFontDatabase.applicationFontFamilies(font_id)
                    logger.info(f"사용 가능한 폰트 패밀리 목록: {font_families}")
                    
                    if font_families:
                        # 빈 문자열이 아닌 실제 폰트 이름 선택
                        font_family = next((name for name in font_families if name), font_families[0])
                        logger.info(f"로드된 폰트 패밀리: {font_family}")
                        # constants.py의 FONT_FAMILY 업데이트
                        import constants
                        constants.FONT_FAMILY = font_family
                        logger.info(f"constants.FONT_FAMILY 업데이트: {constants.FONT_FAMILY}")
                        
                        app_font = QFont(font_family, FONT_SIZE)
                        app_font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
                        app_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
                        app_font.setWeight(QFont.Weight.Normal)
                        app_font.setKerning(True)

                        # 폰트 크기를 0.5배로 축소 (24px -> 12px 효과)
                        app_font.setPointSizeF(FONT_SIZE * 0.5)

                        QApplication.setFont(app_font)
                        # 초기 스타일시트 설정
                        self.setStyleSheet(f"""
                            QMainWindow, QWidget {{
                                font-family: "{font_family}";
                                font-size: {FONT_SIZE}px;
                            }}
                            QLabel, QPushButton, QLineEdit, QComboBox, QTreeView, QListView {{
                                font-family: "{font_family}";
                                font-size: {FONT_SIZE}px;
                            }}
                        """)
                        logger.info(f"폰트 '{font_family}' 로드 완료")
                    else:
                        logger.error("폰트 패밀리 목록이 비어있습니다.")
                else:
                    logger.error("폰트 로드 실패 (ID: -1)")
            else:
                logger.error(f"폰트 파일을 찾을 수 없음: {font_path}")
        except Exception as e:
            logger.error(f"폰트 로드 중 오류 발생: {str(e)}")

        # 정렬 옵션 정의
        self.sort_options = {
            0: ("이름 (오름차순)", lambda x: x["name"].lower()),
            1: ("이름 (내림차순)", lambda x: x["name"].lower(), True),
            2: ("날짜 (최신순)", lambda x: x["modified_time"], True),
            3: ("날짜 (오래된순)", lambda x: x["modified_time"]),
            4: ("크기 (큰순)", lambda x: x["size"], True),
            5: ("크기 (작은순)", lambda x: x["size"]),
            6: ("유형 (폴더 우선)", lambda x: (not x["is_dir"], x["name"].lower())),
            7: ("유형 (파일 우선)", lambda x: (x["is_dir"], x["name"].lower()))
        }

        # 테마 색상 정의
        self.theme_colors = THEME_COLORS

        # 스레드 풀 초기화 (CPU 코어 수 - 1)
        thread_pool = QThreadPool.globalInstance()
        max_threads = max(1, multiprocessing.cpu_count() - 1)
        thread_pool.setMaxThreadCount(max_threads)
        logger.info(f"스레드 풀 초기화: 최대 {max_threads}개 스레드")

        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.base_path = script_dir
        logger.info(f"Base path set to: {self.base_path}")

        if not os.path.exists(self.base_path):
            try:
                os.makedirs(self.base_path)
                logger.info(f"'{self.base_path}' 폴더를 생성했습니다. (테스트용)")
            except OSError as e:
                logger.error(f"'{self.base_path}' 폴더 생성 실패: {e}")

        self.current_dir_path = self.base_path
        self.current_sort_criteria = 0
        self.current_filter_text = ""

        # DataManager 초기화
        self.data_manager = DataManager(self.base_path)
        
        # 단일 콘텐츠 위젯 설정
        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("background-color: transparent;")

        # 타이머 초기화
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(150)
        self._resize_timer.timeout.connect(self.handle_resize_finished)

        self._lazy_load_timer = QTimer(self)
        self._lazy_load_timer.setSingleShot(True)
        self._lazy_load_timer.setInterval(100)
        self._lazy_load_timer.timeout.connect(self._lazy_load_thumbnails)

        # 썸네일 캐시 초기화
        self.thumbnail_cache = ThumbnailCache()

        # 진행 상태 표시를 위한 변수들
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(PROGRESS_BAR_STYLE)

        # UI 빌더를 사용하여 UI 구성
        ui_builder = UIBuilder(self)
        ui_builder.build_main_ui()

        # 초기 테마 설정
        self.change_theme("white")

        # 스크롤 영역에 content_widget을 설정하는 setup_ui 이후 초기 콘텐츠 표시
        self.display_content(self.current_dir_path)

        # 새로운 초기화 부분에 추가
        if hasattr(Qt, 'AA_EnableHighDpiScaling'):
            QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
            QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    def resizeEvent(self, event):
        """창 크기 조절 이벤트 처리 (Handle window resize event)"""
        # 타이머를 다시 시작하여 디바운싱 (Restart the timer for debouncing)
        self._resize_timer.start()
        super().resizeEvent(event) # 기본 이벤트 처리 호출 (Call base event handler)

    def handle_resize_finished(self):
        """창 크기 조절 완료 후 처리 (Handle after resize is finished)"""
        logger.info("Resize finished, updating content layout.")
        # 현재 경로의 콘텐츠를 다시 표시하여 레이아웃 업데이트 (Re-display content for the current path to update layout)
        self.display_content(self.current_dir_path)

    def _setup_timers(self):
        """Setup timers for resize and lazy loading"""
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(150)
        self._resize_timer.timeout.connect(self.handle_resize_finished)

        self._lazy_load_timer = QTimer(self)
        self._lazy_load_timer.setSingleShot(True)
        self._lazy_load_timer.setInterval(100)
        self._lazy_load_timer.timeout.connect(self._lazy_load_thumbnails)

    def _lazy_load_thumbnails(self):
        """현재 보이는 영역의 썸네일만 로드"""
        if not hasattr(self, 'content_widget') or not self.content_widget.layout():
            return

        viewport_rect = self.scroll_area.viewport().rect()
        viewport_rect.translate(0, self.scroll_area.verticalScrollBar().value())
        
        layout = self.content_widget.layout()
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if not item:
                continue
                
            widget = item.widget()
            if not widget:
                continue

            # 위젯의 위치와 크기 계산
            widget_rect = QRect(widget.pos(), widget.size())
            widget_rect.translate(self.content_widget.pos())
            
            # 위젯이 뷰포트와 겹치는지 확인
            if viewport_rect.intersects(widget_rect):
                if isinstance(widget, (FolderItemWidget, FileItemWidget)):
                    widget.load_thumbnail(self.thumbnail_cache)

    def adjust_brightness(self, hex_color, factor):
        """헥스 코드 색상의 밝기를 조정합니다. (Adjust brightness of a hex color.)"""
        # QColor는 상단에서 임포트됨 (QColor is now imported at the top)
        color = QColor(hex_color)
        h, s, v, a = color.getHsv()
        # v가 정수로 처리되도록 보장 (getHsv usually returns ints)
        new_v = max(0, min(255, int(v * factor)))
        color.setHsv(h, s, new_v, a)
        return color.name()

    def setup_theme_buttons(self):
        """테마 버튼 설정"""
        # 테마 버튼들을 위한 컨테이너 위젯
        theme_container = QWidget()
        theme_layout = QHBoxLayout(theme_container)
        theme_layout.setContentsMargins(0, 0, 0, 0)
        theme_layout.setSpacing(5)
        
        # 테마 버튼 생성
        self.theme_buttons = {}
        for theme_name, colors in self.theme_colors.items():
            btn = QPushButton()
            btn.setFixedSize(24, 24)
            btn.setToolTip(theme_name.capitalize())
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {colors['bg']};
                    border: 1px solid {colors['text']};
                    border-radius: 12px;
                }}
                QPushButton:hover {{
                    border: 2px solid {colors['text']};
                }}
                QPushButton:checked {{
                    border: 2px solid {colors['text']};
                }}
            """)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, t=theme_name: self.change_theme(t))
            self.theme_buttons[theme_name] = btn
            theme_layout.addWidget(btn)
        
        return theme_container

    def change_theme(self, theme_name):
        """테마 변경"""
        theme = self.theme_colors.get(theme_name.lower())
        if theme:
            border_color_for_widgets = theme['handle'] # 테두리 색상을 핸들 색상으로 통일
            current_border_width = BORDER_WIDTH # constants.py에서 가져온 BORDER_WIDTH 사용

            self.setStyleSheet(f"""
                QMainWindow {{
                    background-color: {theme['bg']};
                    color: {theme['text']};
                    border: none; /* QMainWindow 자체의 테두리 제거 */
                }}
                QWidget {{
                    background-color: {theme['bg']};
                    color: {theme['text']};
                    border: none; /* 일반 QWidget의 테두리도 기본적으로 제거 */
                }}
                QTreeView {{
                    background-color: {theme['bg']};
                    color: {theme['text']};
                    border: {current_border_width}px solid {border_color_for_widgets}; /* 핸들 색상 테두리, 지정된 두께 */
                    {COMMON_STYLES['border_radius']} /* constants.py의 BORDER_RADIUS 반영 (0) */
                    {COMMON_STYLES['font']}
                }}
                QTreeView::branch {{
                    background-color: {theme['bg']};
                }}
                QTreeView::item {{
                    background-color: {theme['bg']};
                    color: {theme['text']};
                    {COMMON_STYLES['padding_small']}
                    {COMMON_STYLES['font']}
                }}
                QTreeView::item:selected {{
                    background-color: {border_color_for_widgets};
                    color: {theme['text']};
                }}
                QTreeView::item:hover {{
                    background-color: {theme['bg']};
                    color: {theme['text']};
                }}
                QListView {{
                    background-color: {theme['bg']};
                    color: {theme['text']};
                    border: {current_border_width}px solid {border_color_for_widgets};
                    {COMMON_STYLES['border_radius']}
                    {COMMON_STYLES['font']}
                }}
                QLineEdit {{
                    background-color: {theme['bg']};
                    color: {theme['text']};
                    border: {current_border_width}px solid {border_color_for_widgets};
                    {COMMON_STYLES['border_radius']}
                    {COMMON_STYLES['padding_small']}
                    {COMMON_STYLES['font']}
                }}
                QComboBox {{
                    background-color: {theme['bg']};
                    color: {theme['text']};
                    border: {current_border_width}px solid {border_color_for_widgets};
                    {COMMON_STYLES['border_radius']}
                    {COMMON_STYLES['padding_small']}
                    {COMMON_STYLES['font']}
                }}
                QPushButton {{
                    background-color: {theme['bg']};
                    color: {theme['text']};
                    border: {current_border_width}px solid {border_color_for_widgets};
                    {COMMON_STYLES['border_radius']}
                    {COMMON_STYLES['padding_small']}
                    {COMMON_STYLES['font']}
                }}
                QLabel {{
                    background-color: {theme['bg']};
                    color: {theme['text']};
                    {COMMON_STYLES['font']}
                }}
                QTabWidget {{ /* QTabWidget 자체에 대한 스타일 추가 */
                    border: none; /* QTabWidget 자체의 테두리 제거 */
                }}
                QTabWidget::pane {{
                    border: {current_border_width}px solid {border_color_for_widgets}; /* 핸들 색상 테두리, 지정된 두께 */
                    {COMMON_STYLES['border_radius']} /* constants.py의 BORDER_RADIUS 반영 (0) */
                    background-color: {theme['bg']};
                    color: {theme['text']};
                    {COMMON_STYLES['font']}
                }}
                QTabBar::tab {{
                    background-color: {theme['bg']};
                    color: {theme['text']};
                    border: {current_border_width}px solid {border_color_for_widgets};
                    border-bottom-color: transparent; /* 선택되지 않은 탭의 아래쪽 테두리는 투명하게 하여 pane과 연결되도록 */
                    /* border-radius: 5px 5px 0 0; */ /* 라운딩 제거, constants.py의 BORDER_RADIUS가 0이므로 COMMON_STYLES 사용 시 자동 적용 */
                    {COMMON_STYLES['border_radius']} /* 상단 좌우만 라운딩이 필요한 경우 별도 지정 필요하나, 여기서는 전체 0 */
                    {COMMON_STYLES['padding_medium']}
                    {COMMON_STYLES['margin_small']}
                    {COMMON_STYLES['font']}
                }}
                QTabBar::tab:selected {{
                    background-color: {border_color_for_widgets}; /* 선택된 탭 배경은 핸들 색상 */
                    color: {theme['bg']}; /* 선택된 탭 텍스트는 배경색과 대비되도록 */
                    border-bottom-color: {border_color_for_widgets}; /* 선택된 탭은 아래쪽 테두리도 핸들 색상 */
                }}
                QScrollArea {{
                    background-color: {theme['bg']};
                    border: none; /* 스크롤 영역 자체는 테두리 없음. 내용(pane)이 테두리를 가짐 */
                    {COMMON_STYLES['font']}
                }}
                QScrollBar:vertical, QScrollBar:horizontal {{
                    background-color: {theme['bg']};
                    border: none;
                    {COMMON_STYLES['font']}
                }}
                QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
                    background-color: {border_color_for_widgets};
                    /* border-radius: 3px; */ /* 라운딩 제거, COMMON_STYLES 사용 시 자동 적용 또는 직접 0px */
                    {COMMON_STYLES['border_radius']}
                    min-height: 20px;
                }}
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
                QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                    border: none;
                    background: none;
                }}
                QSplitter {{
                    background-color: transparent; /* 스플리터 자체 배경을 투명하게 */
                    border: none;
                }}
                QSplitter::handle {{
                    background: {theme['handle']};
                    background-color: {theme['handle']};
                    width: {current_border_width}px; /* 핸들 너비를 BORDER_WIDTH와 동일하게 */
                    /* height: {current_border_width}px; */ /* 핸들이 수평일 경우 높이도 동일하게 설정 가능 */
                }}
                QDialog {{
                    background-color: {theme['bg']};
                    color: {theme['text']};
                    {COMMON_STYLES['font']}
                }}
                QDialog QLineEdit {{
                    background-color: {theme['bg']};
                    color: {theme['text']};
                    border: {current_border_width}px solid {border_color_for_widgets};
                    {COMMON_STYLES['border_radius']}
                    {COMMON_STYLES['padding_small']}
                    {COMMON_STYLES['font']}
                }}
                QDialog QPushButton {{
                    background-color: {theme['bg']};
                    color: {theme['text']};
                    border: {current_border_width}px solid {border_color_for_widgets};
                    {COMMON_STYLES['border_radius']}
                    {COMMON_STYLES['padding_small']}
                    {COMMON_STYLES['font']}
                }}
            """)
            self.content_widget.setObjectName("content_widget")
            if hasattr(self, 'scroll_area'):
                self.scroll_area.setStyleSheet(f"""
                    QScrollArea {{ 
                        background-color: {theme['bg']};
                        border: none;
                    }}
                """)
            if hasattr(self, 'splitter') and self.splitter is not None:
                self.splitter.setStyleSheet(f"""
                    QSplitter {{
                        background-color: transparent;
                        border: none;
                    }}
                    QSplitter::handle {{
                        background: {theme['handle']};
                        background-color: {theme['handle']};
                        width: {current_border_width}px;
                        /* height: {current_border_width}px; */
                    }}
                """)
            # 모든 썸네일/파일/폴더 위젯에 테마 적용
            self.apply_theme_to_all_content_widgets(theme['bg'], theme['text'])

    def apply_theme_to_all_content_widgets(self, bg_color, text_color):
        if not hasattr(self, 'content_widget') or not self.content_widget.layout():
            return
        layout = self.content_widget.layout()
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if not item:
                continue
            widget = item.widget()
            if widget and hasattr(widget, 'apply_theme'):
                widget.apply_theme(bg_color, text_color)

    def apply_filter_sort(self):
        """필터 및 정렬 변경 시 현재 디렉토리 콘텐츠 다시 표시 (Re-display current directory content when filter and sort are changed)"""
        self.current_filter_text = self.filter_input.text().strip().lower()
        self.current_sort_criteria = self.sort_combo.currentIndex()
        self.display_content(self.current_dir_path) # 현재 경로 기준으로 다시 그림 (Re-draw based on current path)

    @handle_exceptions
    def on_directory_clicked(self, index: QModelIndex):
        """디렉토리 클릭 시 이벤트 처리 (Event handling on directory click)"""
        file_path = self.file_system_model.filePath(index)
        if not self.file_system_model.isDir(index):
            return

        logger.info(f"Clicked directory: {file_path}")
        self.current_dir_path = file_path # 현재 경로 업데이트 (Update current path)
        # 디렉토리 변경 시 필터/정렬 초기화 또는 유지 (여기서는 유지) (Initialize or maintain filter/sort on directory change (maintained here))
        # self.filter_input.clear()
        # self.sort_combo.setCurrentIndex(0)
        self.display_content(self.current_dir_path)

        # 만약 선택된 것이 폴더라면 트리에서 확장 (If the selected item is a folder, expand it in the tree)
        if os.path.isdir(file_path):
             self.tree_view.expand(index)

    @handle_exceptions
    def display_content(self, dir_path):
        """디렉토리 내용을 필터링, 정렬 및 자동 줄 바꿈하여 표시"""
        self.show_progress()  # 진행 상태 표시 시작
        try:
            logger.info(f"Displaying content for: {dir_path} with filter '{self.current_filter_text}' and sort '{self.current_sort_criteria}'")
            row, col = 0, 0

            # --- 레이아웃 가져오기 또는 생성 --- (Get or create the layout)
            target_layout = self.content_widget.layout()
            if not target_layout:
                logger.info("content_widget에 새 레이아웃 생성 (Creating new layout for content_widget)")
                target_layout = QGridLayout()
                self.content_widget.setLayout(target_layout)
                target_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            # 레이아웃이 존재하는지 확인 (Ensure layout exists)
            if not isinstance(target_layout, QGridLayout):
                 logger.error(f"오류: 레이아웃이 QGridLayout이 아님 ({type(target_layout)}). 다시 생성합니다. (Error: Layout is not a QGridLayout ({type(target_layout)}). Recreating.)")
                 if target_layout: del target_layout # 기존 레이아웃 객체 먼저 제거 (Remove old layout object first)
                 target_layout = QGridLayout()
                 self.content_widget.setLayout(target_layout)
                 target_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

            # DataManager를 사용하여 아이템 가져오기 (Use DataManager to get items)
            items_to_display = self.data_manager.get_items_in_directory(
                dir_path,
                self.current_sort_criteria,
                self.current_filter_text
            )

            if items_to_display is None: # DataManager에서 잘못된 경로 또는 오류 처리 (Handle invalid path or error from DataManager)
                 logger.error(f"DataManager에서 오류 또는 잘못된 경로: {dir_path}")
                 # 기존 레이아웃을 지우고 오류 라벨을 레이아웃에 추가 (Clear the existing layout and add an error label TO THE LAYOUT)
                 while target_layout.count():
                     item = target_layout.takeAt(0)
                     widget = item.widget()
                     if widget:
                         widget.deleteLater()
                 error_label = QLabel(f"잘못된 경로이거나 데이터를 불러올 수 없습니다:\n{dir_path}")
                 error_label.setAlignment(Qt.AlignCenter)
                 error_label.setStyleSheet("padding: 20px; color: red;")
                 error_label.setWordWrap(True)
                 target_layout.addWidget(error_label, 0, 0)
                 return

            # 정렬 옵션 적용
            sort_func = self.sort_options[self.current_sort_criteria][1]
            reverse = len(self.sort_options[self.current_sort_criteria]) > 2 and self.sort_options[self.current_sort_criteria][2]
            items_to_display.sort(key=sort_func, reverse=reverse)

            # 4. 너비에 따라 열 개수 계산 (Calculate Columns based on Width)
            if self.scroll_area.widget() != self.content_widget:
                 logger.warning("경고: content_widget이 scroll_area에 설정되지 않았습니다. 지금 설정합니다. (Warning: content_widget not set in scroll_area, setting it now.)")
                 self.scroll_area.setWidget(self.content_widget)

            viewport_width = self.scroll_area.viewport().width()
            item_width = ITEM_WIDGET_WIDTH # 임포트된 상수 사용 (Use imported constant)
            spacing = target_layout.spacing() if target_layout else 10 # 레이아웃 간격 또는 기본값 사용 (Use layout spacing or default)
            col_count = max(1, int(viewport_width / (item_width + spacing)))
            logger.info(f"Viewport width: {viewport_width}, Item width: {item_width}, Spacing: {spacing}, Calculated columns: {col_count}")

            # 5. 새 위젯 먼저 생성 (임포트된 위젯 클래스 사용) (Create new widgets first (Using imported widget classes))
            new_widgets = []
            for item_info in items_to_display:
                try:
                    # 부모는 항상 단일 content_widget (Parent is always the single content_widget)
                    parent_widget = self.content_widget
                    item_widget = None
                    if item_info["is_dir"]:
                        item_widget = FolderItemWidget(item_info["path"], item_info["name"], parent=parent_widget)
                        item_widget.item_double_clicked.connect(self.select_tree_item) # 폴더 더블클릭 연결 (Connect folder double-click)
                    else:
                        item_widget = FileItemWidget(item_info["path"], item_info["name"], parent=parent_widget)
                        # 파일 더블클릭은 BaseItemWidget에서 처리 (파인더 열기) (File double-click is handled in BaseItemWidget (open in Finder))

                    if item_widget:
                        new_widgets.append(item_widget) # 임시 리스트에 추가 (Add to temporary list)
                except Exception as widget_e:
                     logger.error(f"{item_info.get('path', 'N/A')}에 대한 위젯 생성 오류: {widget_e}")
                     # 선택적으로 실패한 위젯마다 메시지 박스 표시 또는 오류 수집 (Optionally show a message box per failed widget, or collect errors)
                     QMessageBox.warning(self, "위젯 생성 오류", f"항목 위젯 생성 중 오류 발생:\n{item_info.get('name', 'N/A')}\n{widget_e}")

            # 6. 새 위젯 생성 후 기존 레이아웃 비우기 (Clear existing layout AFTER creating new widgets)
            # 새 항목을 추가하기 전에 깨끗한 상태를 보장합니다. (This ensures a clean slate before adding the new items.)
            # deleteLater()를 사용하는 것이 안전한 위젯 제거에 중요합니다. (Using deleteLater() is important for safe widget removal.)
            if target_layout:
                while target_layout.count():
                    layout_item = target_layout.takeAt(0)
                    widget = layout_item.widget()
                    if widget:
                        widget.setParent(None) # 삭제 전에 명시적으로 부모 제거 (Explicitly remove parent before deleting)
                        widget.deleteLater()
            else:
                 # 이 경우는 위의 검사로 인해 발생하지 않아야 하지만, 발생하면 기록합니다. (This case should ideally not happen due to checks above, but log if it does.)
                 logger.error("오류: 새 위젯을 추가하기 전에 target_layout이 유효하지 않게 되었습니다. (Error: target_layout became invalid before adding new widgets.)")

            # 7. 이제 비어 있는 레이아웃에 새 위젯 추가 (Add new widgets to the now empty layout)
            row, col = 0, 0 # 행/열 초기화 (Reset row/col)
            for item_widget in new_widgets:
                 # 계산된 열 개수를 기반으로 줄 바꿈하여 그리드 레이아웃에 위젯 추가 (Add widget to the grid layout, wrapping based on calculated col_count)
                 target_layout.addWidget(item_widget, row, col)
                 col += 1
                 if col >= col_count:
                     col = 0
                     row += 1

            # 레이아웃이 지원하는 경우 항목을 왼쪽 상단으로 밀어 넣기 위해 끝에 늘이기 추가 (Add stretch at the end to push items to the top-left if layout supports it)
            # QGridLayout은 QVBoxLayout/QHBoxLayout처럼 늘이기를 사용하지 않음 (QGridLayout doesn't really use stretch like QVBoxLayout/QHBoxLayout)
            # target_layout.setRowStretch(row + 1, 1)
            # target_layout.setColumnStretch(col_count, 1)

            # 초기 지연 로딩 시작
            self._lazy_load_timer.start()

        except Exception as e:
            logger.error(f"{dir_path}에 대한 콘텐츠 표시 오류: {e}")
            # 오류 처리: QMessageBox를 기본 방법으로 사용하고 scroll_area 위젯은 건드리지 않음 (Error handling: Use QMessageBox as the primary method, avoid touching scroll_area widget)
            try:
                QMessageBox.critical(self, "콘텐츠 표시 오류", f"콘텐츠 표시 중 오류 발생:\n{e}\n경로: {dir_path}")
            except Exception as msg_e:
                 logger.error(f"심각한 오류 메시지 상자 표시 실패: {msg_e}")
            # 선택적으로, 주 프로세스 중 오류가 발생한 경우 레이아웃을 다시 비우기 시도 (Optionally, clear the layout again defensively here if needed)
            # 예외 발생 전 부분적으로 렌더링된 콘텐츠가 UI에 표시되지 않도록 함 (This ensures the UI doesn't show partially rendered content from before the exception)
            try:
                target_layout = self.content_widget.layout() # 레이아웃 다시 가져오기 (Get the layout again)
                if target_layout:
                     logger.info("예외 처리 중 레이아웃 비우기. (Clearing layout due to exception during display_content.)")
                     while target_layout.count():
                        layout_item = target_layout.takeAt(0)
                        widget = layout_item.widget()
                        if widget:
                            # widget.setParent(None) # deleteLater와 함께 사용하면 엄밀히 불필요 (Not strictly necessary with deleteLater)
                            widget.deleteLater() # 삭제 예약 (Schedule deletion)
            except Exception as clear_err:
                logger.error(f"예외 처리 중 레이아웃 비우기 오류: {clear_err}")
        finally:
            self.hide_progress()  # 진행 상태 표시 종료

    @handle_exceptions
    def select_tree_item(self, item_path): # item_path는 폴더 또는 파일 경로일 수 있음 (item_path can be a folder or file path)
        """트리 아이템 선택 및 해당 콘텐츠 표시 (Select tree item and display corresponding content)"""
        logger.info(f"트리 아이템 선택 시도: {item_path}")
        index = self.file_system_model.index(item_path)
        if index.isValid():
            logger.info(f"{item_path}에 대한 유효한 인덱스 찾음 (Found valid index for: {item_path})")
            parent_index = index.parent()
            if parent_index.isValid():
                self.tree_view.expand(parent_index)

            self.tree_view.scrollTo(index, QTreeView.ScrollHint.PositionAtCenter)
            self.tree_view.setCurrentIndex(index)
            # self.tree_view.expand(index) # 폴더가 아닐 수도 있으므로 무조건 확장은 제거 (Remove unconditional expansion as it may not be a folder)

            # 트리 선택 시에도 현재 경로 업데이트 및 콘텐츠 표시 (Update current path and display content even on tree selection)
            self.current_dir_path = os.path.dirname(item_path) if not os.path.isdir(item_path) else item_path
            self.display_content(self.current_dir_path)

            # 만약 선택된 것이 폴더라면 트리에서 확장 (If the selected item is a folder, expand it in the tree)
            if os.path.isdir(item_path):
                 self.tree_view.expand(index)

        else:
            logger.warning(f"{item_path}에 대한 유효한 인덱스를 찾을 수 없습니다. (Could not find a valid index for: {item_path})")

    @handle_exceptions
    def search_by_tags(self):
        """태그로 검색 (Search by tags)"""
        search_text = self.search_input.text().strip()
        if not search_text:
            # 검색어가 없으면 현재 선택된 트리 아이템 또는 루트의 내용을 다시 표시 (If there is no search term, re-display the contents of the currently selected tree item or root)
            self.apply_filter_sort() # 필터/정렬 적용하여 현재 디렉토리 다시 로드 (Apply filter/sort and reload current directory)
            return

        search_tags = {tag.strip().lower() for tag in search_text.split(',') if search_text.strip()}
        logger.info(f"태그 검색: {search_tags}")

        # DataManager를 사용하여 태그로 아이템 찾기 (Use DataManager to find items by tags)
        matching_item_paths = self.data_manager.find_items_by_tags(search_tags)
        logger.info(f"태그와 일치하는 {len(matching_item_paths)}개의 아이템 찾음. (Found {len(matching_item_paths)} items matching tags.)")

        self.display_search_results(matching_item_paths) # 검색 결과 표시 (별도 함수) (Display search results (separate function))

    # Removed find_items_by_tags method from BoothManager as it's now in DataManager

    @handle_exceptions
    def display_search_results(self, item_paths):
        """검색 결과(폴더 경로 리스트)를 썸네일 뷰에 표시 (Display search results (list of folder paths) in the thumbnail view)"""
        logger.info(f"아이템 {len(item_paths)}개에 대한 검색 결과 표시. (Displaying search results for {len(item_paths)} items.)")

        # 단일 content_widget 사용 (Use the single content_widget)
        target_widget = self.content_widget

        # content_widget이 스크롤 영역에 설정되었는지 확인 (Ensure the content_widget is set in the scroll_area)
        if self.scroll_area.widget() != target_widget:
             logger.warning("경고: 검색 결과에 대해 content_widget이 scroll_area에 설정되지 않았습니다. 지금 설정합니다. (Warning: content_widget not set in scroll_area for search results, setting it now.)")
             self.scroll_area.setWidget(target_widget)

        # --- 레이아웃 가져오기 또는 생성 --- (Get or create the layout)
        target_layout = target_widget.layout()
        if not target_layout:
            logger.info("검색 결과에서 content_widget에 대한 새 레이아웃 생성 (Creating new layout for content_widget in search results)")
            target_layout = QGridLayout()
            target_widget.setLayout(target_layout)
            target_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        if not isinstance(target_layout, QGridLayout):
             logger.error(f"오류: 검색 결과에서 레이아웃이 QGridLayout이 아님 ({type(target_layout)}). 다시 생성합니다. (Error: Layout is not a QGridLayout ({type(target_layout)}) in search results. Recreating.)")
             if target_layout: del target_layout
             target_layout = QGridLayout()
             target_widget.setLayout(target_layout)
             target_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        # ---

        # 새 위젯 먼저 생성 (Create new widgets first)
        new_search_widgets = []
        for item_path in item_paths: # item_paths는 폴더 경로 리스트 (item_paths is a list of folder paths)
            try:
                item_folder_name = os.path.basename(item_path)
                # 부모는 단일 content_widget (Parent is the single content_widget)
                item_widget = FolderItemWidget(item_path, item_folder_name, parent=target_widget)
                item_widget.item_double_clicked.connect(self.select_tree_item) # 검색 결과 클릭 시 트리 선택 (Connect tree selection on search result click)
                new_search_widgets.append(item_widget)
            except Exception as search_widget_e:
                 logger.error(f"{item_path}에 대한 검색 결과 위젯 생성 오류: {search_widget_e}")
                 QMessageBox.warning(self, "검색 위젯 생성 오류", f"검색 결과 위젯 생성 중 오류 발생:\n{os.path.basename(item_path)}\n{search_widget_e}")

        # 새 검색 결과 위젯 생성 후 기존 레이아웃 비우기 (Clear existing layout AFTER creating new search result widgets)
        if target_layout:
            while target_layout.count():
                layout_item = target_layout.takeAt(0)
                widget = layout_item.widget()
                if widget:
                    widget.setParent(None) # 명시적으로 부모 제거 (Explicitly remove parent)
                    widget.deleteLater()
        else:
             # 이 경우는 위의 검사로 인해 발생하지 않아야 하지만, 발생하면 기록합니다. (This case should ideally not happen due to checks above, but log if it does.)
             logger.error("오류: 검색 결과를 추가하기 전에 target_layout이 유효하지 않게 되었습니다. (Error: target_layout became invalid before adding search results.)")

        # 이제 비어 있는 레이아웃에 새 위젯 또는 "검색 결과 없음" 라벨 추가 (Add new widgets or "No results" label to the now empty layout)
        if not new_search_widgets:
            # 고정 스타일로 "검색 결과 없음" 라벨 추가 (Add "No results" label with fixed style)
            no_results_label = QLabel("검색 결과 없음")
            no_results_label.setStyleSheet("padding: 20px; color: gray;") # 고정 스타일 사용 (Use fixed style)
            no_results_label.setAlignment(Qt.AlignCenter)
            target_layout.addWidget(no_results_label, 0, 0)
        else:
            # 현재 너비를 기준으로 열 개수 계산 (검색 결과에도 적용) (Calculate columns based on current width for search results too)
            viewport_width = self.scroll_area.viewport().width()
            item_width = ITEM_WIDGET_WIDTH # 임포트된 상수 사용 (Use imported constant)
            spacing = target_layout.spacing() if target_layout else 10 # 레이아웃 간격 또는 기본값 사용 (Use layout spacing or default)
            col_count = max(1, int(viewport_width / (item_width + spacing)))
            row, col = 0, 0

            for item_widget in new_search_widgets: # These are already FolderItemWidget instances
                target_layout.addWidget(item_widget, row, col)
                col += 1

    def show_progress(self, show=True):
        """진행 상태 표시줄 표시/숨김"""
        self.progress_bar.setVisible(show)
        if show:
            self.progress_bar.setRange(0, 0)  # 무한 진행 상태

    def hide_progress(self):
        """진행 상태 표시줄 숨김"""
        self.progress_bar.setVisible(False)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BoothManager()
    window.show()
    sys.exit(app.exec())
