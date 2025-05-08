import os
import json
import subprocess
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QDialog,
                             QLineEdit, QDialogButtonBox, QMessageBox, QSizePolicy)
from PySide6.QtCore import Qt, QSize, Signal, QMimeData, QPoint, QUrl, QThreadPool, QRunnable, QObject
from PySide6.QtGui import QPixmap, QDrag, QFontMetrics, QColor, QImage, QPainter, QPainterPath
from PIL import Image
import sys

# --- 상수 정의 ---
THUMBNAIL_WIDTH = 120  # 썸네일 너비 축소
THUMBNAIL_HEIGHT = 120 # 썸네일 높이 축소
ITEM_WIDGET_WIDTH = 160 # 아이템 위젯 너비 축소
ITEM_WIDGET_HEIGHT = 200 # 아이템 위젯 높이 축소

HIDDEN_FILES = {'.DS_Store', 'Thumbs.db'} # 숨김 처리할 파일 목록

# 태그 버튼 스타일 시트
TAG_BUTTON_STYLE = """
    QPushButton {
        padding: 2px 5px;
        background-color: #e0e0e0; /* Light gray background */
        border: 1px solid #b0b0b0; /* Slightly darker border */
        border-radius: 3px;
    }
    QPushButton:hover {
        background-color: #d0d0d0;
    }
    QPushButton:pressed {
        background-color: #c0c0c0;
    }
"""
# 이미지 라벨 기본 스타일 (썸네일 로드 전)
IMAGE_LABEL_STYLE = """
    QLabel {
        border: 1px solid lightgray;
        background-color: #f0f0f0;
        border-radius: 10px;
    }
"""
# 이미지 라벨 스타일 (썸네일 로드 후)
IMAGE_LABEL_STYLE_LOADED = """
    QLabel {
        border: 1px solid lightgray;
        border-radius: 10px;
    }
"""
# --- 상수 정의 끝 ---

class TagEditDialog(QDialog):
    """태그 편집을 위한 간단한 다이얼로그 클래스"""
    def __init__(self, current_tags, parent=None, theme_name="white"):
        super().__init__(parent)
        from constants import THEME_COLORS, COMMON_STYLES
        self.theme_name = theme_name
        self.theme_colors = THEME_COLORS
        self.common_styles = COMMON_STYLES
        self.setWindowTitle("태그 편집")
        self.setMinimumWidth(300) # 최소 너비 설정

        layout = QVBoxLayout(self) # 수직 레이아웃

        # 태그 입력 필드
        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("쉼표(,)로 구분하여 태그 입력")
        if current_tags: # 기존 태그가 있으면 표시
            self.tags_input.setText(", ".join(current_tags))
        layout.addWidget(self.tags_input)

        # 확인/취소 버튼 박스
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept) # 확인 버튼 시그널 연결
        button_box.rejected.connect(self.reject) # 취소 버튼 시그널 연결
        layout.addWidget(button_box)

        self.set_theme(self.theme_name)

    def set_theme(self, theme_name):
        theme = self.theme_colors.get(theme_name, self.theme_colors["white"])
        border = theme.get('border', theme['text'])
        self.setAutoFillBackground(True)
        if self.layout():
            self.layout().setContentsMargins(0, 0, 0, 0)
        # 블랙 테마일 때 버튼 hover/pressed 색상
        btn_hover = '#444444' if theme_name == 'black' else '#d0d0d0'
        btn_pressed = '#222222' if theme_name == 'black' else '#c0c0c0'
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {theme['bg']};
                color: {theme['text']};
                {self.common_styles['font']}
            }}
            QDialog > QWidget {{
                background-color: {theme['bg']};
                color: {theme['text']};
            }}
            QLineEdit {{
                background-color: {theme['bg']};
                color: {theme['text']};
                {self.common_styles['border']} {border};
                {self.common_styles['border_radius']}
                {self.common_styles['padding_small']}
                {self.common_styles['font']}
            }}
            QLabel {{
                background-color: {theme['bg']};
                color: {theme['text']};
                {self.common_styles['font']}
            }}
            QDialogButtonBox {{
                background-color: {theme['bg']};
                color: {theme['text']};
            }}
        """)
        # QDialogButtonBox의 버튼에 직접 스타일 적용
        for child in self.findChildren(QDialogButtonBox):
            for btn in child.findChildren(QPushButton):
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {theme['bg']};
                        color: {theme['text']};
                        {self.common_styles['border']} {border};
                        {self.common_styles['border_radius']}
                        {self.common_styles['padding_small']}
                        {self.common_styles['font']}
                    }}
                    QPushButton:hover {{
                        background-color: {btn_hover};
                    }}
                    QPushButton:pressed {{
                        background-color: {btn_pressed};
                    }}
                """)

    def get_tags(self):
        """입력된 태그 문자열을 파싱하여 태그 리스트로 반환"""
        tags_text = self.tags_input.text().strip() # 입력값 가져오기 및 공백 제거
        if not tags_text: # 입력값이 없으면 빈 리스트 반환
            return []
        # 쉼표로 구분하고 각 태그의 앞뒤 공백 제거, 빈 태그 제외
        tags = [tag.strip() for tag in tags_text.split(',') if tag.strip()]
        # 중복 제거 및 정렬 후 반환
        return sorted(list(set(tags)))

# 썸네일 생성 워커 클래스
class ThumbnailWorker(QRunnable):
    def __init__(self, path, widget, thumbnail_cache=None, cache_key=None):
        super().__init__()
        self.path = path
        self.widget = widget
        self.thumbnail_cache = thumbnail_cache
        self.cache_key = cache_key or path
        self.signals = ThumbnailSignals()

    def run(self):
        try:
            if not os.path.exists(self.path):
                return

            ext = os.path.splitext(self.path)[1].lower()
            if ext in {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}:
                image = QImage(self.path)
                if not image.isNull():
                    if self.thumbnail_cache:
                        self.thumbnail_cache.set(self.cache_key, image)
                    self.signals.finished.emit(self.widget.path, image)
            else:
                file_icon = QImage(THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT, QImage.Format_ARGB32)
                file_icon.fill(Qt.transparent)
                file_icon.fill(Qt.white)
                if self.thumbnail_cache:
                    self.thumbnail_cache.set(self.cache_key, file_icon)
                self.signals.finished.emit(self.widget.path, file_icon)
        except Exception as e:
            print(f"썸네일 생성 오류 ({self.path}): {e}")
            error_icon = QImage(THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT, QImage.Format_ARGB32)
            error_icon.fill(Qt.red)
            self.signals.finished.emit(self.widget.path, error_icon)

class ThumbnailSignals(QObject):
    finished = Signal(str, QImage)  # path, image

class RoundedImageLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(IMAGE_LABEL_STYLE)
        self.setAlignment(Qt.AlignCenter)

    def setPixmap(self, pixmap):
        if pixmap.isNull():
            super().setPixmap(pixmap)
            return

        # 원본 이미지 크기 유지하면서 라운드 처리
        rounded_pixmap = QPixmap(pixmap.size())
        rounded_pixmap.fill(Qt.transparent)

        painter = QPainter(rounded_pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        path = QPainterPath()
        path.addRoundedRect(0, 0, pixmap.width(), pixmap.height(), 10, 10)
        painter.setClipPath(path)
        
        painter.drawPixmap(0, 0, pixmap)
        painter.end()

        super().setPixmap(rounded_pixmap)

class BaseItemWidget(QWidget):
    """
    기본 아이템 위젯 클래스: 폴더 및 파일 위젯의 공통 기능을 정의
    """
    item_double_clicked = Signal(str) # 아이템 더블 클릭 시 발생하는 시그널 (아이템 경로 전달)

    def __init__(self, path, name, parent=None):
        """
        BaseItemWidget 초기화

        Args:
            path (str): 아이템의 전체 경로
            name (str): 표시될 아이템 이름
            parent (QWidget, optional): 부모 위젯. Defaults to None.
        """
        super().__init__(parent)
        self.path = path # 아이템 경로 저장
        self.name = name # 아이템 이름 저장
        self.thumbnail_loaded = False
        self.tags = [] # 태그 리스트 초기화
        self.thumbnail_worker = None

        self.setFixedSize(ITEM_WIDGET_WIDTH, ITEM_WIDGET_HEIGHT) # 위젯 크기 고정 (상수 사용)
        layout = QVBoxLayout(self) # 수직 레이아웃
        layout.setContentsMargins(5, 5, 5, 5) # 내부 여백 설정
        layout.setSpacing(5) # 위젯 간 간격 설정

        # 이미지 표시 라벨 (RoundedImageLabel 사용)
        self.thumbnail_label = RoundedImageLabel()
        self.thumbnail_label.setFixedSize(THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT)
        layout.addWidget(self.thumbnail_label)

        # 아이템 이름 표시 라벨
        self.name_label = QLabel(self.name)
        self.name_label.setAlignment(Qt.AlignCenter) # 가운데 정렬
        self.name_label.setWordWrap(True) # 자동 줄 바꿈 활성화
        self.name_label.setStyleSheet("color: black;") # 텍스트 색상 설정
        layout.addWidget(self.name_label)

        # --- 태그 섹션 ---
        tags_layout = QHBoxLayout() # 태그 버튼과 라벨을 위한 수평 레이아웃
        tags_layout.setSpacing(3) # 버튼과 라벨 사이 간격

        # 태그 편집 버튼
        self.edit_tags_button = QPushButton("태그") # 버튼 텍스트 변경
        self.edit_tags_button.setToolTip("태그 편집") # 마우스 호버 시 툴팁 표시
        self.edit_tags_button.clicked.connect(self.edit_tags) # 클릭 시 edit_tags 메서드 연결
        self.edit_tags_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed) # 버튼 크기 고정
        self.edit_tags_button.setStyleSheet(TAG_BUTTON_STYLE) # 태그 버튼 스타일 적용 (상수 사용)
        tags_layout.addWidget(self.edit_tags_button)

        # 태그 표시 라벨
        self.tags_label = QLabel("없음") # 초기 텍스트 ("태그: " 접두사 제거)
        self.tags_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter) # 왼쪽 및 수직 가운데 정렬
        self.tags_label.setWordWrap(False) # 자동 줄 바꿈 비활성화 (길면 ...으로 표시)
        tags_layout.addWidget(self.tags_label, 1) # 라벨이 남은 공간을 채우도록 설정

        layout.addLayout(tags_layout) # 태그 섹션 레이아웃 추가
        # --- 태그 섹션 끝 ---

        layout.addStretch() # 하단에 공간 추가하여 위젯들을 위로 밀어 올림

        # 초기화 시 썸네일 및 태그 로드
        self.load_thumbnail()
        self.load_tags()
        self.drag_start_position = None # 드래그 시작 위치 초기화

    def mousePressEvent(self, event):
        """마우스 왼쪽 버튼 클릭 시 드래그 시작 위치를 기록합니다."""
        if event.button() == Qt.LeftButton:
            # QApplication.startDragDistance()를 사용하는 것이 이상적이나, 여기서 직접 접근 어려움.
            # 기본 동작에 의존하거나 필요시 QApplication 인스턴스 전달 필요.
            self.drag_start_position = event.pos() # 현재 마우스 위치 저장
        super().mousePressEvent(event) # 부모 클래스의 이벤트 처리 호출

    def mouseMoveEvent(self, event):
        """마우스 이동 시 드래그 시작 조건을 확인하고 드래그 앤 드롭을 시작합니다."""
        # 왼쪽 버튼이 눌린 상태가 아니면 무시
        if not (event.buttons() & Qt.LeftButton):
            return
        # 드래그 시작 위치가 기록되지 않았으면 무시
        if not self.drag_start_position:
            return
        # 일정 거리 이상 이동했는지 확인 (기본값 사용)
        # QApplication.startDragDistance() 사용이 이상적
        if (event.pos() - self.drag_start_position).manhattanLength() < 10: # 기본 거리 (10 픽셀)
            return

        print(f"드래그 시작: {self.path}")

        drag = QDrag(self) # 드래그 객체 생성
        mime_data = QMimeData() # MIME 데이터 객체 생성 (드래그 데이터 저장)

        # 로컬 파일 URL 생성 및 MIME 데이터에 설정
        url = QUrl.fromLocalFile(self.path)
        mime_data.setUrls([url])
        mime_data.setText(self.path) # 호환성을 위해 텍스트 데이터도 설정

        drag.setMimeData(mime_data) # 드래그 객체에 MIME 데이터 설정

        # 드래그 시 표시될 아이콘 설정 (썸네일 사용)
        pixmap = self.thumbnail_label.pixmap()
        if pixmap and not pixmap.isNull():
            # 드래그 아이콘 크기 조정
            drag_pixmap = pixmap.scaled(QSize(80, 80), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            drag.setPixmap(drag_pixmap)
            # 드래그 아이콘의 핫스팟(마우스 포인터 위치)을 중앙으로 설정
            drag.setHotSpot(QPoint(drag_pixmap.width() // 2, drag_pixmap.height() // 2))
        else:
            # 썸네일이 없는 경우 (예: 이미지 파일 아님) 대체 아이콘 설정 가능
            # 위젯 자체를 렌더링하거나 기본 아이콘 사용 등
            pass

        # 드래그 작업 실행 (복사 또는 이동 허용)
        result = drag.exec(Qt.CopyAction | Qt.MoveAction)

        # 드래그 결과 처리 (선택 사항)
        if result == Qt.MoveAction:
            print("드래그 결과: 이동 (선택적 처리)")
            # 이동 성공 시 원본 뷰 업데이트 필요할 수 있음
        elif result == Qt.CopyAction:
            print("드래그 결과: 복사")
        else:
            print("드래그 취소 또는 실패")

        self.drag_start_position = None # 드래그 시작 위치 초기화

    def mouseDoubleClickEvent(self, event):
        """마우스 더블 클릭 시 아이템을 열거나 선택하는 이벤트 처리"""
        if event.button() == Qt.LeftButton:
            print(f"아이템 더블 클릭: {self.path}")
            # 운영체제 기본 탐색기에서 아이템 열기/선택
            if os.path.exists(self.path):
                try:
                    if os.path.isdir(self.path):
                        # 폴더는 탐색기에서 열지 않음 (필요시 주석 해제)
                        # subprocess.Popen(['open', self.path]) # macOS
                        # subprocess.Popen(['explorer', self.path]) # Windows
                        pass # 폴더 더블클릭 시 아무 작업 안 함 (트리 뷰에서 처리)
                    else:
                        # 운영체제에 따라 적절한 명령어 선택
                        if sys.platform == 'win32':
                            # Windows: explorer /select, "파일경로"
                            subprocess.Popen(['explorer', '/select,', os.path.normpath(self.path)])
                        elif sys.platform == 'darwin':
                            # macOS: open -R "파일경로"
                            subprocess.Popen(['open', '-R', self.path])
                        else:
                            # Linux: xdg-open "파일경로"
                            subprocess.Popen(['xdg-open', self.path])
                except Exception as e:
                    print(f"탐색기에서 아이템 열기/선택 오류: {e}")
            # 트리 뷰 선택을 위한 시그널 발생
            self.item_double_clicked.emit(self.path)
        super().mouseDoubleClickEvent(event) # 부모 클래스의 이벤트 처리 호출

    def load_thumbnail(self, thumbnail_cache=None):
        """썸네일 로드 (지연 로딩 지원)"""
        if self.thumbnail_loaded:
            return

        # 캐시에서 먼저 확인
        if thumbnail_cache:
            cached_image = thumbnail_cache.get(self.path)
            if cached_image:
                self.set_thumbnail(cached_image)
                self.thumbnail_loaded = True
                return

        # 캐시에 없으면 새로 생성 (멀티스레딩)
        self.generate_thumbnail(thumbnail_cache)

    def generate_thumbnail(self, thumbnail_cache=None):
        """썸네일 생성 (멀티스레딩)"""
        if self.thumbnail_worker is not None:
            return

        self.thumbnail_worker = ThumbnailWorker(self.path, self, thumbnail_cache)
        self.thumbnail_worker.signals.finished.connect(self._on_thumbnail_ready)
        
        # 스레드 풀에 작업 추가
        QThreadPool.globalInstance().start(self.thumbnail_worker)

    def _on_thumbnail_ready(self, path, image):
        """썸네일 생성 완료 시 호출되는 콜백"""
        if path == self.path:  # 현재 위젯의 썸네일인지 확인
            self.set_thumbnail(image)
            self.thumbnail_loaded = True
            self.thumbnail_worker = None

    def set_thumbnail(self, image):
        """썸네일 설정"""
        if isinstance(image, QImage):
            pixmap = QPixmap.fromImage(image)
        else:
            pixmap = image

        scaled_pixmap = pixmap.scaled(
            self.thumbnail_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.thumbnail_label.setPixmap(scaled_pixmap)

    def load_tags(self):
        """메타데이터 파일(.meta.json)에서 태그를 로드하여 self.tags에 저장"""
        meta_file_path = os.path.join(self.path, ".meta.json")
        if os.path.exists(meta_file_path): # 메타 파일 경로 유효하고 파일 존재 시
            try:
                with open(meta_file_path, 'r', encoding='utf-8') as f:
                    meta_data = json.load(f) # JSON 파일 로드
                    # "tags" 키 값 가져오기 (없으면 빈 리스트)
                    raw_tags = meta_data.get("tags", [])
                    # 태그가 리스트 형태인지 확인하고, 각 태그를 문자열로 변환 및 공백 제거
                    if isinstance(raw_tags, list):
                        self.tags = sorted(list(set(str(tag).strip() for tag in raw_tags if str(tag).strip())))
                    else: # 리스트가 아니면 경고 출력 및 빈 리스트로 초기화
                        print(f"경고: {meta_file_path}의 'tags'가 리스트가 아닙니다. 무시합니다.")
                        self.tags = []
            except (json.JSONDecodeError, IOError) as e: # JSON 디코딩 또는 파일 IO 오류 시
                print(f"{meta_file_path}에서 태그 로드 오류: {e}")
                self.tags = []
            except Exception as e: # 기타 예외 처리
                print(f"{meta_file_path}에서 태그 처리 중 예상치 못한 오류: {e}")
                self.tags = []
        else: # 메타 파일 없으면 빈 리스트
            self.tags = []

        self.update_tags_label() # 태그 라벨 업데이트

    def save_tags(self):
        """현재 self.tags 내용을 메타데이터 파일(.meta.json)에 저장"""
        # 파일인 경우 저장하지 않음
        if os.path.isfile(self.path):
            return

        meta_file_path = os.path.join(self.path, ".meta.json")
        meta_data = {} # 저장할 메타데이터 초기화
        
        # 기존 메타 파일이 있으면 읽어서 다른 필드 유지
        if os.path.exists(meta_file_path):
            try:
                with open(meta_file_path, 'r', encoding='utf-8') as f:
                    meta_data = json.load(f)
                    if not isinstance(meta_data, dict): # 유효한 JSON 객체(딕셔너리)인지 확인
                        print(f"경고: 메타 파일 {meta_file_path}이 유효한 JSON 객체를 포함하지 않습니다. 덮어씁니다.")
                        meta_data = {}
            except (json.JSONDecodeError, IOError) as e: # 읽기 오류 시
                print(f"기존 메타 파일 {meta_file_path} 읽기 오류. 새로 생성하거나 덮어씁니다. 오류: {e}")
                meta_data = {} # 데이터 초기화
            except Exception as e: # 기타 읽기 오류 시
                print(f"메타 파일 {meta_file_path} 읽기 중 예상치 못한 오류: {e}")
                meta_data = {}

        # 태그 업데이트 (항상 리스트 형태로 저장되도록 보장)
        meta_data["tags"] = self.tags if isinstance(self.tags, list) else []

        # 파일에 다시 쓰기
        try:
            with open(meta_file_path, 'w', encoding='utf-8') as f:
                # JSON 형식으로 저장 (들여쓰기 적용, ASCII 아닌 문자 유지)
                json.dump(meta_data, f, ensure_ascii=False, indent=4)
            print(f"태그 저장 완료: {meta_file_path}")
        except IOError as e: # 쓰기 오류 시
            print(f"태그 저장 오류 {meta_file_path}: {e}")
            QMessageBox.warning(self, "저장 오류", f"태그 저장 실패:\n{e}")
        except Exception as e: # 기타 쓰기 오류 시
            print(f"태그 저장 중 예상치 못한 오류 {meta_file_path}: {e}")
            QMessageBox.warning(self, "저장 오류", f"알 수 없는 오류로 태그 저장 실패:\n{e}")

    def update_tags_label(self):
        """태그 라벨의 텍스트를 업데이트 (길면 ...으로 축약)"""
        if self.tags: # 태그가 있으면
            full_text = ", ".join(self.tags) # 쉼표로 구분된 문자열 생성
            # QFontMetrics를 사용하여 텍스트 너비 계산 및 축약
            font_metrics = QFontMetrics(self.tags_label.font())
            # 사용 가능한 너비 계산 (라벨 너비에서 약간의 여백 제외)
            # 레이아웃이 공간을 잘 관리하면 라벨 너비 직접 사용 가능
            available_width = self.tags_label.width() - 5 # 약간의 여백
            if available_width > 0: # 너비가 유효하면
                # 오른쪽 끝을 ...으로 축약 (elide)
                elided_text = font_metrics.elidedText(full_text, Qt.ElideRight, available_width)
                self.tags_label.setText(elided_text) # 축약된 텍스트 설정
            else: # 너비를 아직 알 수 없는 경우 (초기화 중 등)
                # 임시로 길이 기반 축약
                self.tags_label.setText(full_text[:30] + "..." if len(full_text) > 30 else full_text)

            self.tags_label.setToolTip(full_text) # 마우스 호버 시 전체 태그 표시
        else: # 태그가 없으면
            self.tags_label.setText("없음")
            self.tags_label.setToolTip("") # 툴팁 제거

    def edit_tags(self):
        """태그 편집 다이얼로그를 열고 변경된 태그를 저장"""
        # 파일인 경우에만 태그 편집 제한
        if os.path.isfile(self.path):
            QMessageBox.information(self, "알림", "파일에는 태그를 편집할 수 없습니다.")
            return

        # 현재 테마 이름 가져오기 (부모 창에서)
        theme_name = getattr(self.window(), 'theme_name', 'white')
        # 현재 태그를 다이얼로그에 전달
        dialog = TagEditDialog(self.tags, self, theme_name=theme_name)
        if dialog.exec(): # 사용자가 '확인'을 누르면
            new_tags = dialog.get_tags() # 다이얼로그에서 새 태그 목록 가져오기
            # 태그가 실제로 변경되었는지 확인 후 저장
            if set(self.tags) != set(new_tags): # 순서 무시하고 내용 비교
                print(f"{self.name}의 태그 변경됨: {new_tags}")
                self.tags = new_tags # 새 태그 목록으로 업데이트
                self.update_tags_label() # 라벨 업데이트
                self.save_tags() # 변경된 태그 저장

    def apply_theme(self, bg_color, text_color):
        self.setStyleSheet(f"background-color: {bg_color}; color: {text_color}; border-radius: 10px;")
        self.name_label.setStyleSheet(f"color: {text_color}; background: transparent;")
        self.thumbnail_label.setStyleSheet(f"background-color: {bg_color}; border: 1px solid lightgray; border-radius: 10px;")
        self.edit_tags_button.setStyleSheet(f"color: {text_color}; background-color: {bg_color}; border: 1px solid {text_color}; border-radius: 3px; padding: 2px 5px;")
        if hasattr(self, 'tags_label'):
            self.tags_label.setStyleSheet(f"color: {text_color}; background: transparent;")

class FolderItemWidget(BaseItemWidget):
    """폴더 아이템을 표시하는 위젯 클래스"""
    def __init__(self, folder_path, folder_name, parent=None):
        # 부모 클래스 생성자 호출 전에 썸네일 찾기
        thumbnail_file = self.find_thumbnail(folder_path)
        # 찾은 썸네일 경로와 함께 부모 클래스 초기화
        super().__init__(folder_path, folder_name, parent)
        # 부모 클래스에서 load_thumbnail을 호출하므로 여기서 다시 호출할 필요 없음

    def find_thumbnail(self, folder_path):
        """폴더 내에서 썸네일로 사용할 이미지 파일 찾기"""
        try:
            # 지원하는 이미지 확장자
            image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
            
            # 숫자로 시작하는 이미지 파일 우선
            numbered_images = []
            other_images = []
            
            for filename in sorted(os.listdir(folder_path)):
                if filename.startswith('.') or filename in HIDDEN_FILES:
                    continue
                    
                ext = os.path.splitext(filename)[1].lower()
                if ext in image_extensions:
                    full_path = os.path.join(folder_path, filename)
                    if filename[0].isdigit():
                        numbered_images.append(full_path)
                    else:
                        other_images.append(full_path)
            
            # 숫자로 시작하는 이미지가 있으면 첫 번째 것 사용
            if numbered_images:
                return numbered_images[0]
            # 없으면 다른 이미지 중 첫 번째 것 사용
            elif other_images:
                return other_images[0]
            
            # 이미지가 없으면 빈폴더.png 사용
            script_dir = os.path.dirname(os.path.abspath(__file__))
            return os.path.join(script_dir, "빈폴더.png")
            
        except Exception as e:
            print(f"썸네일 검색 오류 ({folder_path}): {e}")
            return None

    def generate_thumbnail(self, thumbnail_cache=None):
        if self.thumbnail_loaded:
            return

        thumbnail_path = self.find_thumbnail(self.path)
        print(f"[폴더 썸네일] {self.path} -> {thumbnail_path}")

        if thumbnail_path and os.path.exists(thumbnail_path):
            cache_key = f"{self.path}|{os.path.basename(thumbnail_path)}"
            if thumbnail_cache:
                cached_image = thumbnail_cache.get(cache_key)
                if cached_image:
                    self.set_thumbnail(cached_image)
                    self.thumbnail_loaded = True
                    return
            self.thumbnail_worker = ThumbnailWorker(thumbnail_path, self, thumbnail_cache, cache_key=cache_key)
            self.thumbnail_worker.signals.finished.connect(self._on_thumbnail_ready)
            QThreadPool.globalInstance().start(self.thumbnail_worker)
        else:
            # 기본 폴더 아이콘 생성
            folder_icon = QImage(THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT, QImage.Format_ARGB32)
            folder_icon.fill(Qt.transparent)
            painter = QPainter(folder_icon)
            painter.setRenderHint(QPainter.Antialiasing)
            folder_color = QColor(100, 100, 100)
            painter.setPen(Qt.NoPen)
            painter.setBrush(folder_color)
            painter.drawRoundedRect(10, 10, THUMBNAIL_WIDTH - 20, 30, 5, 5)
            painter.drawRoundedRect(5, 25, THUMBNAIL_WIDTH - 10, THUMBNAIL_HEIGHT - 30, 5, 5)
            painter.end()
            if thumbnail_cache:
                thumbnail_cache.set(self.path, folder_icon)
            self.set_thumbnail(folder_icon)
            self.thumbnail_loaded = True

    def _on_thumbnail_ready(self, path, image):
        """썸네일 생성 완료 시 호출되는 콜백"""
        if path == self.path:  # 현재 위젯의 썸네일인지 확인
            self.set_thumbnail(image)
            self.thumbnail_loaded = True
            self.thumbnail_worker = None

    def apply_theme(self, bg_color, text_color):
        super().apply_theme(bg_color, text_color)

class FileItemWidget(BaseItemWidget):
    """파일 아이템을 표시하는 위젯 클래스"""
    def __init__(self, file_path, file_name, parent=None):
        # 파일은 썸네일을 명시적으로 전달하지 않음 (BaseItemWidget에서 None 처리)
        super().__init__(file_path, file_name, parent)
        self.load_file_preview() # 파일 미리보기 로드
        # 파일 위젯에서는 태그 편집 기능 숨김
        self.edit_tags_button.setVisible(False)
        self.tags_label.setVisible(False)

    def load_file_preview(self):
        """파일 미리보기를 로드 (이미지 파일이면 이미지, 아니면 텍스트)"""
        # 일반적인 이미지 형식인지 확인
        is_image = self.name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'))

        if is_image: # 이미지 파일인 경우
            try:
                pixmap = QPixmap(self.path) # QPixmap으로 직접 로드 시도
                if not pixmap.isNull(): # 로드 성공 및 유효한 이미지인 경우
                    # 라벨 크기에 맞게 이미지 크기 조정 (가로세로 비율 유지)
                    scaled_pixmap = pixmap.scaled(THUMBNAIL_WIDTH - 10, THUMBNAIL_HEIGHT - 10, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.thumbnail_label.setPixmap(scaled_pixmap) # 라벨에 이미지 설정
                    self.thumbnail_label.setStyleSheet(IMAGE_LABEL_STYLE_LOADED) # 로드 후 스타일 적용
                    self.setToolTip(f"{self.name}\n{self.path}") # 툴팁 설정 (파일명 + 경로)
                else: # 로드 실패 시
                    self.thumbnail_label.setText("(이미지\n로드 실패)")
                    self.thumbnail_label.setStyleSheet(IMAGE_LABEL_STYLE) # 기본 스타일로 리셋
                    print(f"이미지 파일 QPixmap 로드 실패: {self.path}")
            except Exception as e: # 이미지 로드 중 오류 발생 시
                print(f"이미지 미리보기 로드 오류 {self.path}: {e}")
                self.thumbnail_label.setText("(이미지\n오류)")
                self.thumbnail_label.setStyleSheet(IMAGE_LABEL_STYLE) # 기본 스타일로 리셋
        else: # 이미지 파일이 아닌 경우
            # 파일 확장자 또는 기본 아이콘 표시
            # 현재는 간단한 텍스트로 표시
            file_ext = os.path.splitext(self.name)[1].lower() # 파일 확장자 추출
            # 표시할 텍스트 생성 (파일 (확장자)\n파일명 앞부분...)
            display_text = f"파일 ({file_ext})\n{self.name[:20]}{'...' if len(self.name) > 20 else ''}"
            self.thumbnail_label.setText(display_text) # 라벨에 텍스트 설정
            self.thumbnail_label.setWordWrap(True) # 자동 줄 바꿈 활성화
            self.thumbnail_label.setStyleSheet(IMAGE_LABEL_STYLE) # 기본 스타일 적용
            self.setToolTip(f"{self.name}\n{self.path}") # 툴팁 설정 (파일명 + 경로)

    def generate_thumbnail(self, thumbnail_cache=None):
        """파일 썸네일 생성 (멀티스레딩)"""
        if self.thumbnail_worker is not None:
            return

        self.thumbnail_worker = ThumbnailWorker(self.path, self, thumbnail_cache)
        self.thumbnail_worker.signals.finished.connect(self._on_thumbnail_ready)
        
        # 스레드 풀에 작업 추가
        QThreadPool.globalInstance().start(self.thumbnail_worker)

    def _on_thumbnail_ready(self, path, image):
        """썸네일 생성 완료 시 호출되는 콜백"""
        if path == self.path:  # 현재 위젯의 썸네일인지 확인
            self.set_thumbnail(image)
            self.thumbnail_loaded = True
            self.thumbnail_worker = None

    # 파일 위젯은 BaseItemWidget으로부터 드래그 앤 드롭 기능 상속받음

    def apply_theme(self, bg_color, text_color):
        super().apply_theme(bg_color, text_color)
