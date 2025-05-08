from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QFileDialog, QMessageBox)
from PySide6.QtCore import Qt
import os
import shutil

class FileOperationDialog(QDialog):
    def __init__(self, source_path, operation_type, parent=None):
        super().__init__(parent)
        self.source_path = source_path
        self.operation_type = operation_type  # 'copy' or 'move'
        self.setWindowTitle(f"파일 {operation_type}")
        self.setMinimumWidth(500)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 소스 경로 표시
        source_layout = QHBoxLayout()
        source_label = QLabel("소스:")
        self.source_path_label = QLabel(self.source_path)
        self.source_path_label.setWordWrap(True)
        source_layout.addWidget(source_label)
        source_layout.addWidget(self.source_path_label)
        layout.addLayout(source_layout)
        
        # 대상 경로 입력
        target_layout = QHBoxLayout()
        target_label = QLabel("대상:")
        self.target_path_input = QLineEdit()
        self.target_path_input.setReadOnly(True)
        browse_button = QPushButton("찾아보기")
        browse_button.clicked.connect(self.browse_target)
        target_layout.addWidget(target_label)
        target_layout.addWidget(self.target_path_input)
        target_layout.addWidget(browse_button)
        layout.addLayout(target_layout)
        
        # 버튼
        button_layout = QHBoxLayout()
        self.ok_button = QPushButton("확인")
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("취소")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)
        
    def browse_target(self):
        target_dir = QFileDialog.getExistingDirectory(
            self,
            "대상 폴더 선택",
            os.path.dirname(self.source_path)
        )
        if target_dir:
            self.target_path_input.setText(target_dir)
            
    def get_target_path(self):
        target_dir = self.target_path_input.text()
        if not target_dir:
            return None
            
        source_name = os.path.basename(self.source_path)
        return os.path.join(target_dir, source_name)
        
    def execute_operation(self):
        target_path = self.get_target_path()
        if not target_path:
            QMessageBox.warning(self, "오류", "대상 경로를 선택해주세요.")
            return False
            
        if os.path.exists(target_path):
            reply = QMessageBox.question(
                self,
                "파일 존재",
                f"'{os.path.basename(target_path)}'이(가) 이미 존재합니다. 덮어쓰시겠습니까?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return False
                
        try:
            if self.operation_type == 'copy':
                if os.path.isdir(self.source_path):
                    shutil.copytree(self.source_path, target_path, dirs_exist_ok=True)
                else:
                    shutil.copy2(self.source_path, target_path)
            else:  # move
                shutil.move(self.source_path, target_path)
            return True
        except Exception as e:
            QMessageBox.critical(self, "오류", f"작업 중 오류가 발생했습니다:\n{e}")
            return False 