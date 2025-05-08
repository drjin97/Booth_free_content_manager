from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QListWidget, QMessageBox)
from PySide6.QtCore import Qt

class SearchSaveDialog(QDialog):
    def __init__(self, search_manager, search_type, criteria, results, parent=None):
        super().__init__(parent)
        self.search_manager = search_manager
        self.search_type = search_type
        self.criteria = criteria
        self.results = results
        self.setWindowTitle("검색 저장")
        self.setMinimumWidth(500)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 검색 이름 입력
        name_layout = QHBoxLayout()
        name_label = QLabel("검색 이름:")
        self.name_input = QLineEdit()
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.name_input)
        layout.addLayout(name_layout)
        
        # 저장된 검색 목록
        saved_label = QLabel("저장된 검색:")
        layout.addWidget(saved_label)
        
        self.saved_list = QListWidget()
        self.update_saved_list()
        layout.addWidget(self.saved_list)
        
        # 버튼
        button_layout = QHBoxLayout()
        self.save_button = QPushButton("저장")
        self.save_button.clicked.connect(self.save_search)
        self.load_button = QPushButton("불러오기")
        self.load_button.clicked.connect(self.load_search)
        self.delete_button = QPushButton("삭제")
        self.delete_button.clicked.connect(self.delete_search)
        self.cancel_button = QPushButton("취소")
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.load_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)
        
    def update_saved_list(self):
        """저장된 검색 목록을 업데이트합니다."""
        self.saved_list.clear()
        saved_searches = self.search_manager.get_all_saved_searches()
        for name in sorted(saved_searches.keys()):
            self.saved_list.addItem(name)
            
    def save_search(self):
        """검색을 저장합니다."""
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "오류", "검색 이름을 입력해주세요.")
            return
            
        if self.search_manager.save_search(name, self.search_type, self.criteria, self.results):
            self.update_saved_list()
            self.name_input.clear()
            
    def load_search(self):
        """선택된 검색을 불러옵니다."""
        current_item = self.saved_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "오류", "불러올 검색을 선택해주세요.")
            return
            
        name = current_item.text()
        saved_search = self.search_manager.get_saved_search(name)
        if saved_search:
            self.search_type = saved_search['type']
            self.criteria = saved_search['criteria']
            self.results = saved_search['results']
            self.accept()
            
    def delete_search(self):
        """선택된 검색을 삭제합니다."""
        current_item = self.saved_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "오류", "삭제할 검색을 선택해주세요.")
            return
            
        name = current_item.text()
        reply = QMessageBox.question(
            self,
            "검색 삭제",
            f"'{name}'을(를) 삭제하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if self.search_manager.delete_saved_search(name):
                self.update_saved_list() 