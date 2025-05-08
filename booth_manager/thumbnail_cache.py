import os
import time
from collections import OrderedDict
from PySide6.QtGui import QImage
from PySide6.QtCore import QThread, Signal, QObject
import threading
from concurrent.futures import ThreadPoolExecutor

class CacheWorkerSignals(QObject):
    finished = Signal(str, QImage)  # path, image
    error = Signal(str, str)  # path, error message

class CacheWorker(QThread):
    def __init__(self, path, image, cache_dir):
        super().__init__()
        self.path = path
        self.image = image
        self.cache_dir = cache_dir
        self.signals = CacheWorkerSignals()

    def run(self):
        try:
            cache_path = os.path.join(self.cache_dir, f"{hash(self.path)}.jpg")
            self.image.save(cache_path, "JPEG", 85)
            self.signals.finished.emit(self.path, self.image)
        except Exception as e:
            self.signals.error.emit(self.path, str(e))

class ThumbnailCache:
    def __init__(self, max_memory_size=1000, max_disk_size_mb=500):
        self.memory_cache = OrderedDict()  # LRU 캐시 구현
        self.max_memory_size = max_memory_size
        self.max_disk_size = max_disk_size_mb * 1024 * 1024  # MB to bytes
        self.cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'thumbnail_cache')
        self.cache_lock = threading.Lock()
        self.worker_pool = ThreadPoolExecutor(max_workers=4)
        
        # 캐시 디렉토리 초기화
        if os.path.exists(self.cache_dir):
            try:
                for filename in os.listdir(self.cache_dir):
                    file_path = os.path.join(self.cache_dir, filename)
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        print(f"캐시 파일 삭제 실패: {e}")
            except Exception as e:
                print(f"캐시 디렉토리 초기화 실패: {e}")
        else:
            os.makedirs(self.cache_dir, exist_ok=True)
        
        # 디스크 캐시 크기 초기화
        self._init_disk_cache()

    def _init_disk_cache(self):
        """디스크 캐시 초기화 및 크기 관리"""
        try:
            total_size = 0
            cache_files = []
            
            # 캐시 파일 목록 및 크기 계산
            for filename in os.listdir(self.cache_dir):
                file_path = os.path.join(self.cache_dir, filename)
                if os.path.isfile(file_path):
                    size = os.path.getsize(file_path)
                    total_size += size
                    cache_files.append((file_path, os.path.getmtime(file_path)))
            
            # 캐시 크기가 제한을 초과하면 가장 오래된 파일부터 삭제
            if total_size > self.max_disk_size:
                cache_files.sort(key=lambda x: x[1])  # 수정 시간 기준 정렬
                for file_path, _ in cache_files:
                    if total_size <= self.max_disk_size:
                        break
                    size = os.path.getsize(file_path)
                    try:
                        os.remove(file_path)
                        total_size -= size
                    except Exception as e:
                        print(f"캐시 파일 삭제 실패: {e}")
        except Exception as e:
            print(f"디스크 캐시 초기화 실패: {e}")

    def get(self, file_path):
        """썸네일 가져오기 (메모리 -> 디스크 순서)"""
        with self.cache_lock:
            # 메모리 캐시 확인
            if file_path in self.memory_cache:
                # LRU 업데이트
                image = self.memory_cache.pop(file_path)
                self.memory_cache[file_path] = image
                return image

            # 디스크 캐시 확인
            cache_path = os.path.join(self.cache_dir, f"{hash(file_path)}.jpg")
            if os.path.exists(cache_path):
                try:
                    image = QImage(cache_path)
                    if not image.isNull():
                        # 메모리 캐시에 추가
                        self._add_to_memory_cache(file_path, image)
                        return image
                except Exception as e:
                    print(f"디스크 캐시 로드 실패: {e}")
                    try:
                        os.remove(cache_path)
                    except:
                        pass
        return None

    def set(self, file_path, image):
        """썸네일 저장 (메모리 + 비동기 디스크 저장)"""
        with self.cache_lock:
            # 메모리 캐시에 추가
            self._add_to_memory_cache(file_path, image)
            
            # 비동기로 디스크에 저장
            worker = CacheWorker(file_path, image, self.cache_dir)
            worker.signals.error.connect(lambda path, err: print(f"캐시 저장 실패 ({path}): {err}"))
            self.worker_pool.submit(worker.run)

    def _add_to_memory_cache(self, file_path, image):
        """메모리 캐시에 이미지 추가 (LRU 관리)"""
        if file_path in self.memory_cache:
            self.memory_cache.pop(file_path)
        elif len(self.memory_cache) >= self.max_memory_size:
            self.memory_cache.popitem(last=False)  # 가장 오래된 항목 제거
        self.memory_cache[file_path] = image

    def clear(self):
        """캐시 초기화"""
        with self.cache_lock:
            self.memory_cache.clear()
            try:
                for filename in os.listdir(self.cache_dir):
                    file_path = os.path.join(self.cache_dir, filename)
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        print(f"캐시 파일 삭제 실패: {e}")
            except Exception as e:
                print(f"캐시 디렉토리 정리 실패: {e}")

    def __del__(self):
        """소멸자: 스레드 풀 종료"""
        self.worker_pool.shutdown(wait=True) 