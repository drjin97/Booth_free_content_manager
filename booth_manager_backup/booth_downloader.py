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
                    download_url = self.get_download_url(item_id)
                else:
                    download_url = url
                    item_id = download_url.split('/downloadables/')[-1].split('?')[0]

                if not download_url:
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

                    # 파일 다운로드
                    response = requests.get(download_url, cookies=self.cookies, 
                                         headers=self.headers, stream=True)
                    
                    if response.status_code != 200:
                        self.error.emit(f"다운로드 실패: HTTP {response.status_code} - {url}")
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
                    
                    # 파일명 생성
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
            str: 다운로드 URL 또는 None
        """
        item_url = f"https://booth.pm/ko/items/{item_id}"
        response = requests.get(item_url, cookies=self.cookies, headers=self.headers)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 1. data-download-url 속성을 가진 요소 찾기
            download_element = soup.find(attrs={"data-download-url": True})
            if download_element:
                return download_element['data-download-url']
            
            # 2. download-button 클래스를 가진 링크 찾기
            download_button = soup.find('a', {'class': 'download-button'})
            if download_button and 'href' in download_button.attrs:
                return download_button['href']
            
            # 3. download-link 클래스를 가진 링크 찾기
            download_link = soup.find('a', {'class': 'download-link'})
            if download_link and 'href' in download_link.attrs:
                return download_link['href']
            
            # 4. JavaScript 코드에서 다운로드 URL 찾기
            for script in soup.find_all('script'):
                if script.string:
                    # data-download-url 패턴 찾기
                    match = re.search(r'data-download-url="([^"]+)"', script.string)
                    if match:
                        return match.group(1)
                    
                    # downloadables 패턴 찾기
                    match = re.search(r'/downloadables/([^"]+)"', script.string)
                    if match:
                        return f"https://booth.pm/downloadables/{match.group(1)}"
            
            # 5. downloadables 패턴을 가진 링크 찾기
            for link in soup.find_all('a', href=True):
                if '/downloadables/' in link['href']:
                    return link['href']
        
        return None

    def get_image_urls(self, item_id):
        """
        상품 페이지에서 이미지 URL을 추출하는 메서드
        
        Args:
            item_id (str): Booth 상품 ID
            
        Returns:
            list: 이미지 URL 목록
        """
        item_url = f"https://booth.pm/ko/items/{item_id}"
        response = requests.get(item_url, cookies=self.cookies, headers=self.headers)
        image_urls = []

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # market-item-detail-item-image 클래스를 가진 이미지 요소 찾기
            for img in soup.find_all('img', {'class': 'market-item-detail-item-image'}):
                # data-origin 속성에서 원본 이미지 URL 추출
                if 'data-origin' in img.attrs:
                    origin_url = img['data-origin']
                    if 'booth.pximg.net' in origin_url:
                        image_urls.append(origin_url)

        return list(set(image_urls))  # 중복 제거

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
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("하위 폴더 설정")
        self.setModal(True)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        
        # 하위 폴더 입력
        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText("하위 폴더 이름 입력")
        layout.addWidget(self.folder_input)
        
        # 추가 버튼
        add_button = QPushButton("추가")
        add_button.clicked.connect(self.add_folder)
        layout.addWidget(add_button)
        
        # 현재 디렉토리의 폴더 목록
        current_folders_label = QLabel("현재 디렉토리의 폴더:")
        layout.addWidget(current_folders_label)
        
        self.current_folders_list = QListWidget()
        self.current_folders_list.setMaximumHeight(200)  # 높이 증가
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
        select_current_button = QPushButton("현재 폴더에서 선택")
        select_current_button.clicked.connect(self.select_from_current)
        button_layout.addWidget(select_current_button)
        
        # 삭제 버튼
        delete_button = QPushButton("선택 항목 삭제")
        delete_button.clicked.connect(self.delete_selected)
        button_layout.addWidget(delete_button)
        
        layout.addLayout(button_layout)
        
        # 확인 버튼
        ok_button = QPushButton("확인")
        ok_button.clicked.connect(self.accept)
        layout.addWidget(ok_button)
        
        self.setLayout(layout)
        
    def is_numeric_folder(self, folder_name):
        """폴더 이름이 숫자로만 이루어져 있거나 '숫자_'로 시작하거나 '_숫자'로 끝나는지 확인합니다."""
        # Check if the folder name consists only of digits 
        # OR starts with digits followed by an underscore
        # OR ends with an underscore followed by digits
        return (folder_name.isdigit() or 
                re.match(r'^\\d+_', folder_name) is not None or
                re.search(r'_\\d+$', folder_name) is not None)
        
    def get_all_folders(self, current_dir, depth=0, max_depth=2):
        """
        현재 디렉토리와 하위 디렉토리의 폴더 목록을 재귀적으로 가져옵니다.
        
        Args:
            current_dir (str): 현재 디렉토리 경로
            depth (int): 현재 탐색 깊이
            max_depth (int): 최대 탐색 깊이
            
        Returns:
            list: 폴더 경로 목록
        """
        folders = []
        try:
            for item in os.listdir(current_dir):
                full_path = os.path.join(current_dir, item)
                if os.path.isdir(full_path):
                    # 숫자 폴더는 제외
                    if not self.is_numeric_folder(item):
                        # 현재 폴더 추가
                        relative_path = os.path.relpath(full_path, os.getcwd())
                        folders.append(relative_path)
                        
                        # 최대 깊이에 도달하지 않았다면 하위 폴더도 탐색
                        if depth < max_depth:
                            sub_folders = self.get_all_folders(full_path, depth + 1, max_depth)
                            folders.extend(sub_folders)
        except Exception as e:
            print(f"폴더 탐색 중 오류 발생: {str(e)}")
            
        return folders
        
    def load_current_folders(self):
        """현재 디렉토리와 하위 디렉토리의 폴더 목록을 로드합니다."""
        try:
            # 모든 폴더 가져오기
            all_folders = self.get_all_folders(os.getcwd())
            
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
        """현재 폴더 목록에서 선택된 항목을 선택된 폴더 목록에 추가합니다."""
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
        if folder_name and not self.is_folder_in_list(folder_name):
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
        return [self.folder_list.item(i).text() for i in range(self.folder_list.count())]

    def is_folder_in_list(self, folder_name):
        """폴더가 이미 선택된 목록에 있는지 확인합니다."""
        for i in range(self.folder_list.count()):
            if self.folder_list.item(i).text() == folder_name:
                return True
        return False

class URLItemWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setFixedSize(100, 100)
        self.thumbnail_label.setStyleSheet("border: 1px solid #ccc;")
        self.thumbnail_label.setText("썸네일")
        self.setup_ui()
        self.subfolders = []
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
        layout.addWidget(self.subfolder_button)
        
        # 선택된 하위 폴더 표시
        self.subfolder_label = QLabel("선택된 폴더: 없음")
        layout.addWidget(self.subfolder_label)
        
        # URL 제거 버튼
        self.remove_button = QPushButton("삭제")
        self.remove_button.clicked.connect(self.remove_self)
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
                return
                
            # 상품 페이지 요청
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
                    
                    # 이미지 다운로드
                    img_headers = {
                        'accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
                        'accept-language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
                        'referer': 'https://booth.pm/'
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
                            return
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
        self.deleteLater()
        
    def show_subfolder_dialog(self):
        dialog = SubfolderDialog(self)
        if dialog.exec():
            self.subfolders = dialog.get_folders()
            if self.subfolders:
                self.subfolder_label.setText(f"선택된 폴더: {', '.join(self.subfolders)}")
            else:
                self.subfolder_label.setText("선택된 폴더: 없음")

class BoothDownloader(QMainWindow):
    """
    Booth 다운로더 GUI 애플리케이션
    """
    def __init__(self):
        """
        GUI 애플리케이션 초기화
        """
        super().__init__()
        self.setWindowTitle("부스 다운로더")
        self.setMinimumSize(600, 400)
        self.cookie_file = "booth_cookie.txt"
        self.url_scroll = None  # 스크롤 영역을 클래스 변수로 저장
        self.setup_ui()
        self.batch_mode = False
        self.load_cookie()

    def setup_ui(self):
        """
        GUI 인터페이스 설정
        """
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # 쿠키 입력 부분
        cookie_layout = QHBoxLayout()
        cookie_label = QLabel("_plaza_session_nktz7u 쿠키 값을 입력하세요:")
        cookie_layout.addWidget(cookie_label)
        self.cookie_input = QLineEdit()
        self.cookie_input.setPlaceholderText("_plaza_session_nktz7u 쿠키 값을 입력하세요")
        self.cookie_input.setEchoMode(QLineEdit.Password)
        self.cookie_input.textChanged.connect(self.save_cookie)
        cookie_layout.addWidget(self.cookie_input)
        layout.addLayout(cookie_layout)
        
        # 입력 모드 토글 버튼
        self.mode_toggle = QPushButton("일괄 입력 모드")
        self.mode_toggle.setCheckable(True)
        self.mode_toggle.clicked.connect(self.toggle_input_mode)
        layout.addWidget(self.mode_toggle)
        
        # 일괄 입력 영역
        self.batch_input = QTextEdit()
        self.batch_input.setPlaceholderText("URL을 줄바꿈으로 구분하여 입력하세요")
        self.batch_input.setVisible(False)
        layout.addWidget(self.batch_input)
        
        # URL 입력 영역
        self.url_scroll = QScrollArea()  # 클래스 변수에 저장
        self.url_scroll.setWidgetResizable(True)
        self.url_scroll.setMinimumHeight(200)
        
        url_container = QWidget()
        self.url_layout = QVBoxLayout(url_container)
        
        # URL 추가 버튼
        add_url_button = QPushButton("URL 추가")
        add_url_button.clicked.connect(self.add_url_item)
        layout.addWidget(add_url_button)
        
        self.url_scroll.setWidget(url_container)
        layout.addWidget(self.url_scroll)
        
        # 다운로드 버튼
        self.download_button = QPushButton("다운로드 시작")
        self.download_button.clicked.connect(self.start_download)
        layout.addWidget(self.download_button)
        
        # 로그 출력 영역
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)
        
        # 초기 URL 입력 항목 추가
        self.add_url_item()

    def save_cookie(self):
        """쿠키 값을 파일에 저장합니다."""
        try:
            cookie_text = self.cookie_input.text().strip()
            if cookie_text:
                with open(self.cookie_file, 'w', encoding='utf-8') as f:
                    f.write(cookie_text)
        except Exception as e:
            print(f"쿠키 저장 중 오류 발생: {str(e)}")
            
    def load_cookie(self):
        """저장된 쿠키 값을 불러옵니다."""
        try:
            if os.path.exists(self.cookie_file):
                with open(self.cookie_file, 'r', encoding='utf-8') as f:
                    cookie_text = f.read().strip()
                    if cookie_text:
                        self.cookie_input.setText(cookie_text)
        except Exception as e:
            print(f"쿠키 불러오기 중 오류 발생: {str(e)}")

    def toggle_input_mode(self, checked):
        self.batch_mode = checked
        self.batch_input.setVisible(checked)
        self.url_layout.parentWidget().setVisible(not checked)
        self.mode_toggle.setText("일괄 입력 모드" if checked else "개별 입력 모드")
        
    def add_url_item(self):
        url_item = URLItemWidget()
        self.url_layout.addWidget(url_item)
        # 약간의 지연 후 스크롤 이동
        QTimer.singleShot(100, self.scroll_to_bottom)
        
    def scroll_to_bottom(self):
        """스크롤을 맨 아래로 이동합니다."""
        if self.url_scroll:
            scrollbar = self.url_scroll.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        
    def get_url_items(self):
        if self.batch_mode:
            # 일괄 입력 모드에서 URL과 하위 폴더 추출
            urls = self.batch_input.toPlainText().strip().split('\n')
            urls = [url.strip() for url in urls if url.strip()]
            if not urls:
                return []
                
            # 첫 번째 URL 항목의 하위 폴더를 모든 URL에 적용
            first_item = self.url_layout.itemAt(0).widget()
            subfolders = first_item.subfolders
            return [(url, subfolders) for url in urls]
        else:
            # 개별 입력 모드에서 URL과 하위 폴더 추출
            items = []
            for i in range(self.url_layout.count()):
                item = self.url_layout.itemAt(i).widget()
                url = item.url_input.text().strip()
                if url and item.subfolders:
                    items.append((url, item.subfolders))
            return items
        
    def start_download(self):
        download_tasks = self.get_url_items()
        if not download_tasks:
            QMessageBox.warning(self, "오류", "URL을 입력해주세요.")
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
                
        # 다운로드 작업 시작
        self.log_output.append(f"다운로드 시작: {len(download_tasks)}개의 작업")
        
        # 쿠키와 헤더 설정
        cookies = {'_plaza_session_nktz7u': cookie_text} if cookie_text else {}
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # 다운로드 스레드 시작
        urls = [task[0] for task in download_tasks]
        subfolders_list = [task[1] for task in download_tasks]
        
        self.download_thread = DownloadThread(urls, cookies, headers, subfolders_list)
        self.download_thread.progress.connect(self.update_progress)
        self.download_thread.finished.connect(self.download_finished)
        self.download_thread.error.connect(self.download_error)
        self.download_thread.image_progress.connect(self.update_image_progress)
        self.download_thread.url_progress.connect(self.update_url_progress)
        self.download_thread.all_finished.connect(self.enable_buttons)
        self.download_thread.log_message.connect(self.log_output.append)  # 로그 메시지 연결
        
        self.download_button.setEnabled(False)
        self.download_thread.start()
        
    def update_progress(self, value):
        self.log_output.append(f"다운로드 진행률: {value}%")
        
    def update_image_progress(self, current, total):
        self.log_output.append(f"이미지 다운로드: {current}/{total}")
        
    def update_url_progress(self, current, total):
        self.log_output.append(f"URL 처리: {current}/{total}")
        
    def download_finished(self, message):
        self.log_output.append(message)
        QMessageBox.information(self, "완료", message)
        
    def download_error(self, message):
        self.log_output.append(f"오류: {message}")
        QMessageBox.warning(self, "오류", message)
        
    def enable_buttons(self):
        self.download_button.setEnabled(True)

if __name__ == "__main__":
    """
    프로그램 진입점
    """
    app = QApplication(sys.argv)
    window = BoothDownloader()
    window.show()
    sys.exit(app.exec()) 