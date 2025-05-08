from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QMessageBox)
from PySide6.QtCore import Qt
import os

class RenameDialog(QDialog):
    def __init__(self, file_path, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.setWindowTitle("이름 변경")
        self.setMinimumWidth(400)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 현재 이름 표시
        current_layout = QHBoxLayout()
        current_label = QLabel("현재 이름:")
        self.current_name_label = QLabel(os.path.basename(self.file_path))
        current_layout.addWidget(current_label)
        current_layout.addWidget(self.current_name_label)
        layout.addLayout(current_layout)
        
        # 새 이름 입력
        new_layout = QHBoxLayout()
        new_label = QLabel("새 이름:")
        self.new_name_input = QLineEdit(os.path.basename(self.file_path))
        new_layout.addWidget(new_label)
        new_layout.addWidget(self.new_name_input)
        layout.addLayout(new_layout)
        
        # 버튼
        button_layout = QHBoxLayout()
        self.ok_button = QPushButton("확인")
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("취소")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)
        
    def get_new_path(self):
        new_name = self.new_name_input.text().strip()
        if not new_name:
            return None
            
        dir_path = os.path.dirname(self.file_path)
        return os.path.join(dir_path, new_name)
        
    def execute_rename(self):
        new_path = self.get_new_path()
        if not new_path:
            QMessageBox.warning(self, "오류", "새 이름을 입력해주세요.")
            return False
            
        if os.path.exists(new_path):
            reply = QMessageBox.question(
                self,
                "파일 존재",
                f"'{os.path.basename(new_path)}'이(가) 이미 존재합니다. 덮어쓰시겠습니까?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return False
                
        try:
            os.rename(self.file_path, new_path)
            return True
        except Exception as e:
            QMessageBox.critical(self, "오류", f"이름 변경 중 오류가 발생했습니다:\n{e}")
            return False 