import os
import json
import time
from widgets import HIDDEN_FILES # Import constant from widgets

class DataManager:
    """
    파일 시스템 탐색, 메타데이터(태그) 로드/저장, 아이템 필터링/정렬 등
    데이터 관련 로직을 처리하는 클래스.
    """
    def __init__(self, base_path):
        self.base_path = base_path

    def get_items_in_directory(self, dir_path, sort_criteria=0, filter_text=""):
        """
        지정된 디렉토리의 아이템(폴더/파일) 목록을 가져옵니다.
        숨김 파일을 제외하고, 필터링 및 정렬을 적용합니다.

        Args:
            dir_path (str): 탐색할 디렉토리 경로.
            sort_criteria (int): 정렬 기준 (0: 이름, 1: 날짜, 2: 크기).
            filter_text (str): 필터링할 텍스트 (파일 이름 또는 확장자).

        Returns:
            list: 아이템 정보를 담은 딕셔너리 리스트.
                  각 딕셔너리는 'path', 'name', 'is_dir', 'mtime', 'size' 키를 포함.
            None: 경로가 유효하지 않거나 오류 발생 시.
        """
        if not os.path.exists(dir_path) or not os.path.isdir(dir_path):
            print(f"Error: Path is not a valid directory - {dir_path}")
            return None

        items_to_display = []
        try:
            entries = os.listdir(dir_path)
            for entry in entries:
                if entry in HIDDEN_FILES or entry.startswith('.'):
                    continue
                item_path = os.path.join(dir_path, entry)
                try:
                    is_dir = os.path.isdir(item_path)
                    mtime = os.path.getmtime(item_path) if os.path.exists(item_path) else 0
                    size = os.path.getsize(item_path) if not is_dir and os.path.exists(item_path) else 0

                    items_to_display.append({
                        "path": item_path,
                        "name": entry,
                        "is_dir": is_dir,
                        "mtime": mtime,
                        "size": size
                    })
                except OSError as e:
                    print(f"Error accessing file properties for {item_path}: {e}")
                    continue # Skip this item if properties cannot be accessed

            # 필터링 (파일만 필터링)
            if filter_text:
                filter_text_lower = filter_text.lower()
                filtered_items = []
                for item in items_to_display:
                    # 폴더는 항상 포함, 파일은 이름/확장자 매치 시 포함
                    if item["is_dir"] or filter_text_lower in item["name"].lower():
                        filtered_items.append(item)
                items_to_display = filtered_items

            # 정렬
            if sort_criteria == 0: # 이름
                items_to_display.sort(key=lambda x: x["name"].lower())
            elif sort_criteria == 1: # 날짜 (최신순, 폴더 우선)
                items_to_display.sort(key=lambda x: (not x["is_dir"], -x["mtime"]), reverse=False) # Sort by is_dir (False comes first), then mtime descending
            elif sort_criteria == 2: # 크기 (큰 순, 폴더 우선)
                 items_to_display.sort(key=lambda x: (not x["is_dir"], -x["size"]), reverse=False) # Sort by is_dir, then size descending

            return items_to_display

        except Exception as e:
            print(f"Error listing directory {dir_path}: {e}")
            return None

    def find_items_by_tags(self, search_tags):
        """
        주어진 태그를 모두 포함하는 아이템 폴더 경로를 찾습니다.

        Args:
            search_tags (set): 검색할 태그 문자열 집합 (소문자).

        Returns:
            list: 매칭되는 아이템 폴더 경로 리스트.
        """
        matching_paths = []
        if not search_tags:
            return matching_paths

        for root, dirs, files in os.walk(self.base_path):
            meta_path = os.path.join(root, ".meta.json")
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, 'r', encoding='utf-8') as f:
                        meta_data = json.load(f)
                        # Ensure tags are loaded correctly as a set of lowercase strings
                        raw_tags = meta_data.get("tags", [])
                        if isinstance(raw_tags, list):
                             item_tags = {str(tag).strip().lower() for tag in raw_tags if str(tag).strip()}
                        else:
                             item_tags = set() # Ignore if tags are not a list

                        # Check if all search tags are present in the item's tags
                        if search_tags.issubset(item_tags):
                            matching_paths.append(root)
                            # Stop searching deeper in this branch once a match is found
                            dirs[:] = []
                except (json.JSONDecodeError, IOError) as e:
                    print(f"Error reading or parsing meta file {meta_path}: {e}")
                except Exception as e:
                    print(f"Unexpected error processing meta file {meta_path}: {e}")

        return matching_paths

    # Note: Tag saving logic remains in BaseItemWidget as it's directly tied to the widget's state.
    # If a more centralized tag management system is needed later, it could be moved here.
