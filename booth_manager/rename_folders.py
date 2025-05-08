import os
import re
import sys
import json
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QListWidget, QListWidgetItem, QLabel,
    QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt

class RenameApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("폴더 이름 변경 도구")
        self.setGeometry(100, 100, 600, 400)

        self.target_dir = ""
        self.rename_candidates = [] # (original_path, new_name) 튜플 저장
        self.rename_history_file = "rename_history.json"
        self.rename_history = [] # [{ "original": "path", "new": "path" }, ...]

        # Load previous history if exists
        self.load_history()

        # --- UI Elements ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Directory Selection
        dir_layout = QHBoxLayout()
        self.dir_label = QLabel("대상 폴더:")
        self.dir_edit = QLineEdit()
        self.dir_edit.setReadOnly(True)
        self.browse_button = QPushButton("찾아보기...")
        dir_layout.addWidget(self.dir_label)
        dir_layout.addWidget(self.dir_edit)
        dir_layout.addWidget(self.browse_button)
        main_layout.addLayout(dir_layout)

        # Folder Preview List
        self.preview_label = QLabel("변경될 폴더 목록:")
        self.preview_list = QListWidget()
        main_layout.addWidget(self.preview_label)
        main_layout.addWidget(self.preview_list)

        # Action Buttons
        button_layout = QHBoxLayout()
        self.rename_button = QPushButton("이름 변경 실행")
        self.restore_button = QPushButton("이전 변경 복구")
        self.restore_button.setEnabled(len(self.rename_history) > 0) # Enable only if history exists
        button_layout.addWidget(self.rename_button)
        button_layout.addWidget(self.restore_button)
        main_layout.addLayout(button_layout)

        # Status Label
        self.status_label = QLabel("상태: 폴더를 선택하세요.")
        main_layout.addWidget(self.status_label)

        # --- Connect Signals and Slots ---
        self.browse_button.clicked.connect(self.browse_directory)
        self.rename_button.clicked.connect(self.rename_folders)
        self.restore_button.clicked.connect(self.restore_names)

    def browse_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "폴더 선택")
        if directory:
            self.target_dir = directory
            self.dir_edit.setText(directory)
            self.status_label.setText(f"상태: '{os.path.basename(directory)}' 폴더 스캔 중...")
            QApplication.processEvents() # Allow UI update
            self.find_folders()
            self.status_label.setText(f"상태: {len(self.rename_candidates)}개 폴더 변경 준비 완료.")

    def find_folders(self):
        self.rename_candidates.clear()
        self.preview_list.clear()
        if not self.target_dir:
            return

        # 정규식: 이름_숫자 형식
        folder_pattern = re.compile(r'^.+_\d+$')

        try:
            # os.walk를 사용하여 지정된 디렉토리부터 시작
            # topdown=False로 설정하면 하위 디렉토리부터 처리 가능 (선택사항)
            for root, dirs, files in os.walk(self.target_dir, topdown=True):
                # 현재 레벨의 디렉토리 복사본 순회 (dirs를 직접 수정하면 walk 동작에 영향)
                current_level_dirs = list(dirs)
                for folder in current_level_dirs:
                     # 형식 확인
                    if folder_pattern.match(folder):
                        original_path = os.path.join(root, folder)
                        # 숫자와 언더바 제거하여 새 이름 생성
                        new_name = re.sub(r'_\d+$', '', folder)
                        new_path_preview = os.path.join(root, new_name) # 미리보기용 경로

                        self.rename_candidates.append((original_path, new_name))

                        # 리스트 위젯에 아이템 추가
                        item_text = f"{folder}  ->  {new_name}"
                        list_item = QListWidgetItem(item_text)
                        list_item.setData(Qt.UserRole, (original_path, new_name)) # 데이터 저장
                        self.preview_list.addItem(list_item)

                # dirs 리스트를 직접 수정하여 하위 디렉토리 탐색 제어 가능
                # 예: 특정 이름의 폴더는 더 이상 탐색하지 않도록 제거
                # dirs[:] = [d for d in dirs if d not in folders_to_skip]

        except Exception as e:
            QMessageBox.critical(self, "오류", f"폴더 검색 중 오류 발생: {str(e)}")
            self.status_label.setText("상태: 폴더 검색 오류.")

    def rename_folders(self):
        if not self.rename_candidates:
            QMessageBox.warning(self, "경고", "변경할 폴더가 없습니다.")
            return

        reply = QMessageBox.question(self, "확인",
                                     f"{len(self.rename_candidates)}개 폴더의 이름을 변경하시겠습니까?\n"
                                     "이 작업은 이전 변경 내역을 덮어씁니다.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.No:
            self.status_label.setText("상태: 이름 변경 취소됨.")
            return

        self.status_label.setText("상태: 이름 변경 진행 중...")
        QApplication.processEvents()

        new_history = []
        errors = []
        processed_count = 0

        # Rename from deepest paths first to avoid conflicts if renaming parent folders
        # candidates are already collected via os.walk, which is top-down by default.
        # For renaming, it might be safer to rename deeper folders first.
        # Let's sort by path depth (number of separators) descending.
        sorted_candidates = sorted(self.rename_candidates, key=lambda x: x[0].count(os.sep), reverse=True)

        for original_path, new_name in sorted_candidates:
            root = os.path.dirname(original_path)
            new_path = os.path.join(root, new_name)

            # Check if the target name already exists and is a directory
            if os.path.isdir(new_path):
                 errors.append(f"오류: 대상 폴더 '{new_path}'가 이미 존재합니다. '{os.path.basename(original_path)}' 건너뜀.")
                 continue
            elif os.path.exists(new_path):
                 errors.append(f"오류: 대상 이름 '{new_path}'가 이미 존재합니다(파일 등). '{os.path.basename(original_path)}' 건너뜀.")
                 continue


            try:
                os.rename(original_path, new_path)
                new_history.append({"original": original_path, "new": new_path})
                processed_count += 1
                # Update preview list item (optional, could just clear)
                items = self.preview_list.findItems(f"{os.path.basename(original_path)}  ->  {new_name}", Qt.MatchExactly)
                if items:
                    items[0].setText(f"완료: {os.path.basename(original_path)} -> {new_name}")
                    items[0].setForeground(Qt.gray) # Indicate completion

            except Exception as e:
                errors.append(f"'{os.path.basename(original_path)}' 이름 변경 중 오류: {str(e)}")

        self.rename_history = new_history
        self.save_history()

        # Update UI
        self.rename_candidates.clear()
        # Consider clearing or just updating the list visually
        # self.preview_list.clear() # Option 1: Clear list after rename
        self.restore_button.setEnabled(len(self.rename_history) > 0)

        final_message = f"상태: {processed_count}개 폴더 이름 변경 완료."
        if errors:
            final_message += f" {len(errors)}개 오류 발생."
            QMessageBox.warning(self, "이름 변경 오류", "\n".join(errors))

        self.status_label.setText(final_message)


    def restore_names(self):
        if not self.rename_history:
            QMessageBox.information(self, "정보", "복구할 이전 변경 내역이 없습니다.")
            return

        reply = QMessageBox.question(self, "복구 확인",
                                     f"{len(self.rename_history)}개 폴더의 이름을 이전 상태로 복구하시겠습니까?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.No:
            self.status_label.setText("상태: 복구 작업 취소됨.")
            return

        self.status_label.setText("상태: 이름 복구 진행 중...")
        QApplication.processEvents()

        errors = []
        processed_count = 0

        # Restore in reverse order of renaming (rename 'new' back to 'original')
        # It's generally safer to restore shallower paths first if parents were renamed.
        # The history stores absolute paths. Let's sort by depth ascending.
        sorted_history = sorted(self.rename_history, key=lambda x: x['original'].count(os.sep))

        for entry in sorted_history:
            original_path = entry["original"]
            new_path = entry["new"] # This is the path that currently exists

            # Check if original name exists
            if os.path.isdir(original_path):
                 errors.append(f"오류: 복구 대상 '{original_path}'가 이미 존재합니다. '{os.path.basename(new_path)}' 건너뜀.")
                 continue
            elif os.path.exists(original_path):
                 errors.append(f"오류: 복구 대상 이름 '{original_path}'가 이미 존재합니다(파일 등). '{os.path.basename(new_path)}' 건너뜀.")
                 continue


            try:
                 # Check if the path we expect to restore from actually exists
                if os.path.isdir(new_path):
                    os.rename(new_path, original_path)
                    processed_count += 1
                else:
                    errors.append(f"오류: 복구할 폴더 '{new_path}'를 찾을 수 없습니다. 건너뜀.")

            except Exception as e:
                errors.append(f"'{os.path.basename(new_path)}' 이름 복구 중 오류: {str(e)}")

        # Clear history after attempting restore
        self.rename_history = []
        self.save_history() # Save the empty history

        # Update UI
        self.preview_list.clear() # Clear preview list as it's no longer relevant
        self.rename_candidates.clear()
        self.restore_button.setEnabled(False) # Disable restore button

        final_message = f"상태: {processed_count}개 폴더 이름 복구 완료."
        if errors:
            final_message += f" {len(errors)}개 오류 발생."
            QMessageBox.warning(self, "복구 오류", "\n".join(errors))

        self.status_label.setText(final_message)


    def save_history(self):
        try:
            with open(self.rename_history_file, 'w', encoding='utf-8') as f:
                json.dump(self.rename_history, f, ensure_ascii=False, indent=4)
        except Exception as e:
            QMessageBox.warning(self, "오류", f"변경 내역 저장 실패: {str(e)}")

    def load_history(self):
        if os.path.exists(self.rename_history_file):
            try:
                with open(self.rename_history_file, 'r', encoding='utf-8') as f:
                    self.rename_history = json.load(f)
            except Exception as e:
                QMessageBox.warning(self, "오류", f"이전 변경 내역 로드 실패: {str(e)}\n파일이 손상되었을 수 있습니다.")
                self.rename_history = [] # Reset history on load error
        else:
            self.rename_history = []


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = RenameApp()
    window.show()
    sys.exit(app.exec()) 