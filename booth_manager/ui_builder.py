from PySide6.QtCore import Qt, QDir
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSplitter,
                             QTreeView, QFileSystemModel, QComboBox, QScrollArea,
                             QGridLayout, QPushButton, QLineEdit, QTabWidget)
from PySide6.QtGui import QColor

from logger_config import logger

class UIBuilder:
    def __init__(self, main_window):
        self.main_window = main_window
        self.base_path = main_window.base_path

    def build_main_ui(self):
        """Build the main UI structure"""
        # Create main widget and layout
        main_widget = QWidget()
        self.main_window.main_widget = main_widget
        self.main_window.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Add top bar
        top_bar = self._build_top_bar()
        main_layout.addLayout(top_bar)

        # Add tab widget
        tab_widget = self._build_tab_widget()
        main_layout.addWidget(tab_widget)

    def _build_top_bar(self):
        """Build the top control bar with search, filter, and theme controls"""
        top_bar_layout = QHBoxLayout()
        top_bar_layout.setContentsMargins(0, 0, 0, 0)
        top_bar_layout.setSpacing(0)

        # Left controls (search, filter, sort)
        controls_layout = self._build_left_controls()
        top_bar_layout.addLayout(controls_layout)
        top_bar_layout.addStretch(1)

        # Right controls (theme buttons)
        theme_container = self.main_window.setup_theme_buttons()
        top_bar_layout.addWidget(theme_container)

        return top_bar_layout

    def _build_left_controls(self):
        """Build the left control section with search, filter, and sort controls"""
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(0)

        # Tag search
        controls_layout.addWidget(QLabel("태그 검색:"))
        self.main_window.search_input = QLineEdit()
        self.main_window.search_input.setPlaceholderText("검색할 태그 입력 (쉼표로 구분)")
        self.main_window.search_input.returnPressed.connect(self.main_window.search_by_tags)
        controls_layout.addWidget(self.main_window.search_input)
        
        search_button = QPushButton("태그 검색")
        search_button.clicked.connect(self.main_window.search_by_tags)
        controls_layout.addWidget(search_button)
        controls_layout.addStretch(1)

        # File filter
        controls_layout.addWidget(QLabel("파일 필터:"))
        self.main_window.filter_input = QLineEdit()
        self.main_window.filter_input.setPlaceholderText("이름 또는 확장자 필터")
        self.main_window.filter_input.textChanged.connect(self.main_window.apply_filter_sort)
        controls_layout.addWidget(self.main_window.filter_input)
        
        # Sort
        controls_layout.addWidget(QLabel("정렬:"))
        self.main_window.sort_combo = QComboBox()
        for idx, (name, *_) in self.main_window.sort_options.items():
            self.main_window.sort_combo.addItem(name)
        self.main_window.sort_combo.currentIndexChanged.connect(self.main_window.apply_filter_sort)
        controls_layout.addWidget(self.main_window.sort_combo)

        return controls_layout

    def _build_tab_widget(self):
        """Build the main tab widget with manager and downloader tabs"""
        tab_widget = QTabWidget()

        # Manager tab
        manager_tab = self._build_manager_tab()
        tab_widget.addTab(manager_tab, "아이템 관리")

        # Downloader tab
        from downloader_widget import DownloaderWidget
        downloader_widget = DownloaderWidget(self.base_path)
        tab_widget.addTab(downloader_widget, "다운로더")

        return tab_widget

    def _build_manager_tab(self):
        """Build the manager tab with tree view and content area"""
        manager_widget = QWidget()
        manager_layout = QVBoxLayout(manager_widget)
        manager_layout.setContentsMargins(0, 0, 0, 0)
        manager_layout.setSpacing(0)

        # Create splitter
        splitter = QSplitter(Qt.Horizontal)
        self.main_window.splitter = splitter
        
        # Add tree view
        tree_view = self._build_tree_view()
        splitter.addWidget(tree_view)

        # Add scroll area
        scroll_area = self._build_scroll_area()
        splitter.addWidget(scroll_area)

        # Set initial splitter sizes
        splitter.setSizes([250, 750])

        manager_layout.addWidget(splitter)
        return manager_widget

    def _build_tree_view(self):
        """Build the tree view for directory navigation"""
        tree_view = QTreeView()
        file_system_model = QFileSystemModel()
        file_system_model.setFilter(QDir.Dirs | QDir.NoDotAndDotDot)
        file_system_model.setRootPath(self.base_path)

        tree_view.setModel(file_system_model)
        root_index = file_system_model.index(self.base_path)
        if root_index.isValid():
            tree_view.setRootIndex(root_index)
            logger.info(f"Tree view root index set to: {file_system_model.filePath(root_index)}")
        else:
            logger.error(f"Could not get a valid index for base_path: {self.base_path}")

        # Hide other columns
        for i in range(1, file_system_model.columnCount()):
            tree_view.hideColumn(i)

        tree_view.clicked.connect(self.main_window.on_directory_clicked)
        
        # Store references
        self.main_window.tree_view = tree_view
        self.main_window.file_system_model = file_system_model

        return tree_view

    def _build_scroll_area(self):
        """Build the scroll area for content display"""
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.main_window.content_widget)
        scroll_area.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")
        
        # Store reference
        self.main_window.scroll_area = scroll_area

        return scroll_area

    def _adjust_brightness(self, hex_color, factor):
        """Adjust the brightness of a hex color"""
        color = QColor(hex_color)
        h, s, v, a = color.getHsv()
        new_v = max(0, min(255, int(v * factor)))
        color.setHsv(h, s, new_v, a)
        return color.name() 