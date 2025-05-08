from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QScrollArea, 
                             QPushButton, QHBoxLayout, QTreeWidget, QTreeWidgetItem)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap, QImage
import os
import fitz  # PyMuPDF for PDF preview
import zipfile
import tarfile
import rarfile
from PIL import Image
import io

class PreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.setWindowTitle("파일 미리보기")
        self.setMinimumSize(800, 600)
        
        # 메인 레이아웃
        layout = QVBoxLayout(self)
        
        # 상단 컨트롤 바
        control_bar = QHBoxLayout()
        self.close_button = QPushButton("닫기")
        self.close_button.clicked.connect(self.close)
        control_bar.addStretch()
        control_bar.addWidget(self.close_button)
        layout.addLayout(control_bar)
        
        # 스크롤 영역
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.scroll_area.setWidget(self.preview_label)
        layout.addWidget(self.scroll_area)
        
        # 압축 파일 목록 표시 영역
        self.archive_tree = QTreeWidget()
        self.archive_tree.setHeaderLabels(["파일명", "크기", "수정일"])
        self.archive_tree.setColumnWidth(0, 300)
        self.archive_tree.setColumnWidth(1, 100)
        self.archive_tree.setColumnWidth(2, 150)
        self.archive_tree.hide()  # 초기에는 숨김
        layout.addWidget(self.archive_tree)
        
        self.current_file = None
        
    def show_preview(self, file_path):
        """파일 미리보기를 표시합니다."""
        if not os.path.exists(file_path):
            return
            
        self.current_file = file_path
        file_ext = os.path.splitext(file_path)[1].lower()
        
        try:
            if file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
                self._show_image_preview(file_path)
            elif file_ext == '.pdf':
                self._show_pdf_preview(file_path)
            elif file_ext in {'.zip', '.tar', '.gz', '.rar'}:
                self._show_archive_preview(file_path)
            else:
                self._show_unsupported_preview()
        except Exception as e:
            self._show_error_preview(str(e))
            
    def _show_image_preview(self, file_path):
        """이미지 파일 미리보기를 표시합니다."""
        image = Image.open(file_path)
        # 이미지 크기 조정
        max_size = QSize(1600, 1200)
        image.thumbnail((max_size.width(), max_size.height()))
        
        # PIL Image를 QPixmap으로 변환
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        qimage = QImage.fromData(buffer.getvalue())
        pixmap = QPixmap.fromImage(qimage)
        
        self.preview_label.setPixmap(pixmap)
        
    def _show_pdf_preview(self, file_path):
        """PDF 파일 미리보기를 표시합니다."""
        doc = fitz.open(file_path)
        if doc.page_count > 0:
            page = doc[0]
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            
            # 이미지 크기 조정
            max_size = QSize(1600, 1200)
            img.thumbnail((max_size.width(), max_size.height()))
            
            # PIL Image를 QPixmap으로 변환
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            qimage = QImage.fromData(buffer.getvalue())
            pixmap = QPixmap.fromImage(qimage)
            
            self.preview_label.setPixmap(pixmap)
        doc.close()
        
    def _show_archive_preview(self, file_path):
        """압축 파일 내부 목록을 표시합니다."""
        try:
            ext = os.path.splitext(file_path)[1].lower()
            
            if ext == '.zip':
                with zipfile.ZipFile(file_path, 'r') as archive:
                    self._populate_archive_tree(archive.namelist(), archive)
            elif ext in {'.tar', '.gz'}:
                with tarfile.open(file_path, 'r:*') as archive:
                    self._populate_archive_tree(archive.getnames(), archive)
            elif ext == '.rar':
                with rarfile.RarFile(file_path, 'r') as archive:
                    self._populate_archive_tree(archive.namelist(), archive)
                    
            self.archive_tree.show()
            self.preview_label.hide()
        except Exception as e:
            self.preview_label.setText(f"압축 파일 로드 오류: {str(e)}")
            
    def _populate_archive_tree(self, file_list, archive):
        """압축 파일 내부 파일 목록을 트리 위젯에 표시합니다."""
        self.archive_tree.clear()
        
        # 파일 경로를 트리 구조로 변환
        root_items = {}
        
        for file_path in sorted(file_list):
            parts = file_path.split('/')
            current_dict = root_items
            
            # 디렉토리 구조 생성
            for i, part in enumerate(parts[:-1]):
                if part not in current_dict:
                    item = QTreeWidgetItem([part, "", ""])
                    current_dict[part] = {"item": item, "children": {}}
                current_dict = current_dict[part]["children"]
            
            # 파일 정보 가져오기
            try:
                if isinstance(archive, zipfile.ZipFile):
                    info = archive.getinfo(file_path)
                    size = info.file_size
                    date = info.date_time
                elif isinstance(archive, tarfile.TarFile):
                    info = archive.getmember(file_path)
                    size = info.size
                    date = info.mtime
                elif isinstance(archive, rarfile.RarFile):
                    info = archive.getinfo(file_path)
                    size = info.file_size
                    date = info.date_time
            except:
                size = 0
                date = (0, 0, 0, 0, 0, 0)
            
            # 파일 크기 포맷팅
            if size < 1024:
                size_str = f"{size} B"
            elif size < 1024 * 1024:
                size_str = f"{size/1024:.1f} KB"
            else:
                size_str = f"{size/(1024*1024):.1f} MB"
            
            # 날짜 포맷팅
            date_str = f"{date[0]}-{date[1]:02d}-{date[2]:02d} {date[3]:02d}:{date[4]:02d}"
            
            # 파일 항목 추가
            file_item = QTreeWidgetItem([parts[-1], size_str, date_str])
            if parts[:-1]:
                current_dict[parts[-1]] = {"item": file_item, "children": {}}
            else:
                self.archive_tree.addTopLevelItem(file_item)
        
        # 트리 구조 정렬
        self.archive_tree.sortItems(0, Qt.AscendingOrder)
        
    def _show_unsupported_preview(self):
        """지원하지 않는 파일 형식에 대한 메시지를 표시합니다."""
        self.preview_label.setText("이 파일 형식은 미리보기를 지원하지 않습니다.")
        
    def _show_error_preview(self, error_message):
        """오류 메시지를 표시합니다."""
        self.preview_label.setText(f"미리보기 중 오류가 발생했습니다:\n{error_message}") 