import sqlite3
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict

@dataclass
class Task:
    id: int
    date_str: str
    content: str
    status: str
    tag: str
    priority: int = 0
    description: str = "" # [New] Task description

@dataclass
class Tag:
    name: str
    color: str

class TaskManager:
    DB_NAME = "myday.db"
    
    # Default preset tags
    DEFAULT_TAGS = [
        ("工作", "#5E5CE6"), # Indigo
        ("生活", "#30D158"), # Green
        ("学习", "#FF9F0A"), # Orange
        ("健康", "#FF453A"), # Red
        ("其他", "#BF5AF2"), # Purple
    ]

    def __init__(self):
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.DB_NAME)
        cursor = conn.cursor()
        
        # 1. Tasks Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date_str TEXT NOT NULL,
                content TEXT NOT NULL,
                status TEXT NOT NULL,
                tag TEXT NOT NULL,
                priority INTEGER DEFAULT 0,
                description TEXT DEFAULT ''
            )
        ''')
        
        # [Migration] Ensure tasks table has priority and description columns
        cursor.execute("PRAGMA table_info(tasks)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if "priority" not in columns:
            cursor.execute("ALTER TABLE tasks ADD COLUMN priority INTEGER DEFAULT 0")
            
        if "description" not in columns:
            cursor.execute("ALTER TABLE tasks ADD COLUMN description TEXT DEFAULT ''")

        # 2. Tags Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tags (
                name TEXT PRIMARY KEY,
                color TEXT NOT NULL
            )
        ''')
        
        # Initialize default tags
        cursor.execute("SELECT count(*) FROM tags")
        if cursor.fetchone()[0] == 0:
            cursor.executemany("INSERT INTO tags (name, color) VALUES (?, ?)", self.DEFAULT_TAGS)
            
        conn.commit()
        conn.close()

    # --- Tag Management ---
    def get_all_tags(self) -> List[Tag]:
        conn = sqlite3.connect(self.DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT name, color FROM tags")
        rows = cursor.fetchall()
        conn.close()
        return [Tag(*row) for row in rows]

    def add_custom_tag(self, name: str, color: str) -> bool:
        try:
            conn = sqlite3.connect(self.DB_NAME)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO tags (name, color) VALUES (?, ?)", (name, color))
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            return False

    # --- Task Management ---
    def add_task(self, date_str: str, content: str, status: str, tag: str, priority: int = 0, description: str = "") -> None:
        conn = sqlite3.connect(self.DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO tasks (date_str, content, status, tag, priority, description) VALUES (?, ?, ?, ?, ?, ?)",
            (date_str, content, status, tag, priority, description)
        )
        conn.commit()
        conn.close()

    def update_task_status(self, task_id: int, new_status: str) -> None:
        conn = sqlite3.connect(self.DB_NAME)
        cursor = conn.cursor()
        cursor.execute("UPDATE tasks SET status = ? WHERE id = ?", (new_status, task_id))
        conn.commit()
        conn.close()
        
    def update_task_priority(self, task_id: int, priority: int) -> None:
        conn = sqlite3.connect(self.DB_NAME)
        cursor = conn.cursor()
        cursor.execute("UPDATE tasks SET priority = ? WHERE id = ?", (priority, task_id))
        conn.commit()
        conn.close()

    # [New] Update comprehensive task info
    def update_task_info(self, task_id: int, content: str, tag: str, priority: int, description: str) -> None:
        conn = sqlite3.connect(self.DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE tasks SET content = ?, tag = ?, priority = ?, description = ? WHERE id = ?", 
            (content, tag, priority, description, task_id)
        )
        conn.commit()
        conn.close()

    def delete_task(self, task_id: int) -> None:
        conn = sqlite3.connect(self.DB_NAME)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
        conn.close()

    # --- Queries ---
    def get_tasks_by_date_and_tags(self, date_str: str, active_tags: List[str]) -> List[Task]:
        if not active_tags: return []
        conn = sqlite3.connect(self.DB_NAME)
        cursor = conn.cursor()
        placeholders = ','.join('?' for _ in active_tags)
        # Select all fields including description
        query = f"""
            SELECT id, date_str, content, status, tag, priority, description 
            FROM tasks 
            WHERE date_str = ? AND tag IN ({placeholders})
            ORDER BY priority DESC, id ASC
        """
        cursor.execute(query, [date_str] + active_tags)
        rows = cursor.fetchall()
        conn.close()
        return [Task(*row) for row in rows]

    def search_tasks(self, keyword: str) -> List[Task]:
        conn = sqlite3.connect(self.DB_NAME)
        cursor = conn.cursor()
        # Search in content or description
        cursor.execute("""
            SELECT id, date_str, content, status, tag, priority, description 
            FROM tasks 
            WHERE content LIKE ? OR description LIKE ? 
            ORDER BY date_str DESC
        """, (f"%{keyword}%", f"%{keyword}%"))
        rows = cursor.fetchall()
        conn.close()
        return [Task(*row) for row in rows]

    # --- Calendar Summary ---
    def get_month_task_summary(self, year: int, month: int, active_tags: List[str]) -> dict:
        """
        Get task summary for calendar view.
        """
        if not active_tags: return {}
        
        conn = sqlite3.connect(self.DB_NAME)
        cursor = conn.cursor()
        month_str = f"{year}-{month:02d}-%"
        placeholders = ','.join('?' for _ in active_tags)
        
        query = f"""
            SELECT date_str, tag, priority 
            FROM tasks 
            WHERE date_str LIKE ? AND tag IN ({placeholders})
            ORDER BY priority DESC, id ASC
        """
        cursor.execute(query, [month_str] + active_tags)
        rows = cursor.fetchall()
        
        cursor.execute("SELECT name, color FROM tags")
        tag_rows = cursor.fetchall()
        conn.close()

        tags_info = {name: color for name, color in tag_rows}
        
        summary = {}
        for date_str, tag_name, priority in rows:
            if date_str not in summary:
                summary[date_str] = {
                    'color': tags_info.get(tag_name, '#8E8E93'),
                    'priority': priority,
                    'tag': tag_name
                }
        
        return summary