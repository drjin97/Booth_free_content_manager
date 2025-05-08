from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QComboBox, QSpinBox,
                             QDateEdit, QCheckBox, QGroupBox, QFormLayout)
from PySide6.QtCore import Qt, QDate
import os
from datetime import datetime, timedelta

class AdvancedSearchDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("고급 검색")
        self.setMinimumWidth(500)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 파일명 검색
        name_group = QGroupBox("파일명")
        name_layout = QFormLayout()
        self.name_input = QLineEdit()
        self.name_case_sensitive = QCheckBox("대소문자 구분")
        name_layout.addRow("파일명:", self.name_input)
        name_layout.addRow("", self.name_case_sensitive)
        name_group.setLayout(name_layout)
        layout.addWidget(name_group)
        
        # 파일 크기 검색
        size_group = QGroupBox("파일 크기")
        size_layout = QHBoxLayout()
        self.size_combo = QComboBox()
        self.size_combo.addItems(["이상", "이하", "정확히"])
        self.size_input = QSpinBox()
        self.size_input.setRange(0, 1000000)
        self.size_unit = QComboBox()
        self.size_unit.addItems(["KB", "MB", "GB"])
        size_layout.addWidget(self.size_combo)
        size_layout.addWidget(self.size_input)
        size_layout.addWidget(self.size_unit)
        size_group.setLayout(size_layout)
        layout.addWidget(size_group)
        
        # 날짜 검색
        date_group = QGroupBox("날짜")
        date_layout = QFormLayout()
        self.date_type = QComboBox()
        self.date_type.addItems(["수정일", "생성일", "접근일"])
        self.date_from = QDateEdit()
        self.date_from.setDate(QDate.currentDate().addDays(-30))
        self.date_to = QDateEdit()
        self.date_to.setDate(QDate.currentDate())
        date_layout.addRow("날짜 유형:", self.date_type)
        date_layout.addRow("시작일:", self.date_from)
        date_layout.addRow("종료일:", self.date_to)
        date_group.setLayout(date_layout)
        layout.addWidget(date_group)
        
        # 파일 형식 검색
        type_group = QGroupBox("파일 형식")
        type_layout = QFormLayout()
        self.type_input = QLineEdit()
        self.type_input.setPlaceholderText("예: jpg, png, pdf (쉼표로 구분)")
        type_layout.addRow("확장자:", self.type_input)
        type_group.setLayout(type_layout)
        layout.addWidget(type_group)
        
        # 버튼
        button_layout = QHBoxLayout()
        self.search_button = QPushButton("검색")
        self.search_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("취소")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.search_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)
        
    def get_search_criteria(self):
        """검색 조건을 반환합니다."""
        criteria = {
            'name': {
                'text': self.name_input.text(),
                'case_sensitive': self.name_case_sensitive.isChecked()
            },
            'size': {
                'operator': self.size_combo.currentText(),
                'value': self.size_input.value(),
                'unit': self.size_unit.currentText()
            },
            'date': {
                'type': self.date_type.currentText(),
                'from': self.date_from.date().toPython(),
                'to': self.date_to.date().toPython()
            },
            'type': [ext.strip() for ext in self.type_input.text().split(',') if ext.strip()]
        }
        return criteria 