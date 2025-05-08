import json
import os
from datetime import datetime
from PySide6.QtWidgets import QMessageBox

class SearchManager:
    def __init__(self, base_path):
        self.base_path = base_path
        self.search_history_file = os.path.join(base_path, ".search_history.json")
        self.saved_searches_file = os.path.join(base_path, ".saved_searches.json")
        self.max_history_items = 50
        self.load_history()
        self.load_saved_searches()
        
    def load_history(self):
        """검색 히스토리를 로드합니다."""
        try:
            if os.path.exists(self.search_history_file):
                with open(self.search_history_file, 'r', encoding='utf-8') as f:
                    self.search_history = json.load(f)
            else:
                self.search_history = []
        except Exception as e:
            print(f"검색 히스토리 로드 오류: {e}")
            self.search_history = []
            
    def save_history(self):
        """검색 히스토리를 저장합니다."""
        try:
            with open(self.search_history_file, 'w', encoding='utf-8') as f:
                json.dump(self.search_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"검색 히스토리 저장 오류: {e}")
            
    def add_to_history(self, search_type, criteria, results):
        """검색 히스토리에 항목을 추가합니다."""
        history_item = {
            'timestamp': datetime.now().isoformat(),
            'type': search_type,
            'criteria': criteria,
            'results_count': len(results)
        }
        
        self.search_history.insert(0, history_item)
        if len(self.search_history) > self.max_history_items:
            self.search_history = self.search_history[:self.max_history_items]
            
        self.save_history()
        
    def get_history(self):
        """검색 히스토리를 반환합니다."""
        return self.search_history
        
    def clear_history(self):
        """검색 히스토리를 초기화합니다."""
        self.search_history = []
        self.save_history()
        
    def load_saved_searches(self):
        """저장된 검색을 로드합니다."""
        try:
            if os.path.exists(self.saved_searches_file):
                with open(self.saved_searches_file, 'r', encoding='utf-8') as f:
                    self.saved_searches = json.load(f)
            else:
                self.saved_searches = {}
        except Exception as e:
            print(f"저장된 검색 로드 오류: {e}")
            self.saved_searches = {}
            
    def save_searches(self):
        """저장된 검색을 저장합니다."""
        try:
            with open(self.saved_searches_file, 'w', encoding='utf-8') as f:
                json.dump(self.saved_searches, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"저장된 검색 저장 오류: {e}")
            
    def save_search(self, name, search_type, criteria, results):
        """검색을 저장합니다."""
        if name in self.saved_searches:
            reply = QMessageBox.question(
                None,
                "검색 저장",
                f"'{name}'이(가) 이미 존재합니다. 덮어쓰시겠습니까?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return False
                
        self.saved_searches[name] = {
            'timestamp': datetime.now().isoformat(),
            'type': search_type,
            'criteria': criteria,
            'results': results
        }
        self.save_searches()
        return True
        
    def get_saved_search(self, name):
        """저장된 검색을 반환합니다."""
        return self.saved_searches.get(name)
        
    def delete_saved_search(self, name):
        """저장된 검색을 삭제합니다."""
        if name in self.saved_searches:
            del self.saved_searches[name]
            self.save_searches()
            return True
        return False
        
    def get_all_saved_searches(self):
        """모든 저장된 검색을 반환합니다."""
        return self.saved_searches 