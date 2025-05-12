import sys
import os
import re
from datetime import datetime
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLineEdit, QPushButton, QLabel, 
                             QProgressBar, QMessageBox, QFileDialog, QTextEdit,
                             QScrollArea, QListWidget, QDialog)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from PySide6.QtGui import QIcon, QPixmap

# Import the style from widgets.py
from widgets import TAG_BUTTON_STYLE

class DownloadThread(QThread):
    """
    다운로드 작업을 백그라운드에서 처리하는 스레드 클래스
    """
    progress = Signal(int)              # 파일 다운로드 진행률 (0-100)
    finished = Signal(str)              # 다운로드 완료 메시지
    error = Signal(str)                 # 오류 메시지
    image_progress = Signal(int, int)   # 이미지 다운로드 진행 (현재/전체)
    url_progress = Signal(int, int)     # URL 처리 진행 (현재/전체)
    all_finished = Signal()             # 모든 다운로드 완료 신호
    log_message = Signal(str)           # 로그 메시지

    def __init__(self, urls, cookies, headers, subfolders_list):
        """
        다운로드 스레드 초기화
        
        Args:
            urls (list): 다운로드할 URL 목록
            cookies (dict): Booth 웹사이트 쿠키
            headers (dict): HTTP 요청 헤더
            subfolders_list (list): 선택된 하위 폴더 목록
        """
        super().__init__()
        self.urls = urls
        self.cookies = cookies
        self.headers = headers
        self.subfolders_list = subfolders_list
        self.downloaded_files = []  # 다운로드된 파일 경로 저장
        # 이미지 다운로드를 위한 별도 헤더
        self.image_headers = {
            'accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
            'accept-language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'referer': 'https://booth.pm/'
        }

    def run(self):
        """
        다운로드 스레드의 메인 실행 메서드
        각 URL에 대해 순차적으로 이미지와 파일을 다운로드
        """
        total_urls = len(self.urls)
        for url_idx, (url, subfolders) in enumerate(zip(self.urls, self.subfolders_list), 1):
            try:
                self.url_progress.emit(url_idx, total_urls)
                
                # URL에서 상품 ID 추출
                if '/items/' in url:
                    item_id = url.split('/items/')[-1].split('?')[0]
                    download_urls = self.get_download_url(item_id)
                else:
                    download_urls = [url]
                    item_id = url.split('/downloadables/')[-1].split('?')[0]

                if not download_urls:
                    self.error.emit(f"다운로드 URL을 찾을 수 없습니다: {url}")
                    continue

                # 각 하위 폴더에 대해 다운로드 수행
                for subfolder in subfolders:
                    # 다운로드 디렉토리 생성
                    output_dir = os.path.join(subfolder, item_id) 
                    os.makedirs(output_dir, exist_ok=True)

                    # 이미지 다운로드
                    image_urls = self.get_image_urls(item_id)
                    if image_urls:
                        self.download_images(image_urls, output_dir)

                    # 각 다운로드 URL에 대해 파일 다운로드
                    for download_url in download_urls:
                        try:
                            response = requests.get(download_url, cookies=self.cookies, 
                                                 headers=self.headers, stream=True)
                            
                            if response.status_code != 200:
                                self.error.emit(f"다운로드 실패: HTTP {response.status_code} - {download_url}")
                                continue

                            # 파일 확장자 결정
                            file_extension = '.zip'  # 기본값
                            
                            # 1. Content-Type에서 확장자 추출 시도
                            content_type = response.headers.get('Content-Type', '')
                            if 'application/x-rar-compressed' in content_type:
                                file_extension = '.rar'
                            elif 'application/x-7z-compressed' in content_type:
                                file_extension = '.7z'
                            elif 'application/pdf' in content_type:
                                file_extension = '.pdf'
                            elif 'application/zip' in content_type:
                                file_extension = '.zip'
                            elif 'application/unitypackage' in content_type:
                                file_extension = '.unitypackage'
                            elif 'image/png' in content_type:
                                file_extension = '.png'
                            elif 'image/jpeg' in content_type:
                                file_extension = '.jpg'
                            elif 'image/gif' in content_type:
                                file_extension = '.gif'
                            elif 'text/plain' in content_type:
                                file_extension = '.txt'
                            elif 'text/html' in content_type:
                                file_extension = '.html'
                            elif 'text/css' in content_type:
                                file_extension = '.css'
                            elif 'text/javascript' in content_type:
                                file_extension = '.js'
                            elif 'application/json' in content_type:
                                file_extension = '.json'
                            elif 'application/xml' in content_type:
                                file_extension = '.xml'
                            
                            # 2. Content-Disposition에서 파일명 추출 시도
                            if file_extension == '.zip':  # 아직 기본값인 경우에만 시도
                                content_disposition = response.headers.get('Content-Disposition', '')
                                if 'filename=' in content_disposition:
                                    original_filename = content_disposition.split('filename=')[-1].strip('"')
                                    ext = os.path.splitext(original_filename)[1].lower()
                                    if ext:  # 확장자가 있는 경우에만 사용
                                        file_extension = ext
                            
                            # 파일명 생성 (여러 파일이 있을 경우 구분을 위해 인덱스 추가)
                            if len(download_urls) > 1:
                                filename = f"{item_id}_{download_urls.index(download_url) + 1}{file_extension}"
                            else:
                                filename = f"{item_id}{file_extension}"
                            
                            file_path = os.path.join(output_dir, filename)
                            self.downloaded_files.append(file_path)
                            
                            total_size = int(response.headers.get('content-length', 0))
                            downloaded = 0
                            
                            with open(file_path, 'wb') as f:
                                for chunk in response.iter_content(chunk_size=8192):
                                    if chunk:
                                        f.write(chunk)
                                        downloaded += len(chunk)
                                        if total_size > 0:
                                            progress = int((downloaded / total_size) * 100)
                                            self.progress.emit(progress)
                            
                            self.finished.emit(f"파일 다운로드 완료: {filename}")
                            
                        except Exception as e:
                            self.error.emit(f"파일 다운로드 중 오류 발생 ({download_url}): {str(e)}")

            except Exception as e:
                self.error.emit(f"오류 발생 ({url}): {str(e)}")

        # 모든 다운로드가 완료되면 완료 메시지 전송
        if self.downloaded_files:
            self.finished.emit(f"다운로드 완료: {len(self.downloaded_files)}개의 파일이 저장되었습니다.")
        self.all_finished.emit()

    def get_download_url(self, item_id):
        """
        상품 페이지에서 다운로드 URL을 찾는 메서드
        
        Args:
            item_id (str): Booth 상품 ID
            
        Returns:
            list: 다운로드 URL 목록 또는 빈 리스트
        """
        item_url = f"https://booth.pm/ko/items/{item_id}"
        response = requests.get(item_url, cookies=self.cookies, headers=self.headers)
        download_urls = []
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 1. data-download-url 속성을 가진 요소 찾기
            for element in soup.find_all(attrs={"data-download-url": True}):
                download_urls.append(element['data-download-url'])
            
            # 2. download-button 클래스를 가진 링크 찾기
            for button in soup.find_all('a', {'class': 'download-button'}):
                if 'href' in button.attrs:
                    download_urls.append(button['href'])
            
            # 3. download-link 클래스를 가진 링크 찾기
            for link in soup.find_all('a', {'class': 'download-link'}):
                if 'href' in link.attrs:
                    download_urls.append(link['href'])
            
            # 4. JavaScript 코드에서 다운로드 URL 찾기
            for script in soup.find_all('script'):
                if script.string:
                    # data-download-url 패턴 찾기
                    matches = re.finditer(r'data-download-url="([^"]+)"', script.string)
                    for match in matches:
                        download_urls.append(match.group(1))
                    
                    # downloadables 패턴 찾기
                    matches = re.finditer(r'/downloadables/([^"]+)"', script.string)
                    for match in matches:
                        download_urls.append(f"https://booth.pm/downloadables/{match.group(1)}")
            
            # 5. downloadables 패턴을 가진 링크 찾기
            for link in soup.find_all('a', href=True):
                if '/downloadables/' in link['href']:
                    download_urls.append(link['href'])
        
        # 중복 제거 및 유효한 URL만 필터링
        return list(set(url for url in download_urls if url))

    def get_image_urls(self, item_id):
        """
        상품 페이지에서 이미지 URL을 추출하는 메서드
        
        Args:
            item_id (str): Booth 상품 ID
            
        Returns:
            list: 이미지 URL 목록 (웹페이지에서 보이는 순서대로)
        """
        item_url = f"https://booth.pm/ko/items/{item_id}"
        response = requests.get(item_url, cookies=self.cookies, headers=self.headers)
        image_urls = []
        seen_urls = set()  # 중복 체크를 위한 set

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # market-item-detail-item-image 클래스를 가진 이미지 요소 찾기
            for img in soup.find_all('img', {'class': 'market-item-detail-item-image'}):
                # data-origin 속성에서 원본 이미지 URL 추출
                if 'data-origin' in img.attrs:
                    origin_url = img['data-origin']
                    if 'booth.pximg.net' in origin_url and origin_url not in seen_urls:
                        image_urls.append(origin_url)
                        seen_urls.add(origin_url)  # 중복 체크를 위해 set에 추가

        return image_urls  # 순서가 보존된 리스트 반환

    def download_images(self, image_urls, output_dir):
        """
        이미지 URL 목록을 다운로드하는 메서드
        
        Args:
            image_urls (list): 다운로드할 이미지 URL 목록
            output_dir (str): 이미지를 저장할 디렉토리 경로
        """
        total_images = len(image_urls)
        for idx, img_url in enumerate(image_urls, 1):
            try:
                response = requests.get(img_url, headers=self.image_headers)
                if response.status_code == 200:
                    # 파일명을 번호로 지정
                    filename = f"{idx}.jpg" if img_url.endswith('.jpg') else f"{idx}.png"
                    file_path = os.path.join(output_dir, filename)
                    
                    with open(file_path, 'wb') as f:
                        f.write(response.content)
                    
                    self.image_progress.emit(idx, total_images)
            except Exception as e:
                print(f"이미지 다운로드 실패 ({img_url}): {str(e)}")

class SubfolderDialog(QDialog):
    recent_folders = []  # 클래스 변수로 변경하여 모든 다이얼로그에서 공유
    
    def __init__(self, base_path, parent=None): # Add base_path argument
        super().__init__(parent)
        self.setWindowTitle("하위 폴더 설정")
        self.setModal(True)
        self.base_path = base_path # Store base path
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        
        # 하위 폴더 입력
        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText("하위 폴더 이름 입력 (예: 의상/아우터)")
        layout.addWidget(self.folder_input)
        
        # 추가 버튼
        add_button = QPushButton("추가")
        add_button.clicked.connect(self.add_folder)
        add_button.setStyleSheet(TAG_BUTTON_STYLE) # Apply style
        layout.addWidget(add_button)

        # 현재 디렉토리의 폴더 목록
        current_folders_label = QLabel("기존 폴더:")
        layout.addWidget(current_folders_label)
        
        # 검색바 추가
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("폴더 검색...")
        self.search_input.textChanged.connect(self.filter_folders)
        layout.addWidget(self.search_input)
        
        self.current_folders_list = QListWidget()
        self.current_folders_list.setMaximumHeight(200)  # 높이 증가
        self.current_folders_list.itemDoubleClicked.connect(self.add_current_folder)  # 더블클릭 이벤트 연결
        self.load_current_folders()
        layout.addWidget(self.current_folders_list)
        
        # 최근 선택한 폴더 목록
        recent_folders_label = QLabel("최근 선택한 폴더:")
        layout.addWidget(recent_folders_label)
        
        self.recent_folders_list = QListWidget()
        self.recent_folders_list.setMaximumHeight(100)
        self.recent_folders_list.itemDoubleClicked.connect(self.add_recent_folder)
        self.update_recent_folders_list()
        layout.addWidget(self.recent_folders_list)
        
        # 선택된 폴더 목록
        selected_folders_label = QLabel("선택된 폴더:")
        layout.addWidget(selected_folders_label)
        
        self.folder_list = QListWidget()
        self.folder_list.setMaximumHeight(100)
        layout.addWidget(self.folder_list)
        
        # 버튼 레이아웃
        button_layout = QHBoxLayout()
        
        # 현재 폴더에서 선택 버튼
        select_current_button = QPushButton("기존 폴더에서 선택")
        select_current_button.clicked.connect(self.select_from_current)
        select_current_button.setStyleSheet(TAG_BUTTON_STYLE) # Apply style
        button_layout.addWidget(select_current_button)

        # 삭제 버튼
        delete_button = QPushButton("선택 항목 삭제")
        delete_button.clicked.connect(self.delete_selected)
        delete_button.setStyleSheet(TAG_BUTTON_STYLE) # Apply style
        button_layout.addWidget(delete_button)

        layout.addLayout(button_layout)

        # 확인 버튼
        ok_button = QPushButton("확인")
        ok_button.clicked.connect(self.accept)
        ok_button.setStyleSheet(TAG_BUTTON_STYLE) # Apply style
        layout.addWidget(ok_button)

        self.setLayout(layout)
        
    def filter_folders(self):
        """검색어에 따라 폴더 목록을 필터링합니다."""
        search_text = self.search_input.text().lower()
        self.current_folders_list.clear()
        
        # 모든 폴더 가져오기
        all_folders = self.get_all_folders(self.base_path, self.base_path)
        all_folders.sort()
        
        # 검색어로 필터링
        filtered_folders = [folder for folder in all_folders if search_text in folder.lower()]
        self.current_folders_list.addItems(filtered_folders)
        
    def add_current_folder(self, item):
        """기존 폴더 목록에서 더블클릭한 폴더를 선택된 폴더 목록에 추가합니다."""
        folder_name = item.text()
        if not self.is_folder_in_list(folder_name):
            self.folder_list.addItem(folder_name)
            # 최근 선택한 폴더에 추가
            if folder_name in self.recent_folders:
                self.recent_folders.remove(folder_name)
            self.recent_folders.insert(0, folder_name)
            self.update_recent_folders_list()
            
    def load_current_folders(self):
        """기본 다운로드 경로의 폴더 목록을 로드합니다."""
        self.current_folders_list.clear()
        try:
            # 기본 경로가 존재하지 않으면 생성 시도
            if not os.path.exists(self.base_path):
                os.makedirs(self.base_path, exist_ok=True)
                print(f"기본 폴더 생성: {self.base_path}")

            # 모든 폴더 가져오기 (base_path 기준 상대 경로)
            all_folders = self.get_all_folders(self.base_path, self.base_path)
            
            # 폴더 정렬 (알파벳 순)
            all_folders.sort()
            
            # 리스트에 추가
            self.current_folders_list.addItems(all_folders)
        except Exception as e:
            print(f"폴더 목록 로드 중 오류 발생: {str(e)}")
            
    def add_recent_folder(self, item):
        """최근 선택한 폴더를 선택된 폴더 목록에 추가합니다."""
        folder_name = item.text()
        if not self.is_folder_in_list(folder_name):
            self.folder_list.addItem(folder_name)
            # 최근 선택한 폴더를 리스트의 맨 위로 이동
            if folder_name in self.recent_folders:
                self.recent_folders.remove(folder_name)
            self.recent_folders.insert(0, folder_name)
            self.update_recent_folders_list()
            
    def update_recent_folders_list(self):
        """최근 선택한 폴더 리스트를 업데이트합니다."""
        self.recent_folders_list.clear()
        self.recent_folders_list.addItems(self.recent_folders)
        
    def select_from_current(self):
        """기존 폴더 목록에서 선택된 항목을 선택된 폴더 목록에 추가합니다."""
        selected_items = self.current_folders_list.selectedItems()
        for item in selected_items:
            folder_name = item.text()
            if not self.is_folder_in_list(folder_name):
                self.folder_list.addItem(folder_name)
                # 최근 선택한 폴더에 추가
                if folder_name in self.recent_folders:
                    self.recent_folders.remove(folder_name)
                self.recent_folders.insert(0, folder_name)
                self.update_recent_folders_list()
                
    def add_folder(self):
        folder_name = self.folder_input.text().strip()
        # 경로 구분자 정규화 (Windows/Unix 호환)
        folder_name = os.path.normpath(folder_name)
        # 맨 앞/뒤 슬래시 제거
        folder_name = folder_name.strip(os.sep)

        if folder_name and not self.is_folder_in_list(folder_name):
            # 숫자만 있는 폴더 이름 방지
            if self.is_numeric_folder(os.path.basename(folder_name)):
                 QMessageBox.warning(self, "오류", "폴더 이름은 숫자만으로 구성될 수 없습니다.")
                 return
            
            self.folder_list.addItem(folder_name)
            # 최근 선택한 폴더에 추가
            if folder_name in self.recent_folders:
                self.recent_folders.remove(folder_name)
            self.recent_folders.insert(0, folder_name)
            self.update_recent_folders_list()
            self.folder_input.clear()
            
    def delete_selected(self):
        for item in self.folder_list.selectedItems():
            self.folder_list.takeItem(self.folder_list.row(item))
            
    def get_folders(self):
        # 선택된 폴더 목록 반환 (base_path 기준 상대 경로)
        return [self.folder_list.item(i).text() for i in range(self.folder_list.count())]

    def is_folder_in_list(self, folder_name):
        """폴더가 이미 선택된 목록에 있는지 확인합니다."""
        for i in range(self.folder_list.count()):
            if self.folder_list.item(i).text() == folder_name:
                return True
        return False

    def is_numeric_folder(self, folder_name):
        """
        폴더 이름이 숫자만으로 구성되어 있는지 확인합니다. (아이템 ID 폴더 제외 목적)
        """
        return folder_name.isdigit()
        
    def get_all_folders(self, current_dir, relative_to):
        """
        지정된 디렉토리와 하위 디렉토리의 폴더 목록을 재귀적으로 가져옵니다.
        
        Args:
            current_dir (str): 탐색 시작 디렉토리 경로
            relative_to (str): 상대 경로를 계산할 기준 디렉토리 경로
            
        Returns:
            list: 기준 디렉토리에 대한 상대 폴더 경로 목록
        """
        folders = []
        try:
            for item in os.listdir(current_dir):
                full_path = os.path.join(current_dir, item)
                if os.path.isdir(full_path):
                    # 숫자 폴더(아이템 ID 폴더)는 제외
                    if not self.is_numeric_folder(item):
                        # 현재 폴더 추가 (상대 경로)
                        relative_path = os.path.relpath(full_path, relative_to)
                        # 루트 폴더 자체는 제외 (상대 경로가 '.' 인 경우)
                        if relative_path != '.':
                            folders.append(relative_path)
                        
                        # 하위 폴더도 탐색
                        sub_folders = self.get_all_folders(full_path, relative_to)
                        folders.extend(sub_folders)
        except Exception as e:
            print(f"폴더 탐색 중 오류 발생 ({current_dir}): {str(e)}")
            
        return folders

class URLItemWidget(QWidget):
    # Signal to notify parent when remove button is clicked
    remove_requested = Signal(QWidget) 

    def __init__(self, parent=None):
        super().__init__(parent)
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setFixedSize(100, 100)
        self.thumbnail_label.setStyleSheet("border: 1px solid #ccc;")
        self.thumbnail_label.setText("썸네일")
        self.setup_ui()
        self.subfolders = [] # 기본 경로 기준 상대 경로 저장
        self.url_input.textChanged.connect(self.update_thumbnail)

    def setup_ui(self):
        layout = QHBoxLayout()
        
        # 썸네일 표시 영역
        layout.addWidget(self.thumbnail_label)
        
        # URL 입력
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("부스 URL을 입력하세요")
        layout.addWidget(self.url_input)
        
        # 하위 폴더 설정 버튼
        self.subfolder_button = QPushButton("하위 폴더 설정")
        self.subfolder_button.clicked.connect(self.show_subfolder_dialog)
        self.subfolder_button.setStyleSheet(TAG_BUTTON_STYLE) # Apply style
        layout.addWidget(self.subfolder_button)

        # 선택된 하위 폴더 표시
        self.subfolder_label = QLabel("선택된 폴더: 없음")
        layout.addWidget(self.subfolder_label)
        
        # URL 제거 버튼
        self.remove_button = QPushButton("삭제")
        self.remove_button.clicked.connect(self.remove_self)
        self.remove_button.setStyleSheet(TAG_BUTTON_STYLE) # Apply style
        layout.addWidget(self.remove_button)

        self.setLayout(layout)
        
    def update_thumbnail(self):
        url = self.url_input.text().strip()
        if not url:
            self.thumbnail_label.clear()
            self.thumbnail_label.setText("썸네일")
            return
            
        try:
            # URL에서 상품 ID 추출
            if '/items/' in url:
                item_id = url.split('/items/')[-1].split('?')[0]
            else:
                # 아이템 URL이 아니면 썸네일 초기화
                self.thumbnail_label.clear()
                self.thumbnail_label.setText("썸네일")
                return

            # 상품 페이지 요청 (썸네일용 표준 헤더 사용, 쿠키 불필요)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
                'Referer': 'https://booth.pm/'
            }
            response = requests.get(f"https://booth.pm/ko/items/{item_id}", headers=headers)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                # market-item-detail-item-image 클래스를 가진 이미지 요소 찾기
                image_urls = []
                for img in soup.find_all('img', {'class': 'market-item-detail-item-image'}):
                    # data-origin 속성에서 원본 이미지 URL 추출
                    if 'data-origin' in img.attrs:
                        origin_url = img['data-origin']
                        if 'booth.pximg.net' in origin_url:
                            image_urls.append(origin_url)
                
                if image_urls:
                    # 첫 번째 이미지만 사용
                    img_url = image_urls[0]
                    
                    # 이미지 다운로드 (Use specific image headers)
                    img_headers = {
                        'accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
                        'accept-language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
                        'referer': 'https://booth.pm/' # Referer is important for images
                    }
                    img_response = requests.get(img_url, headers=img_headers)
                    
                    if img_response.status_code == 200:
                        # 이미지를 QPixmap으로 변환
                        pixmap = QPixmap()
                        pixmap.loadFromData(img_response.content)
                        
                        if not pixmap.isNull():
                            # 이미지 크기 조정
                            scaled_pixmap = pixmap.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                            self.thumbnail_label.setPixmap(scaled_pixmap)
                            return # 성공
                        else:
                            raise ValueError("이미지 변환 실패")
                    else:
                        raise ValueError(f"이미지 다운로드 실패: {img_response.status_code}")
                else:
                    raise ValueError("이미지를 찾을 수 없습니다")
            else:
                raise ValueError(f"상품 페이지 요청 실패: {response.status_code}")
                
        except Exception as e:
            print(f"썸네일 로드 중 오류 발생: {str(e)}")
            self.thumbnail_label.clear()
            self.thumbnail_label.setText("오류")
            self.thumbnail_label.setStyleSheet("border: 1px solid #ccc; color: red;")

    def remove_self(self):
        """URL 항목 위젯 자신을 제거하도록 부모에게 시그널을 보냅니다."""
        # 직접 삭제하는 대신 시그널 발생
        self.remove_requested.emit(self)

    def show_subfolder_dialog(self):
        """하위 폴더 선택 다이얼로그를 표시합니다."""
        # 메인 BoothManager 창을 찾아 base_path 가져오기
        window = self.window()
        if hasattr(window, 'base_path'):
            base_path = window.base_path
            dialog = SubfolderDialog(base_path, self) # base_path 전달
            if dialog.exec():
                self.subfolders = dialog.get_folders() # 상대 경로 반환
                if self.subfolders:
                    # 상대 경로 표시
                    self.subfolder_label.setText(f"선택된 폴더: {', '.join(self.subfolders)}")
                else:
                    self.subfolder_label.setText("선택된 폴더: 없음")
        else:
             QMessageBox.warning(self, "오류", "기본 다운로드 경로를 찾을 수 없습니다.")


class DownloaderWidget(QWidget): # BoothDownloader(QMainWindow)에서 변경
    """
    Booth 다운로더 GUI 위젯 (QWidget 상속)
    """
    def __init__(self, base_path, parent=None): # base_path 인자 추가
        """
        GUI 위젯 초기화

        Args:
            base_path (str): 다운로드 기본 경로
            parent (QWidget, optional): 부모 위젯. Defaults to None.
        """
        super().__init__(parent)
        # self.setWindowTitle("부스 다운로더") # 더 이상 창 제목 설정 안 함
        # self.setMinimumSize(600, 400) # 크기는 부모 레이아웃에서 관리
        self.base_path = base_path # 다운로드를 위한 기본 경로 저장
        
        # 쿠키 파일 경로 설정
        if getattr(sys, 'frozen', False):
            # PyInstaller로 빌드된 경우
            self.cookie_file = os.path.join(os.path.dirname(sys.executable), "booth_cookie.txt")
        else:
            # 일반 Python 스크립트로 실행된 경우
            self.cookie_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "booth_cookie.txt")
            
        self.url_scroll = None  # 스크롤 영역을 클래스 멤버 변수로 저장
        self.setup_ui()
        self.batch_mode = False # 일괄 입력 모드 플래그
        self.load_cookie()

    def setup_ui(self):
        """
        GUI 인터페이스 설정
        """
        layout = QVBoxLayout(self) # self를 부모 레이아웃으로 사용

        # --- 쿠키 입력 섹션 ---
        cookie_layout = QHBoxLayout()
        cookie_label = QLabel("_plaza_session_nktz7u 쿠키 값을 입력하세요:")
        cookie_layout.addWidget(cookie_label)
        self.cookie_input = QLineEdit()
        self.cookie_input.setPlaceholderText("_plaza_session_nktz7u 쿠키 값을 입력하세요")
        self.cookie_input.setEchoMode(QLineEdit.Password)
        self.cookie_input.textChanged.connect(self.save_cookie)
        cookie_layout.addWidget(self.cookie_input)
        layout.addLayout(cookie_layout)
        # --- 쿠키 입력 섹션 끝 ---

        # --- 입력 모드 토글 ---
        self.mode_toggle = QPushButton("일괄 입력 모드")
        self.mode_toggle.setCheckable(True) # 체크 가능한 버튼으로 설정
        self.mode_toggle.clicked.connect(self.toggle_input_mode)
        self.mode_toggle.setStyleSheet(TAG_BUTTON_STYLE) # 스타일 적용
        layout.addWidget(self.mode_toggle)
        # --- 입력 모드 토글 끝 ---

        # --- 일괄 입력 영역 ---
        self.batch_input = QTextEdit()
        self.batch_input.setPlaceholderText("URL을 줄바꿈으로 구분하여 입력하세요")
        self.batch_input.setVisible(False) # 초기에는 숨김
        layout.addWidget(self.batch_input)
        # --- 일괄 입력 영역 끝 ---

        # --- 개별 URL 입력 영역 (스크롤) ---
        self.url_scroll = QScrollArea()  # 스크롤 영역 생성 및 멤버 변수에 저장
        self.url_scroll.setWidgetResizable(True) # 스크롤 영역 크기 조절 가능하게 설정
        self.url_scroll.setMinimumHeight(300) # 최소 높이 증가

        # 스크롤 영역 내 URL 항목들을 담을 컨테이너 위젯
        url_container = QWidget()
        self.url_layout = QVBoxLayout(url_container) # URL 항목들을 위한 수직 레이아웃
        self.url_layout.setAlignment(Qt.AlignTop) # 항목들을 위쪽으로 정렬

        self.url_scroll.setWidget(url_container) # 스크롤 영역에 컨테이너 위젯 설정
        layout.addWidget(self.url_scroll)
        # --- 개별 URL 입력 영역 끝 ---

        # --- 버튼 섹션 ---
        # URL 추가 버튼 (스크롤 영역 아래로 이동됨)
        self.add_url_button = QPushButton("URL 추가") # 참조 저장
        self.add_url_button.setObjectName("addUrlButton") # 객체 이름 설정 (선택 사항)
        self.add_url_button.clicked.connect(self.add_url_item)
        self.add_url_button.setStyleSheet(TAG_BUTTON_STYLE) # 스타일 적용
        layout.addWidget(self.add_url_button)

        # 다운로드 버튼
        self.download_button = QPushButton("다운로드 시작")
        self.download_button.clicked.connect(self.start_download)
        self.download_button.setStyleSheet(TAG_BUTTON_STYLE) # 스타일 적용
        layout.addWidget(self.download_button)
        # --- 버튼 섹션 끝 ---

        # --- 로그 출력 영역 ---
        log_label = QLabel("다운로드 로그:")
        layout.addWidget(log_label)
        
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(150)  # 로그 영역 최대 높이 제한
        layout.addWidget(self.log_output)
        # --- 로그 출력 영역 끝 ---

        # 초기 URL 입력 항목 추가
        self.add_url_item()

    def save_cookie(self):
        """쿠키 입력 필드의 텍스트를 파일에 저장합니다."""
        try:
            cookie_text = self.cookie_input.text().strip()
            if cookie_text:
                # 필요시 절대 경로 또는 CWD 기준 상대 경로 사용
                with open(self.cookie_file, 'w', encoding='utf-8') as f:
                    f.write(cookie_text)
        except Exception as e:
            print(f"쿠키 저장 중 오류 발생: {str(e)}")
            self.log_output.append(f"오류: 쿠키 저장 실패 - {e}")
            
    def load_cookie(self):
        """파일에서 쿠키 값을 불러와 입력 필드에 설정합니다."""
        try:
            if not os.path.exists(self.cookie_file):
                # 쿠키 파일이 없으면 빈 파일 생성
                with open(self.cookie_file, 'w', encoding='utf-8') as f:
                    pass
                    
            with open(self.cookie_file, 'r', encoding='utf-8') as f:
                cookie_text = f.read().strip()
                if cookie_text:
                    self.cookie_input.setText(cookie_text)
        except Exception as e:
            print(f"쿠키 불러오기 중 오류 발생: {str(e)}")
            self.log_output.append(f"오류: 쿠키 불러오기 실패 - {e}")


    def toggle_input_mode(self, checked):
        """입력 모드(개별/일괄)를 전환합니다."""
        self.batch_mode = checked
        self.batch_input.setVisible(checked) # 일괄 입력 영역 표시/숨김
        # 개별 URL 입력 스크롤 영역 표시/숨김
        self.url_scroll.setVisible(not checked)
        # "URL 추가" 버튼도 표시/숨김
        self.add_url_button.setVisible(not checked) # 직접 참조 사용
        self.mode_toggle.setText("개별 입력 모드로 전환" if checked else "일괄 입력 모드로 전환")

    def add_url_item(self):
        """새 URL 입력 항목 위젯을 레이아웃에 추가합니다."""
        url_item = URLItemWidget()
        # 제거 요청 시그널 연결
        url_item.remove_requested.connect(self.remove_url_item)
        self.url_layout.addWidget(url_item)
        # 새 항목 추가 후 스크롤을 아래로 이동 (약간의 지연 필요)
        QTimer.singleShot(100, self.scroll_to_bottom)

    def remove_url_item(self, item_widget):
        """지정된 URLItemWidget을 레이아웃에서 제거합니다."""
        self.url_layout.removeWidget(item_widget)
        item_widget.deleteLater() # 위젯 메모리 해제 예약

    def scroll_to_bottom(self):
        """스크롤을 맨 아래로 이동합니다."""
        if self.url_scroll:
            scrollbar = self.url_scroll.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        
    def get_url_items(self):
        """현재 입력된 URL과 선택된 하위 폴더 목록을 가져옵니다."""
        tasks = [] # (url, [absolute_subfolder_path, ...]) 튜플 리스트
        if self.batch_mode:
            # --- 일괄 입력 모드 ---
            urls = self.batch_input.toPlainText().strip().split('\n')
            urls = [url.strip() for url in urls if url.strip()] # 빈 줄 제거
            if not urls:
                QMessageBox.warning(self, "오류", "일괄 입력 모드에서 URL을 입력해주세요.")
                return []

            # 공통 하위 폴더 설정을 위한 다이얼로그 표시
            dialog = SubfolderDialog(self.base_path, self)
            if dialog.exec():
                 subfolders = dialog.get_folders() # 상대 경로 반환
                 if not subfolders:
                     QMessageBox.warning(self, "오류", "일괄 다운로드를 위한 하위 폴더를 하나 이상 선택해야 합니다.")
                     return [] # 일괄 모드에서는 하위 폴더 필수
                 # DownloadThread를 위해 상대 경로를 절대 경로로 변환
                 absolute_subfolders = [os.path.join(self.base_path, sf) for sf in subfolders]
                 tasks = [(url, absolute_subfolders) for url in urls]
            else:
                 return [] # 사용자가 하위 폴더 선택 취소

        else:
            # --- 개별 입력 모드 ---
            for i in range(self.url_layout.count()):
                widget = self.url_layout.itemAt(i).widget()
                if isinstance(widget, URLItemWidget): # 올바른 위젯인지 확인
                    url = widget.url_input.text().strip()
                    relative_subfolders = widget.subfolders # 상대 경로 리스트
                    if url:
                        if relative_subfolders:
                            # DownloadThread를 위해 상대 경로를 절대 경로로 변환
                            absolute_subfolders = [os.path.join(self.base_path, sf) for sf in relative_subfolders]
                            tasks.append((url, absolute_subfolders))
                        else:
                            # URL은 있지만 하위 폴더가 선택되지 않은 경우, 기본 경로에 다운로드
                            absolute_subfolders = [self.base_path]
                            tasks.append((url, absolute_subfolders))
                    # URL이 비어있으면 무시

        if not tasks:
             QMessageBox.warning(self, "오류", "다운로드할 유효한 URL 항목이 없습니다.")
             return []

        return tasks

    def start_download(self):
        """다운로드 스레드를 시작합니다."""
        download_tasks = self.get_url_items()
        if not download_tasks:
            # get_url_items에서 이미 경고 메시지 처리
            return

        cookie_text = self.cookie_input.text().strip()
        if not cookie_text:
            reply = QMessageBox.question(
                self,
                "경고",
                "쿠키 값이 입력되지 않아 정상적으로 진행되지 않을 수 있습니다. 계속 하시겠습니까?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
            cookie_text = ""  # 빈 쿠키로 진행

        # --- 다운로드 작업 시작 ---
        self.log_output.append(f"다운로드 시작: {len(download_tasks)}개의 작업")

        # 쿠키 및 헤더 설정
        cookies = {'_plaza_session_nktz7u': cookie_text} if cookie_text else {}
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        # 다운로드 스레드 생성 및 시작
        urls = [task[0] for task in download_tasks]
        # get_url_items에서 이미 절대 경로로 변환됨
        subfolders_list = [task[1] for task in download_tasks]

        # 기존 스레드가 실행 중인지 확인
        if hasattr(self, 'download_thread') and self.download_thread.isRunning():
             QMessageBox.warning(self, "진행 중", "이미 다운로드가 진행 중입니다.")
             return

        self.download_thread = DownloadThread(urls, cookies, headers, subfolders_list)
        # 시그널 연결
        self.download_thread.progress.connect(self.update_progress)
        self.download_thread.finished.connect(self.download_finished)
        self.download_thread.error.connect(self.download_error)
        self.download_thread.image_progress.connect(self.update_image_progress)
        self.download_thread.url_progress.connect(self.update_url_progress)
        self.download_thread.all_finished.connect(self.enable_buttons) # 모든 작업 완료 시 버튼 활성화
        self.download_thread.log_message.connect(self.log_output.append)  # 스레드 로그 메시지 연결

        self.download_button.setEnabled(False) # 다운로드 중 버튼 비활성화
        self.download_thread.start() # 스레드 시작

    def update_progress(self, value):
        """파일 다운로드 진행률 업데이트 (현재는 사용 안 함)"""
        # 로그가 너무 많아지는 것을 방지하기 위해 덜 자주 업데이트하거나 프로그레스 바 사용 고려
        # 현재는 URL/이미지 진행률 로그로 대체
        # self.log_output.append(f"다운로드 진행률: {value}%")
        pass

    def update_image_progress(self, current, total):
        """이미지 다운로드 진행 상황 로그 업데이트"""
        self.log_output.append(f"이미지 다운로드: {current}/{total}")

    def update_url_progress(self, current, total):
        """URL 처리 진행 상황 로그 업데이트"""
        self.log_output.append(f"URL 처리: {current}/{total}")

    def download_finished(self, message):
        """개별 파일 다운로드 완료 시 로그 업데이트"""
        self.log_output.append(message)
        # 선택적으로 메시지 박스 표시 가능하나, 로그가 주 피드백
        # QMessageBox.information(self, "완료", message)

    def download_error(self, message):
        """다운로드 오류 발생 시 로그 업데이트"""
        self.log_output.append(f"오류: {message}")
        # 선택적으로 메시지 박스 표시 가능
        # QMessageBox.warning(self, "오류", message)

    def enable_buttons(self):
        """모든 다운로드 작업 완료 시 버튼 활성화"""
        self.download_button.setEnabled(True)

    # get_subfolders는 SubfolderDialog가 폴더 목록을 처리하므로 제거됨

# if __name__ == "__main__": 블록 제거됨
