import sys
import os
import shutil
import json
import urllib.request
import datetime
import sqlite3 
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QCalendarWidget, QLabel, QListWidget, QListWidgetItem, 
    QPushButton, QDialog, QLineEdit, QComboBox, QMessageBox, 
    QFrame, QGraphicsDropShadowEffect, QCheckBox, QSplitter,
    QColorDialog, QScrollArea, QGridLayout, QSizePolicy, QMenu, QToolTip,
    QDateEdit, QAbstractItemView, QStyle, QFileDialog, QProgressBar, QFormLayout,
    QTextEdit
)
from PyQt6.QtCore import QDate, Qt, QPoint, QRect, QSize, pyqtSignal, QEvent, QSettings
from PyQt6.QtGui import QColor, QPainter, QFont, QPen, QAction, QIcon, QPixmap, QTextCharFormat

# 引入数据管理模块 (请确保 task_manager.py 在同级目录)
from task_manager import TaskManager, Task, Tag

# --- 农历支持 ---
try:
    from zhdate import ZhDate
    HAS_LUNAR = True
except ImportError:
    HAS_LUNAR = False

# --- 图标资源配置 ---
ICON_URLS = {
    "prev": "https://img.icons8.com/ios-glyphs/60/ffffff/chevron-left.png",
    "next": "https://img.icons8.com/ios-glyphs/60/ffffff/chevron-right.png",
    "today": "", # [修改] 留空，使用文字 "今"
    "add": "https://img.icons8.com/ios-glyphs/60/ffffff/plus-math.png",
    "close": "https://img.icons8.com/ios-glyphs/60/ffffff/multiply.png",
    "search": "https://img.icons8.com/ios-glyphs/60/ffffff/search--v1.png",
    "add_task": "https://img.icons8.com/ios-glyphs/60/ffffff/create-new.png",
    "filter": "https://img.icons8.com/ios-glyphs/60/ffffff/filter.png",
    "pin": "https://img.icons8.com/ios-glyphs/60/ffffff/pin.png",
    "note": "https://img.icons8.com/ios-glyphs/60/ffffff/note.png",
    "mini_mode": "https://img.icons8.com/ios-glyphs/60/ffffff/note.png",
    "import": "https://img.icons8.com/ios-glyphs/60/ffffff/import.png",
    "export": "https://img.icons8.com/ios-glyphs/60/ffffff/export.png",
    "exit": "https://img.icons8.com/ios-glyphs/60/ffffff/shutdown.png",
    "reset_layout": "https://img.icons8.com/ios-glyphs/60/ffffff/restart--v1.png",
    "sidebar": "https://img.icons8.com/ios-glyphs/60/ffffff/menu--v1.png",
    "stats": "https://img.icons8.com/ios-glyphs/60/ffffff/combo-chart.png",
    "backup": "https://img.icons8.com/ios-glyphs/60/ffffff/data-backup.png",
    "settings": "https://img.icons8.com/ios-glyphs/60/ffffff/settings--v1.png",
    "about": "https://img.icons8.com/ios-glyphs/60/ffffff/info--v1.png"
}

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def get_font(size=10, bold=False):
    safe_size = max(1, size)
    font = QFont("Microsoft YaHei UI", safe_size)
    if bold: font.setBold(True)
    return font

# --- 工具类: 农历与日期处理 ---
class DateUtils:
    @staticmethod
    def get_lunar_text(qdate: QDate):
        if not HAS_LUNAR: return "", False
        try:
            dt = datetime.datetime(qdate.year(), qdate.month(), qdate.day())
            zd = ZhDate.from_datetime(dt)
            lunar_month = zd.lunar_month
            lunar_day = zd.lunar_day
            
            solar_festivals = {
                (1, 1): "元旦", (5, 1): "劳动节", (10, 1): "国庆",
                (12, 25): "圣诞", (3, 8): "妇女节", (6, 1): "儿童节"
            }
            if (qdate.month(), qdate.day()) in solar_festivals:
                return solar_festivals[(qdate.month(), qdate.day())], True
            
            lunar_festivals = {
                (1, 1): "春节", (1, 15): "元宵", (5, 5): "端午",
                (7, 7): "七夕", (8, 15): "中秋", (9, 9): "重阳", 
                (12, 8): "腊八", (12, 23): "小年", (12, 30): "除夕"
            }
            if (lunar_month, lunar_day) in lunar_festivals:
                return lunar_festivals[(lunar_month, lunar_day)], True
            
            cn_days = ["", "初一", "初二", "初三", "初四", "初五", "初六", "初七", "初八", "初九", "初十",
                "十一", "十二", "十三", "十四", "十五", "十六", "十七", "十八", "十九", "二十",
                "廿一", "廿二", "廿三", "廿四", "廿五", "廿六", "廿七", "廿八", "廿九", "三十"]
            cn_months = ["", "正月", "二月", "三月", "四月", "五月", "六月", "七月", "八月", "九月", "十月", "冬月", "腊月"]
            
            if lunar_day == 1: return cn_months[lunar_month], False
            if 1 <= lunar_day < len(cn_days): return cn_days[lunar_day], False
        except: return "", False
        return "", False

class IconLoader:
    SAVE_DIR = "ico_image"
    @classmethod
    def ensure_dir(cls):
        if not os.path.exists(cls.SAVE_DIR):
            try: os.makedirs(cls.SAVE_DIR)
            except: pass
    @classmethod
    def get(cls, name):
        cls.ensure_dir()
        url = ICON_URLS.get(name)
        if not url: return QIcon()
        filename = f"{name}.png"
        filepath = os.path.join(cls.SAVE_DIR, filename)
        if os.path.exists(filepath): return QIcon(filepath)
        try:
            opener = urllib.request.build_opener()
            opener.addheaders = [('User-Agent', 'Mozilla/5.0')]
            urllib.request.install_opener(opener)
            urllib.request.urlretrieve(url, filepath)
            return QIcon(filepath)
        except: return QIcon()

# --- 自定义控件 ---

# [修改] 悬浮便签小部件 (增强版)
class MiniModeWidget(QWidget):
    restore_signal = pyqtSignal()

    def __init__(self, task_manager):
        super().__init__()
        self.db = task_manager
        # 无边框 + 工具窗口 + 置顶
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(320, 480) # 稍微加高一点以容纳描述
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        
        # 黄色便签容器样式
        self.container = QFrame()
        self.container.setStyleSheet("""
            QFrame {
                background-color: #FEF9C3; /* 浅黄色 */
                border-radius: 12px;
                border: 1px solid #FDE047;
            }
            QLabel { color: #451a03; }
            QListWidget {
                background-color: transparent;
                border: none;
                outline: none;
            }
            QListWidget::item {
                color: #451a03;
                padding: 10px;
                border-bottom: 1px dashed #FCD34D;
                font-size: 14px;
            }
            QListWidget::item:selected {
                background-color: rgba(253, 224, 71, 0.5);
                color: #000;
            }
            /* 进度条样式 */
            QProgressBar {
                border: none;
                background-color: rgba(0,0,0,0.1);
                border-radius: 2px;
                height: 4px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #F59E0B; /* 橙色进度 */
                border-radius: 2px;
            }
        """)
        
        # 阴影效果
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 4)
        self.container.setGraphicsEffect(shadow)
        
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(15, 15, 15, 15)
        
        # 顶部栏
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("📝 今日待办")
        title.setFont(QFont("Microsoft YaHei UI", 13, QFont.Weight.Bold))
        date_lbl = QLabel(QDate.currentDate().toString("M月d日 dddd"))
        date_lbl.setStyleSheet("font-size: 11px; color: #78350f;")
        title_box.addWidget(title)
        title_box.addWidget(date_lbl)
        
        btn_restore = QPushButton("🗖") 
        btn_restore.setFixedSize(30, 30)
        btn_restore.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_restore.setStyleSheet("""
            QPushButton { background: rgba(0,0,0,0.05); border-radius: 15px; font-size: 14px; color: #451a03; border: none; }
            QPushButton:hover { background: rgba(0,0,0,0.1); }
        """)
        btn_restore.setToolTip("恢复主界面")
        btn_restore.clicked.connect(self.restore_signal.emit)
        
        header.addLayout(title_box)
        header.addStretch()
        header.addWidget(btn_restore)
        self.container_layout.addLayout(header)
        
        # [新增] 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.container_layout.addWidget(self.progress_bar)
        
        self.container_layout.addSpacing(10)
        
        # 任务列表
        self.list_widget = QListWidget()
        self.list_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.list_widget.itemDoubleClicked.connect(self.toggle_task)
        # 启用右键菜单
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.show_context_menu)
        self.container_layout.addWidget(self.list_widget)
        
        # [修改] 删除了底部的说明 Label
        
        self.layout.addWidget(self.container)
        self.old_pos = None

    def load_data(self):
        self.list_widget.clear()
        today_str = QDate.currentDate().toString("yyyy-MM-dd")
        tags = [t.name for t in self.db.get_all_tags()]
        tasks = self.db.get_tasks_by_date_and_tags(today_str, tags)
        
        total_tasks = len(tasks)
        done_tasks = 0
        
        if not tasks:
            item = QListWidgetItem("今天没有待办事项 🎉")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list_widget.addItem(item)
            self.progress_bar.setValue(0)
            return

        for t in tasks:
            if t.status == "已完成":
                done_tasks += 1
                
            status_icon = "✅" if t.status == "已完成" else "⬜"
            
            # [修改] 组合显示内容：标题 + (换行)详细描述
            display_text = f"{status_icon} {t.content}"
            if t.description and t.description.strip():
                # 截取前30个字符，避免太长
                desc_preview = t.description.strip().replace('\n', ' ')
                if len(desc_preview) > 30: desc_preview = desc_preview[:30] + "..."
                display_text += f"\n      ↳ {desc_preview}"
            
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, t)
            
            # 如果有描述，适当增加行高
            if t.description and t.description.strip():
                item.setSizeHint(QSize(item.sizeHint().width(), 50))
            
            # 已完成样式
            if t.status == "已完成":
                font = item.font()
                font.setStrikeOut(True)
                item.setFont(font)
                item.setForeground(QColor("#a8a29e")) # 灰色
                
            self.list_widget.addItem(item)
            
        # 更新进度条
        if total_tasks > 0:
            self.progress_bar.setValue(int(done_tasks / total_tasks * 100))
        else:
            self.progress_bar.setValue(0)

    def toggle_task(self, item):
        task = item.data(Qt.ItemDataRole.UserRole)
        if not task: return
        new_status = "已完成" if task.status != "已完成" else "待完成"
        self.db.update_task_status(task.id, new_status)
        self.load_data()

    # [新增] 右键菜单功能
    def show_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #FEF9C3; border: 1px solid #FDE047; }
            QMenu::item { color: #451a03; padding: 5px 20px; }
            QMenu::item:selected { background-color: #FDE047; }
        """)
        
        # 透明度控制
        opacity_menu = menu.addMenu("👁️ 透明度")
        opacity_menu.setStyleSheet(menu.styleSheet())
        for op in [1.0, 0.8, 0.6, 0.4]:
            act = QAction(f"{int(op*100)}%", self)
            act.triggered.connect(lambda checked, o=op: self.setWindowOpacity(o))
            opacity_menu.addAction(act)
            
        menu.exec(self.list_widget.mapToGlobal(pos))

    # 拖拽移动窗口逻辑
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.old_pos:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.pos() + delta)
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.old_pos = None

class AddTagDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加新标签")
        self.setFixedWidth(320)
        self.setStyleSheet("QDialog { background-color: #2C2C2E; color: white; border-radius: 8px; } QLabel { color: #DDDDDD; font-size: 14px; }")
        layout = QVBoxLayout(self)
        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText("标签名称")
        layout.addWidget(QLabel("名称:"))
        layout.addWidget(self.input_name)
        layout.addWidget(QLabel("颜色:"))
        self.combo_color = QComboBox()
        self.colors = [("#5E5CE6", "靛蓝"), ("#30D158", "绿色"), ("#FF9F0A", "橙色"), ("#FF453A", "红色"), ("#BF5AF2", "紫色"), ("#64D2FF", "天蓝")]
        for color, name in self.colors: self.combo_color.addItem(name, color) 
        layout.addWidget(self.combo_color)
        btn = QPushButton("添加")
        btn.setObjectName("PrimaryButton")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)
    def get_data(self):
        return self.input_name.text(), self.colors[self.combo_color.currentIndex()][0]

class TaskDialog(QDialog):
    def __init__(self, tag_dict, parent=None, task: Task = None):
        super().__init__(parent)
        self.task = task
        self.setWindowTitle("编辑事项" if task else "新事项")
        self.setFixedWidth(400)
        self.setStyleSheet("""
            QDialog { background-color: #2C2C2E; border-radius: 10px; }
            QLabel { color: #BBBBBB; font-size: 14px; }
            QLineEdit, QComboBox, QTextEdit { background-color: #333; border: 1px solid #555; padding: 8px; border-radius: 6px; color: white; font-size: 14px; }
            QTextEdit { padding: 5px; }
        """)
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        self.input_content = QLineEdit()
        self.input_content.setPlaceholderText("事项标题")
        self.input_content.setFont(get_font(16, True))
        layout.addWidget(self.input_content)
        
        form = QVBoxLayout()
        form.setSpacing(10)
        
        row_meta = QHBoxLayout()
        row_meta.addWidget(QLabel("标签"))
        self.combo_tag = QComboBox()
        self.combo_tag.addItems(tag_dict.keys())
        row_meta.addWidget(self.combo_tag)
        
        row_meta.addSpacing(20)
        
        row_meta.addWidget(QLabel("优先级"))
        self.combo_priority = QComboBox()
        self.combo_priority.addItems(["普通", "重要 (!)", "紧急 (!!)", "非常紧急 (!!!)"])
        row_meta.addWidget(self.combo_priority)
        
        form.addLayout(row_meta)
        layout.addLayout(form)
        
        layout.addWidget(QLabel("详细描述 (可选):"))
        self.input_desc = QTextEdit()
        self.input_desc.setPlaceholderText("添加详细说明、备注或子任务...")
        self.input_desc.setFixedHeight(120)
        layout.addWidget(self.input_desc)

        layout.addSpacing(10)
        
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("保存修改" if task else "创建任务")
        btn_save.setObjectName("PrimaryButton")
        btn_save.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)
        
        if task:
            self.input_content.setText(task.content)
            self.combo_tag.setCurrentText(task.tag)
            p_map = {0: 0, 1: 1, 3: 2, 5: 3}
            self.combo_priority.setCurrentIndex(p_map.get(task.priority, 0))
            self.input_desc.setPlainText(task.description)

    def get_data(self):
        priorities = [0, 1, 3, 5]
        return {
            "content": self.input_content.text(),
            "tag": self.combo_tag.currentText(),
            "status": self.task.status if self.task else "待完成",
            "priority": priorities[self.combo_priority.currentIndex()],
            "description": self.input_desc.toPlainText()
        }

class AdvancedSearchDialog(QDialog):
    def __init__(self, tag_list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("高级搜索 / 筛选")
        self.setFixedWidth(400)
        self.setStyleSheet("""
            QDialog { background-color: #2C2C2E; border-radius: 10px; color: white; }
            QLabel { color: #BBBBBB; font-size: 14px; }
            QLineEdit, QComboBox, QDateEdit { background-color: #333; border: 1px solid #555; padding: 6px; border-radius: 6px; color: white; font-size: 14px; }
            QDateEdit::drop-down { border: none; }
        """)
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.addWidget(QLabel("关键词:"))
        self.input_keyword = QLineEdit()
        self.input_keyword.setPlaceholderText("搜索任务内容或描述...")
        layout.addWidget(self.input_keyword)
        date_group = QFrame()
        date_layout = QGridLayout(date_group)
        date_layout.setContentsMargins(0,0,0,0)
        date_layout.addWidget(QLabel("开始日期:"), 0, 0)
        self.date_start = QDateEdit()
        self.date_start.setCalendarPopup(True)
        self.date_start.setDate(QDate.currentDate().addDays(-7))
        date_layout.addWidget(self.date_start, 0, 1)
        date_layout.addWidget(QLabel("结束日期:"), 1, 0)
        self.date_end = QDateEdit()
        self.date_end.setCalendarPopup(True)
        self.date_end.setDate(QDate.currentDate().addDays(7))
        date_layout.addWidget(self.date_end, 1, 1)
        layout.addWidget(date_group)
        layout.addWidget(QLabel("标签:"))
        self.combo_tag = QComboBox()
        self.combo_tag.addItem("全部")
        self.combo_tag.addItems(tag_list)
        layout.addWidget(self.combo_tag)
        layout.addWidget(QLabel("最低优先级:"))
        self.combo_priority = QComboBox()
        self.combo_priority.addItem("全部", -1)
        self.combo_priority.addItem("普通及以上", 0)
        self.combo_priority.addItem("重要 (★) 及以上", 1)
        self.combo_priority.addItem("紧急 (★★★) 及以上", 3)
        self.combo_priority.addItem("非常紧急 (★★★★★)", 5)
        layout.addWidget(self.combo_priority)
        btn_layout = QHBoxLayout()
        btn_search = QPushButton("开始搜索")
        btn_search.setObjectName("PrimaryButton")
        btn_search.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_search)
        layout.addLayout(btn_layout)

    def get_filters(self):
        return {
            "keyword": self.input_keyword.text().strip(),
            "start_date": self.date_start.date(),
            "end_date": self.date_end.date(),
            "tag": self.combo_tag.currentText(),
            "min_priority": self.combo_priority.currentData()
        }

class StatsDialog(QDialog):
    def __init__(self, stats_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("数据统计分析")
        self.setFixedWidth(400)
        self.setStyleSheet("""
            QDialog { background-color: #2C2C2E; color: white; border-radius: 8px; }
            QLabel { color: #DDDDDD; font-size: 14px; }
            QProgressBar { border: 1px solid #555; border-radius: 5px; text-align: center; color: white; }
            QProgressBar::chunk { background-color: #0A84FF; border-radius: 4px; }
        """)
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        title = QLabel("📊 任务概览")
        title.setFont(get_font(16, True))
        layout.addWidget(title)
        grid = QGridLayout()
        grid.addWidget(QLabel("总任务数:"), 0, 0)
        grid.addWidget(QLabel(f"<b>{stats_data['total']}</b>"), 0, 1)
        grid.addWidget(QLabel("已完成:"), 1, 0)
        lbl_done = QLabel(f"<b>{stats_data['done']}</b>")
        lbl_done.setStyleSheet("color: #30D158;")
        grid.addWidget(lbl_done, 1, 1)
        grid.addWidget(QLabel("待办中:"), 2, 0)
        lbl_todo = QLabel(f"<b>{stats_data['todo']}</b>")
        lbl_todo.setStyleSheet("color: #FF9F0A;")
        grid.addWidget(lbl_todo, 2, 1)
        layout.addLayout(grid)
        layout.addSpacing(10)
        layout.addWidget(QLabel("完成率:"))
        progress = QProgressBar()
        progress.setRange(0, 100)
        rate = 0
        if stats_data['total'] > 0:
            rate = int((stats_data['done'] / stats_data['total']) * 100)
        progress.setValue(rate)
        layout.addWidget(progress)
        layout.addSpacing(10)
        layout.addWidget(QLabel(f"重要任务 (★3+): {stats_data['high_prio']} 个"))
        btn_close = QPushButton("关闭")
        btn_close.setObjectName("PrimaryButton")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

class PreferencesDialog(QDialog):
    def __init__(self, current_settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("偏好设置")
        self.setFixedWidth(350)
        self.setStyleSheet("""
            QDialog { background-color: #2C2C2E; color: white; border-radius: 8px; }
            QLabel { color: #DDDDDD; font-size: 14px; }
            QCheckBox { color: white; font-size: 14px; spacing: 8px; }
            QCheckBox::indicator { width: 18px; height: 18px; border-radius: 4px; border: 1px solid #555; }
            QCheckBox::indicator:checked { background-color: #0A84FF; border-color: #0A84FF; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        layout.addWidget(QLabel("通用设置", font=get_font(15, True)))
        self.chk_confirm_delete = QCheckBox("删除任务时弹窗确认")
        self.chk_confirm_delete.setChecked(current_settings.get("confirm_delete", True))
        layout.addWidget(self.chk_confirm_delete)
        self.chk_show_completed = QCheckBox("在日历中显示已完成的划线任务")
        self.chk_show_completed.setChecked(current_settings.get("show_completed_cal", True))
        self.chk_show_completed.setEnabled(False) 
        layout.addWidget(self.chk_show_completed)
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("保存")
        btn_save.setObjectName("PrimaryButton")
        btn_save.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)

    def get_settings(self):
        return {
            "confirm_delete": self.chk_confirm_delete.isChecked(),
            "show_completed_cal": self.chk_show_completed.isChecked()
        }

class BigCalendarWidget(QCalendarWidget):
    dayDoubleClicked = pyqtSignal(QDate)

    def __init__(self, task_manager, parent=None):
        super().__init__(parent)
        self.task_manager = task_manager
        self.active_tags_list = []
        self.tag_colors = {}
        self.date_rects = {} 
        self.setGridVisible(False)
        self.setNavigationBarVisible(False)
        self.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.setHorizontalHeaderFormat(QCalendarWidget.HorizontalHeaderFormat.ShortDayNames)
        self.view = self.findChild(QWidget, "qt_calendar_calendarview")
        if self.view:
            self.view.installEventFilter(self)
            try:
                self.view.viewport().installEventFilter(self)
                self.view.setMouseTracking(True)
                self.view.viewport().setMouseTracking(True)
            except: pass
        fmt = QTextCharFormat()
        fmt.setFont(get_font(14, bold=True)) 
        fmt.setForeground(QColor("#E0E0E0"))
        fmt.setBackground(QColor("#252525")) 
        self.setHeaderTextFormat(fmt)
        for day in [Qt.DayOfWeek.Monday, Qt.DayOfWeek.Tuesday, Qt.DayOfWeek.Wednesday, 
                    Qt.DayOfWeek.Thursday, Qt.DayOfWeek.Friday, Qt.DayOfWeek.Saturday, Qt.DayOfWeek.Sunday]:
            self.setWeekdayTextFormat(day, fmt)
        self.summary_cache = {} 
        self.currentPageChanged.connect(self.update_cache)
        
    def set_config(self, tags_list, colors_dict):
        self.active_tags_list = tags_list
        self.tag_colors = colors_dict
        self.update_cache()

    def update_cache(self):
        year = self.yearShown()
        month = self.monthShown()
        self.summary_cache = self.task_manager.get_month_task_summary(year, month, self.active_tags_list)
        self.date_rects = {}
        self.update()

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.MouseButtonDblClick:
            self.selected_date = self.selectedDate()
            self.dayDoubleClicked.emit(self.selected_date)
            return True 
        if event.type() == QEvent.Type.ToolTip:
            pos = event.pos()
            found_date = None
            for date, rect in self.date_rects.items():
                if rect.contains(pos):
                    found_date = date
                    break
            if found_date:
                tasks = self.task_manager.get_tasks_by_date_and_tags(found_date.toString("yyyy-MM-dd"), self.active_tags_list)
                if tasks:
                    tooltip_text = f"<b>{found_date.toString('yyyy-MM-dd')}</b><br>"
                    for t in tasks:
                        status_mark = "✅ " if t.status == "已完成" else "⬜ "
                        star_mark = "★" * t.priority if t.priority > 0 else ""
                        tooltip_text += f"{status_mark} [{t.tag}] {t.content} <span style='color:orange'>{star_mark}</span><br>"
                    QToolTip.showText(event.globalPos(), tooltip_text, watched, rect)
                else:
                    QToolTip.showText(event.globalPos(), "无事项", watched, rect)
                return True
        return super().eventFilter(watched, event)

    def paintCell(self, painter, rect, date):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.date_rects[date] = rect
        painter.fillRect(rect, QColor("#252525"))
        painter.setPen(QColor("#3A3A3A")) 
        painter.drawRect(rect)
        is_selected = (date == self.selectedDate())
        is_today = (date == QDate.currentDate())
        is_current_month = (date.month() == self.monthShown())
        date_str = date.toString("yyyy-MM-dd")
        task_info = self.summary_cache.get(date_str) 
        if is_today:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#FF3B30"))
            circle_size = 28
            circle_rect = QRect(rect.left() + 4, rect.top() + 4, circle_size, circle_size)
            painter.drawEllipse(circle_rect)
        elif is_selected:
            painter.fillRect(rect.adjusted(1,1,-1,-1), QColor(10, 132, 255, 40))
        if is_today: painter.setPen(QColor("white"))
        elif not is_current_month: painter.setPen(QColor("#555555")) 
        else: painter.setPen(QColor("#FFFFFF")) 
        font = get_font(14, bold=True)
        painter.setFont(font)
        date_rect = QRect(rect.left() + 8, rect.top() + 8, rect.width()-10, 30)
        if is_today:
             date_rect = QRect(rect.left() + 4, rect.top() + 4, 28, 28)
             painter.drawText(date_rect, Qt.AlignmentFlag.AlignCenter, str(date.day())) 
        else:
             painter.drawText(date_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, f"{date.day()}日")
        lunar_text, is_festival = DateUtils.get_lunar_text(date)
        if lunar_text:
            font_lunar = get_font(10)
            painter.setFont(font_lunar)
            if is_festival: painter.setPen(QColor("#FF453A")) 
            elif not is_current_month: painter.setPen(QColor("#444444"))
            else: painter.setPen(QColor("#999999")) 
            lunar_rect = QRect(rect.left(), rect.top() + 10, rect.width() - 8, 20)
            painter.drawText(lunar_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop, lunar_text)
        if task_info:
            color = QColor(task_info['color'])
            bar_height = 5
            bar_rect = QRect(rect.left() + 1, rect.bottom() - bar_height, rect.width() - 2, bar_height)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(bar_rect, 2, 2)
            bg_rect = QRect(rect.left() + 1, rect.bottom() - 24, rect.width() - 2, 20)
            color.setAlpha(30)
            painter.setBrush(color)
            painter.drawRect(bg_rect)
            painter.setPen(QColor("#CCCCCC"))
            font_tag = get_font(9)
            painter.setFont(font_tag)
            text_rect = QRect(rect.left() + 4, rect.bottom() - 24, rect.width()-8, 20)
            display_text = task_info['tag']
            priority = task_info.get('priority', 0)
            if priority > 0:
                display_text += " " + "★" * priority
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, display_text)
        painter.restore()

class TaskItemWidget(QWidget):
    def __init__(self, task, color_hex, show_date=False):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)
        
        bar = QFrame()
        bar.setFixedWidth(5)
        bar.setStyleSheet(f"background-color: {color_hex}; border-radius: 2.5px;")
        layout.addWidget(bar)
        
        content_layout = QVBoxLayout()
        content_layout.setSpacing(4)
        
        row1 = QHBoxLayout()
        title = QLabel(task.content)
        title.setFont(get_font(15, True))
        if task.status == "已完成":
            title.setStyleSheet("color: #777777; text-decoration: line-through;")
        else:
            title.setStyleSheet("color: #FFFFFF;")
        row1.addWidget(title)
        
        if task.priority > 0:
            stars = QLabel("★" * task.priority)
            stars.setStyleSheet("color: #FFD60A; font-size: 14px;")
            row1.addWidget(stars)
            
        content_layout.addLayout(row1)
        
        if task.description and task.description.strip():
            desc_lbl = QLabel(task.description)
            desc_lbl.setWordWrap(True)
            desc_lbl.setStyleSheet("color: #AAAAAA; font-size: 13px; margin-top: 2px; margin-bottom: 4px;")
            content_layout.addWidget(desc_lbl)
        
        row2 = QHBoxLayout()
        tag_lbl = QLabel(task.tag)
        tag_lbl.setStyleSheet(f"color: {color_hex}; font-size: 12px; font-weight: bold;")
        row2.addWidget(tag_lbl)
        
        # [New] Status Display after Tag
        status_text = f"[{task.status}]"
        status_lbl = QLabel(status_text)
        status_lbl.setStyleSheet("color: #777; font-size: 12px; margin-left: 5px;")
        row2.addWidget(status_lbl)
        
        if show_date:
            date_lbl = QLabel(f"📅 {task.date_str}")
            date_lbl.setStyleSheet("color: #888888; font-size: 12px; margin-left: 10px;")
            row2.addWidget(date_lbl)
            
        row2.addStretch()
        content_layout.addLayout(row2)
        
        layout.addLayout(content_layout)
        self.setStyleSheet("background-color: #333333; border-radius: 8px;")

class ManageMyDayApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Manage MyDay")
        self.resize(1200, 800) 
        
        self.set_app_icon()
        self.app_settings = QSettings("MyCompany", "ManageMyDay")
        
        self.db = TaskManager()
        self.current_tags = [] 
        self.active_tag_names = []
        self.is_details_expanded = False 
        
        self.search_mode = False
        self.search_filters = {}
        self.is_pinned = False # State for pin

        self.init_data()
        self.init_ui()
        self.init_menu()
        self.load_styles()
        
        # Initialize Mini Mode
        self.mini_widget = MiniModeWidget(self.db)
        self.mini_widget.restore_signal.connect(self.switch_to_normal_mode)
        
        self.refresh_view()

    def set_app_icon(self):
        IconLoader.ensure_dir()
        icon_path = resource_path(os.path.join(IconLoader.SAVE_DIR, "Task.ico"))
        if os.path.exists(icon_path):
            app_icon = QIcon(icon_path)
            self.setWindowIcon(app_icon)
            QApplication.setWindowIcon(app_icon)

    def init_data(self):
        tags = self.db.get_all_tags()
        self.current_tags = [(t.name, t.color) for t in tags]
        self.active_tag_names = [t[0] for t in self.current_tags] 

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0) 
        main_layout.setSpacing(0)
        
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(2)
        self.splitter.setStyleSheet("QSplitter::handle { background-color: #333333; }")
        
        # === Sidebar ===
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setMinimumWidth(240)
        sidebar.setStyleSheet("#Sidebar { background-color: #1C1C1E; }")
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(20, 25, 20, 25)
        
        # Nav
        row1_combo = QHBoxLayout()
        row1_combo.setSpacing(5)

        self.combo_year = QComboBox()
        self.combo_year.setObjectName("DateNavCombo")
        curr_year = QDate.currentDate().year()
        for y in range(curr_year - 10, curr_year + 11): 
            self.combo_year.addItem(f"{y}年", y)
        self.combo_year.setCurrentText(f"{curr_year}年")
        self.combo_year.currentIndexChanged.connect(self.jump_to_date_from_combo)
        
        self.combo_month = QComboBox()
        self.combo_month.setObjectName("DateNavCombo")
        for m in range(1, 13):
            self.combo_month.addItem(f"{m}月", m)
        self.combo_month.setCurrentIndex(QDate.currentDate().month() - 1)
        self.combo_month.currentIndexChanged.connect(self.jump_to_date_from_combo)

        row1_combo.addWidget(self.combo_year, 1)
        row1_combo.addWidget(self.combo_month, 0)
        side_layout.addLayout(row1_combo)
        
        row2_btns = QHBoxLayout()
        row2_btns.setSpacing(10)
        
        btn_prev = QPushButton()
        btn_prev.setFixedSize(30, 30)
        btn_prev.setObjectName("IconButton")
        btn_prev.setIcon(IconLoader.get("prev")) 
        btn_prev.clicked.connect(lambda: self.calendar.showPreviousMonth())
        
        # [修改] 使用文字 "今" 而不是图标
        btn_today = QPushButton("今") 
        btn_today.setFixedSize(50, 30)
        btn_today.setObjectName("IconButton")
        btn_today.setToolTip("回到今天")
        btn_today.clicked.connect(self.go_today)

        btn_next = QPushButton()
        btn_next.setFixedSize(30, 30)
        btn_next.setObjectName("IconButton")
        btn_next.setIcon(IconLoader.get("next")) 
        btn_next.clicked.connect(lambda: self.calendar.showNextMonth())

        row2_btns.addStretch()
        row2_btns.addWidget(btn_prev)
        row2_btns.addWidget(btn_today)
        row2_btns.addWidget(btn_next)
        row2_btns.addStretch()
        side_layout.addLayout(row2_btns)
        side_layout.addSpacing(20)
        
        # Add Task Button
        self.btn_add_sidebar = QPushButton(" 添加事项")
        self.btn_add_sidebar.setObjectName("PrimaryButton")
        self.btn_add_sidebar.setFixedHeight(40)
        icon_add = IconLoader.get("add")
        if not icon_add.isNull(): self.btn_add_sidebar.setIcon(icon_add)
        self.btn_add_sidebar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_add_sidebar.clicked.connect(self.open_add_task_dialog)
        side_layout.addWidget(self.btn_add_sidebar)
        
        side_layout.addSpacing(8)

        # Add Tag Button
        self.btn_add_tag_sidebar = QPushButton(" 新建标签")
        self.btn_add_tag_sidebar.setObjectName("PrimaryButton") 
        self.btn_add_tag_sidebar.setFixedHeight(40)
        if not icon_add.isNull(): self.btn_add_tag_sidebar.setIcon(icon_add) 
        self.btn_add_tag_sidebar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_add_tag_sidebar.clicked.connect(self.add_custom_tag)
        side_layout.addWidget(self.btn_add_tag_sidebar)
        
        side_layout.addSpacing(8)
        
        # [New] Mini Mode Button
        self.btn_mini_sidebar = QPushButton(" 悬浮便签")
        self.btn_mini_sidebar.setObjectName("PrimaryButton") 
        self.btn_mini_sidebar.setFixedHeight(40)
        self.btn_mini_sidebar.setStyleSheet("background-color: #EAB308; color: white;") # Different color for distinction
        self.btn_mini_sidebar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mini_sidebar.clicked.connect(self.switch_to_mini_mode)
        side_layout.addWidget(self.btn_mini_sidebar)
        
        side_layout.addSpacing(20)

        # Advanced Search
        btn_adv_search = QPushButton(" 高级搜索")
        btn_adv_search.setObjectName("SecondaryButton") 
        btn_adv_search.setStyleSheet("""
            QPushButton { background-color: #3A3A3C; color: white; border: none; border-radius: 6px; font-size: 14px; text-align: left; padding-left: 15px; }
            QPushButton:hover { background-color: #48484A; }
        """)
        btn_adv_search.setFixedHeight(36)
        icon_filter = IconLoader.get("search")
        if not icon_filter.isNull(): btn_adv_search.setIcon(icon_filter)
        btn_adv_search.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_adv_search.clicked.connect(self.open_advanced_search)
        side_layout.addWidget(btn_adv_search)
        
        side_layout.addSpacing(20)

        # Tag List
        lbl_tags = QLabel("我的标签")
        lbl_tags.setObjectName("SectionTitle")
        side_layout.addWidget(lbl_tags)
        
        self.scroll_tags = QScrollArea()
        self.scroll_tags.setWidgetResizable(True)
        self.scroll_tags.setStyleSheet("background: transparent; border: none;")
        self.tags_container = QWidget()
        self.tags_layout = QVBoxLayout(self.tags_container)
        self.tags_layout.setContentsMargins(0,0,0,0)
        self.tags_layout.setSpacing(8)
        self.tags_layout.addStretch() 
        self.scroll_tags.setWidget(self.tags_container)
        side_layout.addWidget(self.scroll_tags)
        
        # === Calendar ===
        self.calendar_container = QWidget()
        self.calendar_container.setObjectName("CalendarContainer")
        self.calendar_container.setStyleSheet("#CalendarContainer { background-color: #252525; }")
        cal_layout = QVBoxLayout(self.calendar_container)
        cal_layout.setContentsMargins(10, 10, 10, 10)

        self.calendar = BigCalendarWidget(self.db)
        self.calendar.currentPageChanged.connect(self.update_nav_combos_from_calendar) 
        self.calendar.dayDoubleClicked.connect(self.toggle_panel_by_double_click)
        self.calendar.clicked.connect(self.on_calendar_single_click) 
        cal_layout.addWidget(self.calendar)
        
        # === Right Panel ===
        self.right_panel = QWidget()
        self.right_panel.setObjectName("RightPanel")
        self.right_panel.setVisible(False) 
        self.right_panel.setMinimumWidth(300) 
        self.right_panel.setStyleSheet("#RightPanel { background-color: #1C1C1E; }")
        
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(25, 25, 25, 25)
        
        # Header
        r_header = QHBoxLayout()
        self.lbl_sel_date = QLabel("今天")
        self.lbl_sel_date.setFont(get_font(16, True)) 
        self.lbl_sel_date.setStyleSheet("color: white;")
        r_header.addWidget(self.lbl_sel_date)
        r_header.addStretch()
        
        btn_close = QPushButton()
        btn_close.setObjectName("IconButton")
        btn_close.setFixedSize(32, 32)
        btn_close.setToolTip("收起面板")
        btn_close.setIcon(IconLoader.get("close")) 
        btn_close.clicked.connect(self.collapse_panel)
        r_header.addWidget(btn_close)
        right_layout.addLayout(r_header)
        
        right_layout.addSpacing(15)
        
        # Simple Search
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(" 列表内筛选...")
        icon_search = IconLoader.get("search")
        if not icon_search.isNull():
            self.search_input.addAction(icon_search, QLineEdit.ActionPosition.LeadingPosition)
        self.search_input.textChanged.connect(self.refresh_task_list)
        right_layout.addWidget(self.search_input)
        
        # Task List
        self.task_list_widget = QListWidget()
        self.task_list_widget.setObjectName("TaskArea")
        self.task_list_widget.itemDoubleClicked.connect(self.toggle_task_complete)
        self.task_list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.task_list_widget.customContextMenuRequested.connect(self.show_context_menu)
        right_layout.addWidget(self.task_list_widget)
        
        # Inner Add Button
        btn_add_task_inner = QPushButton(" 添加事项")
        btn_add_task_inner.setObjectName("PrimaryButton")
        btn_add_task_inner.setFixedHeight(40)
        btn_add_task_inner.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add_task_inner.clicked.connect(self.open_add_task_dialog)
        right_layout.addWidget(btn_add_task_inner)
        
        self.splitter.addWidget(sidebar)
        self.splitter.addWidget(self.calendar_container)
        self.splitter.addWidget(self.right_panel)
        
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)

        main_layout.addWidget(self.splitter)
        
        # Removed DraggableButton (Pin Icon)

    def init_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("文件")
        
        act_import = QAction(IconLoader.get("import"), "导入数据...", self)
        act_import.triggered.connect(self.import_data)
        file_menu.addAction(act_import)
        
        act_export = QAction(IconLoader.get("export"), "导出数据...", self)
        act_export.triggered.connect(self.export_data)
        file_menu.addAction(act_export)
        
        file_menu.addSeparator()
        
        act_exit = QAction(IconLoader.get("exit"), "退出", self)
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)

        view_menu = menubar.addMenu("界面")
        
        # [New] Pin to Top Action
        self.act_pin_top = QAction(IconLoader.get("pin"), "📌 置于桌面顶层", self)
        self.act_pin_top.setCheckable(True)
        self.act_pin_top.triggered.connect(self.toggle_stay_on_top)
        view_menu.addAction(self.act_pin_top)

        view_menu.addSeparator()

        expand_action = QAction(IconLoader.get("reset_layout"), "恢复默认布局", self)
        expand_action.triggered.connect(self.reset_layout)
        view_menu.addAction(expand_action)
        
        toggle_side = QAction(IconLoader.get("sidebar"), "显示/隐藏侧边栏", self)
        toggle_side.triggered.connect(self.toggle_sidebar)
        view_menu.addAction(toggle_side)
        
        tools_menu = menubar.addMenu("工具")
        
        act_stats = QAction(IconLoader.get("stats"), "统计分析", self)
        act_stats.triggered.connect(self.show_statistics)
        tools_menu.addAction(act_stats)
        
        act_backup = QAction(IconLoader.get("backup"), "本地备份", self)
        act_backup.triggered.connect(self.create_backup)
        tools_menu.addAction(act_backup)
        
        settings_menu = menubar.addMenu("设置")
        settings_action = QAction(IconLoader.get("settings"), "偏好设置...", self)
        settings_action.triggered.connect(self.show_preferences)
        settings_menu.addAction(settings_action)

        help_menu = menubar.addMenu("帮助")
        about_action = QAction(IconLoader.get("about"), "关于", self)
        about_action.triggered.connect(lambda: QMessageBox.about(self, "关于", "Manage MyDay \n\n高效的任务管理工具。\n集成日历、任务追踪与数据分析。"))
        help_menu.addAction(about_action)

    # --- Mode Switching ---
    
    def switch_to_mini_mode(self):
        self.mini_widget.load_data()
        self.hide()
        self.mini_widget.show()
        # Ensure it appears center-ish or remember position
        if not self.mini_widget.old_pos:
            screen_geo = self.screen().geometry()
            self.mini_widget.move(
                screen_geo.center().x() - self.mini_widget.width() // 2,
                screen_geo.center().y() - self.mini_widget.height() // 2
            )
            
    def switch_to_normal_mode(self):
        self.mini_widget.hide()
        self.refresh_task_list() # refresh main list just in case
        self.calendar.update_cache()
        self.show()
        self.activateWindow()

    # --- Core Logic ---
    
    def get_db_path(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        path_in_script_dir = os.path.join(script_dir, "myday.db")
        if os.path.exists(path_in_script_dir): return path_in_script_dir
        path_in_cwd = os.path.join(os.getcwd(), "myday.db")
        if os.path.exists(path_in_cwd): return path_in_cwd
        return path_in_script_dir

    def create_backup(self):
        backup_dir = "backups"
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
            
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(backup_dir, f"myday_backup_{timestamp}.db")
        source_path = self.get_db_path()
        
        try:
            if not os.path.exists(source_path):
                QMessageBox.warning(self, "提示", f"未找到数据库文件 (myday.db)。")
                return
            shutil.copy(source_path, backup_file)
            QMessageBox.information(self, "成功", f"数据库备份已创建:\n{backup_file}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"备份失败: {str(e)}")

    def export_data(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "导出数据", "myday_export.json", "JSON Files (*.json)")
        if not file_path: return
            
        source_path = self.get_db_path()
        if not os.path.exists(source_path): return

        try:
            conn = sqlite3.connect(source_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name, color FROM tags")
            tags_data = [{"name": row[0], "color": row[1]} for row in cursor.fetchall()]
            
            # Export description too
            cursor.execute("SELECT id, date_str, content, status, tag, priority, description FROM tasks")
            tasks_data = [
                {"id": r[0], "date_str": r[1], "content": r[2], "status": r[3], "tag": r[4], "priority": r[5], "description": r[6]}
                for r in cursor.fetchall()
            ]
            conn.close()
            
            export_data = {"version": "1.1", "tags": tags_data, "tasks": tasks_data}
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=4)
            QMessageBox.information(self, "成功", f"数据已成功导出为 JSON:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出失败: {str(e)}")

    def import_data(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "导入数据", "", "JSON Files (*.json)")
        if not file_path: return
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if "tasks" not in data: raise ValueError("无效的数据文件格式: 缺少 tasks 字段")
            
            db_path = self.get_db_path()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            if "tags" in data:
                for tag in data["tags"]:
                    try: cursor.execute("INSERT OR IGNORE INTO tags (name, color) VALUES (?, ?)", (tag["name"], tag["color"]))
                    except: pass
            
            count = 0
            for task in data["tasks"]:
                cursor.execute(
                    "INSERT INTO tasks (date_str, content, status, tag, priority, description) VALUES (?, ?, ?, ?, ?, ?)",
                    (task["date_str"], task["content"], task["status"], task["tag"], task.get("priority", 0), task.get("description", ""))
                )
                count += 1
            
            conn.commit()
            conn.close()
            self.db = TaskManager() 
            self.init_data()
            self.refresh_view()
            self.calendar.update_cache()
            QMessageBox.information(self, "成功", f"成功导入 {count} 条任务！")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导入失败: {str(e)}")

    def show_statistics(self):
        source_path = self.get_db_path()
        if not os.path.exists(source_path): return
        try:
            conn = sqlite3.connect(source_path)
            cursor = conn.cursor()
            cursor.execute("SELECT count(*) FROM tasks")
            total = cursor.fetchone()[0]
            cursor.execute("SELECT count(*) FROM tasks WHERE status IN ('DONE', '已完成')")
            done = cursor.fetchone()[0]
            cursor.execute("SELECT count(*) FROM tasks WHERE priority >= 3")
            high_prio = cursor.fetchone()[0]
            conn.close()
            
            stats = {"total": total, "done": done, "todo": total - done, "high_prio": high_prio}
            dlg = StatsDialog(stats, self)
            dlg.exec()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"统计分析失败: {str(e)}")

    def show_preferences(self):
        confirm = self.app_settings.value("confirm_delete", True, type=bool)
        show_cal = self.app_settings.value("show_completed_cal", True, type=bool)
        dlg = PreferencesDialog({"confirm_delete": confirm, "show_completed_cal": show_cal}, self)
        if dlg.exec():
            new_settings = dlg.get_settings()
            self.app_settings.setValue("confirm_delete", new_settings["confirm_delete"])
            self.app_settings.setValue("show_completed_cal", new_settings["show_completed_cal"])

    def reset_layout(self):
        self.right_panel.setVisible(True)
        self.is_details_expanded = True
        self.refresh_task_list()
        total_width = self.width()
        self.splitter.setSizes([260, total_width - 610, 350])
        
    def toggle_sidebar(self):
        sidebar = self.splitter.widget(0)
        sidebar.setVisible(not sidebar.isVisible())

    def toggle_stay_on_top(self, checked):
        if checked:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
            self.act_pin_top.setText("📌 取消置顶")
        else:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)
            self.act_pin_top.setText("📌 置于桌面顶层")
        self.show()

    def load_styles(self):
        with open(resource_path("mac_style.qss"), "r", encoding="utf-8") as f:
             self.setStyleSheet(f.read())

    def jump_to_date_from_combo(self):
        y = self.combo_year.currentData()
        m = self.combo_month.currentData()
        if y and m:
            self.calendar.blockSignals(True) 
            self.calendar.setCurrentPage(y, m)
            self.calendar.blockSignals(False)
            self.calendar.update_cache()

    def update_nav_combos_from_calendar(self):
        year = self.calendar.yearShown()
        month = self.calendar.monthShown()
        self.combo_year.blockSignals(True)
        self.combo_month.blockSignals(True)
        idx_y = self.combo_year.findData(year)
        if idx_y == -1:
            self.combo_year.addItem(f"{year}年", year)
            self.combo_year.setCurrentIndex(self.combo_year.count()-1)
        else:
            self.combo_year.setCurrentIndex(idx_y)
        self.combo_month.setCurrentIndex(month - 1)
        self.combo_year.blockSignals(False)
        self.combo_month.blockSignals(False)
        self.calendar.update_cache()

    def go_today(self):
        today = QDate.currentDate()
        self.calendar.setSelectedDate(today)
        self.calendar.setCurrentPage(today.year(), today.month())

    def refresh_view(self):
        self.render_sidebar_tags()
        tag_colors = {name: color for name, color in self.current_tags}
        self.calendar.set_config(self.active_tag_names, tag_colors)
        self.update_nav_combos_from_calendar()
        
    def render_sidebar_tags(self):
        for i in range(self.tags_layout.count()):
            item = self.tags_layout.itemAt(i)
            if item.widget(): item.widget().deleteLater()
        self.tag_checkboxes = []
        for name, color in self.current_tags:
            cb = QCheckBox(name)
            cb.setChecked(name in self.active_tag_names)
            cb.setStyleSheet(f"QCheckBox {{ color: {color}; font-size: 15px; }}") 
            cb.stateChanged.connect(self.on_tag_filter_changed)
            self.tags_layout.insertWidget(self.tags_layout.count()-1, cb) 
            self.tag_checkboxes.append((cb, name))

    def on_tag_filter_changed(self):
        self.active_tag_names = [name for cb, name in self.tag_checkboxes if cb.isChecked()]
        self.refresh_view() 
        if self.is_details_expanded: self.refresh_task_list()

    def add_custom_tag(self):
        dlg = AddTagDialog(self)
        if dlg.exec():
            name, color = dlg.get_data()
            if name:
                if self.db.add_custom_tag(name, color):
                    self.current_tags.append((name, color))
                    self.active_tag_names.append(name) 
                    self.refresh_view()
                else:
                    QMessageBox.warning(self, "错误", "标签名称已存在")

    def on_calendar_single_click(self):
        self.search_mode = False
        if self.is_details_expanded: self.refresh_task_list()

    def toggle_panel_by_double_click(self, date):
        self.search_mode = False 
        if self.is_details_expanded:
            self.collapse_panel()
        else:
            self.expand_panel()
            self.refresh_task_list()

    def expand_panel(self):
        self.is_details_expanded = True
        self.right_panel.setVisible(True)
        self.refresh_task_list()
        
    def collapse_panel(self):
        self.is_details_expanded = False
        self.right_panel.setVisible(False)

    def open_advanced_search(self):
        tag_names = [t[0] for t in self.current_tags]
        dlg = AdvancedSearchDialog(tag_names, self)
        if dlg.exec():
            self.search_filters = dlg.get_filters()
            self.search_mode = True
            self.expand_panel()
            self.refresh_task_list()

    def refresh_task_list(self):
        if not self.is_details_expanded: return
        
        colors = {n: c for n, c in self.current_tags}
        self.task_list_widget.clear()

        if self.search_mode:
            self.lbl_sel_date.setText("🔍 搜索结果")
            f = self.search_filters
            start = f['start_date']
            end = f['end_date']
            target_tag = f['tag']
            min_prio = f['min_priority']
            keyword = f['keyword']
            
            all_results = []
            days_span = start.daysTo(end)
            if days_span > 365: days_span = 365
            
            for i in range(days_span + 1):
                curr_date = start.addDays(i)
                d_str = curr_date.toString("yyyy-MM-dd")
                search_tags = [target_tag] if target_tag != "全部" else self.active_tag_names
                day_tasks = self.db.get_tasks_by_date_and_tags(d_str, search_tags)
                for t in day_tasks:
                    if min_prio != -1 and t.priority < min_prio: continue
                    if keyword and (keyword not in t.content and keyword not in t.description): continue
                    all_results.append(t)
            
            if not all_results:
                item = QListWidgetItem("未找到匹配事项")
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setFlags(Qt.ItemFlag.NoItemFlags) 
                self.task_list_widget.addItem(item)
            else:
                for task in all_results:
                    item = QListWidgetItem()
                    widget = TaskItemWidget(task, colors.get(task.tag, "#888888"), show_date=True)
                    item.setSizeHint(widget.sizeHint())
                    item.setData(Qt.ItemDataRole.UserRole, task)
                    self.task_list_widget.addItem(item)
                    self.task_list_widget.setItemWidget(item, widget)
        else:
            date_str = self.calendar.selectedDate().toString("yyyy-MM-dd")
            self.lbl_sel_date.setText(self.calendar.selectedDate().toString("M月d日 dddd"))
            
            tasks = self.db.get_tasks_by_date_and_tags(date_str, self.active_tag_names)
            
            keyword = self.search_input.text().strip()
            if keyword: tasks = [t for t in tasks if (keyword in t.content or keyword in t.description)]
            
            for task in tasks:
                item = QListWidgetItem()
                widget = TaskItemWidget(task, colors.get(task.tag, "#888888"), show_date=False)
                item.setSizeHint(widget.sizeHint())
                item.setData(Qt.ItemDataRole.UserRole, task)
                self.task_list_widget.addItem(item)
                self.task_list_widget.setItemWidget(item, widget)

    def open_add_task_dialog(self):
        colors = {n: c for n, c in self.current_tags}
        dlg = TaskDialog(colors, self)
        if dlg.exec():
            data = dlg.get_data()
            if data['content']:
                date_str = self.calendar.selectedDate().toString("yyyy-MM-dd")
                self.db.add_task(date_str, data['content'], data['status'], data['tag'], data['priority'], data['description'])
                self.calendar.update_cache() 
                self.refresh_task_list()
                if self.mini_widget.isVisible(): self.mini_widget.load_data()

    def open_edit_task_dialog(self, task):
        colors = {n: c for n, c in self.current_tags}
        dlg = TaskDialog(colors, self, task=task) # Pass task for editing
        if dlg.exec():
            data = dlg.get_data()
            if data['content']:
                self.db.update_task_info(task.id, data['content'], data['tag'], data['priority'], data['description'])
                self.calendar.update_cache()
                self.refresh_task_list()
                if self.mini_widget.isVisible(): self.mini_widget.load_data()

    def toggle_task_complete(self, item):
        task = item.data(Qt.ItemDataRole.UserRole)
        if not task: return
        new_status = "已完成" if task.status != "已完成" else "待完成"
        self.db.update_task_status(task.id, new_status)
        self.refresh_task_list()
        if self.mini_widget.isVisible(): self.mini_widget.load_data()

    def show_context_menu(self, pos):
        item = self.task_list_widget.itemAt(pos)
        if not item: return
        task = item.data(Qt.ItemDataRole.UserRole)
        if not task: return

        menu = QMenu(self)
        
        # Edit Action
        edit_action = QAction("✏️ 编辑任务 / 详细", self)
        edit_action.triggered.connect(lambda: self.open_edit_task_dialog(task))
        menu.addAction(edit_action)
        
        menu.addSeparator()

        p_menu = menu.addMenu("⭐ 设为重要")
        for i in range(6):
            action = QAction(f"{i} 星", self)
            action.triggered.connect(lambda checked, t=task.id, p=i: self.update_task_attr(t, 'priority', p))
            p_menu.addAction(action)
            
        s_menu = menu.addMenu("📝 更改状态")
        for s in ["待完成", "进行中", "已完成", "搁置"]:
            action = QAction(s, self)
            action.triggered.connect(lambda checked, t=task.id, val=s: self.update_task_attr(t, 'status', val))
            s_menu.addAction(action)
            
        menu.addSeparator()
        del_action = QAction("🗑️ 删除任务", self)
        del_action.triggered.connect(lambda: self.delete_task(task.id))
        menu.addAction(del_action)
        
        menu.exec(self.task_list_widget.mapToGlobal(pos))

    def update_task_attr(self, task_id, attr, value):
        if attr == 'priority':
            self.db.update_task_priority(task_id, value)
        elif attr == 'status':
            self.db.update_task_status(task_id, value)
        self.refresh_task_list()
        self.calendar.update_cache()
        if self.mini_widget.isVisible(): self.mini_widget.load_data()

    def delete_task(self, task_id):
        confirm_needed = self.app_settings.value("confirm_delete", True, type=bool)
        if confirm_needed:
            reply = QMessageBox.question(self, "确认删除", "确定要删除这个事项吗？",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No: return
        self.db.delete_task(task_id)
        self.refresh_task_list()
        self.calendar.update_cache()
        if self.mini_widget.isVisible(): self.mini_widget.load_data()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ManageMyDayApp()
    window.show()
    sys.exit(app.exec())