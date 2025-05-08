# UI Constants
FONT_FAMILY = ""  # 폰트 파일에서 자동으로 읽어옴
FONT_SIZE = 15  # 폰트 크기
BORDER_RADIUS = 0  # 라운딩
BORDER_WIDTH = 1   # 테두리 두께
PADDING_SMALL = "2px 5px"  # 작은 패딩
PADDING_MEDIUM = "4px 8px"  # 중간 패딩
MARGIN_SMALL = "2px"  # 작은 마진

# Theme Colors
THEME_COLORS = {
    "white": {  # 흰색 테마
        "bg": "#FFFFFF",  # 배경색
        "text": "#000000",  # 텍스트 색상
        "handle": "#1A237E"  # 핸들 색상
    },
    "gray": {  # 회색 테마
        "bg": "#F5F5F5",  # 배경색
        "text": "#333333",  # 텍스트 색상
        "handle": "#333333"  # 핸들 색상
    },
    "black": {  # 검정색 테마
        "bg": "#1E1E1E",  # 배경색
        "text": "#FFFFFF",  # 텍스트 색상
        "handle": "#FFFFFF"  # 핸들 색상
    },
    "pastel_blue": {  # 파스텔 블루 테마
        "bg": "#E3F2FD",  # 배경색
        "text": "#1A237E",  # 텍스트 색상
        "handle": "#1A237E"  # 핸들 색상
    },
    "beige": {  # 베이지색 테마
        "bg": "#F5F5DC",  # 배경색
        "text": "#4A4A4A",  # 텍스트 색상
        "handle": "#4A4A4A"  # 핸들 색상
    }
}

# Common Styles
COMMON_STYLES = {
    "font": f'font-family: "{FONT_FAMILY}"; font-size: {FONT_SIZE}px;',  # 폰트 스타일
    "border": f"border: {BORDER_WIDTH}px solid;",  # 테두리 스타일
    "border_radius": f"border-radius: {BORDER_RADIUS}px;",  # 테두리 라운드 스타일
    "padding_small": f"padding: {PADDING_SMALL};",  # 작은 패딩 스타일
    "padding_medium": f"padding: {PADDING_MEDIUM};",  # 중간 패딩 스타일
    "margin_small": f"margin: {MARGIN_SMALL};"  # 작은 마진 스타일
}

# Progress Bar Style
PROGRESS_BAR_STYLE = """
    QProgressBar {
        border: none;  # 테두리 없음
        background: transparent;  # 배경 투명
    }
    QProgressBar::chunk {
        background-color: #4CAF50;  # 진행 바 색상
        border-radius: 0px;  # 진행 바 라운드
    }
""" 