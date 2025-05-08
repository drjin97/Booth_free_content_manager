from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QListWidget, QMessageBox)
from PySide6.QtCore import Qt
from datetime import datetime

class SearchHistoryDialog(QDialog):
    def __init__(self, search_manager, parent=None):
        super().__init__(parent)
        self.search_manager = search_manager
        self.setWindowTitle("검색 히스토리")
        self.setMinimumWidth(600)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 히스토리 목록
        self.history_list = QListWidget()
        self.update_history_list()
        layout.addWidget(self.history_list)
        
        # 버튼
        button_layout = QHBoxLayout()
        self.load_button = QPushButton("불러오기")
        self.load_button.clicked.connect(self.load_history_item)
        self.clear_button = QPushButton("히스토리 지우기")
        self.clear_button.clicked.connect(self.clear_history)
        self.close_button = QPushButton("닫기")
        self.close_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.load_button)
        button_layout.addWidget(self.clear_button)
        button_layout.addWidget(self.close_button)
        layout.addLayout(button_layout)
        
    def update_history_list(self):
        """검색 히스토리 목록을 업데이트합니다."""
        self.history_list.clear()
        history = self.search_manager.get_history()
        
        for item in history:
            timestamp = datetime.fromisoformat(item['timestamp'])
            formatted_time = timestamp.strftime("%Y-%m-%d %H:%M:%S")
            
            if item['type'] == 'tag':
                criteria = f"태그: {', '.join(item['criteria'])}"
            else:  # advanced
                criteria = "고급 검색"
                
            text = f"[{formatted_time}] {criteria} (결과: {item['results_count']}개)"
            self.history_list.addItem(text)
            
    def load_history_item(self):
        """선택된 히스토리 항목을 불러옵니다."""
        current_item = self.history_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "오류", "불러올 검색을 선택해주세요.")
            return
            
        index = self.history_list.row(current_item)
        history = self.search_manager.get_history()
        if 0 <= index < len(history):
            item = history[index]
            self.search_type = item['type']
            self.criteria = item['criteria']
            self.accept()
            
    def clear_history(self):
        """검색 히스토리를 초기화합니다."""
        reply = QMessageBox.question(
            self,
            "히스토리 지우기",
            "검색 히스토리를 모두 지우시겠습니까?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.search_manager.clear_history()
            self.update_history_list() 