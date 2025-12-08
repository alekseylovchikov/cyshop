import sqlite3
import json
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
from typing import Optional


class AdStatus(Enum):
    PENDING = "pending"      # На модерации
    APPROVED = "approved"    # Одобрено
    REJECTED = "rejected"    # Отклонено


@dataclass
class BannedUser:
    user_id: int
    username: Optional[str]
    reason: str
    banned_at: datetime
    banned_by: int


@dataclass
class Advertisement:
    id: int
    user_id: int
    username: Optional[str]
    first_name: str
    description: str
    photo_ids: list[str]
    status: AdStatus
    reject_reason: Optional[str]
    created_at: datetime
    moderated_at: Optional[datetime]
    published_message_id: Optional[int]


class Database:
    def __init__(self, db_path: str = "ads.db"):
        self.db_path = db_path
        self._create_tables()
    
    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _create_tables(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS advertisements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    first_name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    photo_ids TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    reject_reason TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    moderated_at TIMESTAMP,
                    published_message_id INTEGER
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_status ON advertisements(status)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_id ON advertisements(user_id)
            """)
            # Таблица забаненных пользователей
            conn.execute("""
                CREATE TABLE IF NOT EXISTS banned_users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    reason TEXT NOT NULL,
                    banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    banned_by INTEGER NOT NULL
                )
            """)
            conn.commit()
    
    def add_advertisement(
        self,
        user_id: int,
        username: Optional[str],
        first_name: str,
        description: str,
        photo_ids: list[str]
    ) -> int:
        """Добавляет новое объявление и возвращает его ID"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO advertisements (user_id, username, first_name, description, photo_ids)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, username, first_name, description, json.dumps(photo_ids))
            )
            conn.commit()
            return cursor.lastrowid
    
    def get_advertisement(self, ad_id: int) -> Optional[Advertisement]:
        """Получает объявление по ID"""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM advertisements WHERE id = ?",
                (ad_id,)
            ).fetchone()
            
            if row:
                return self._row_to_ad(row)
            return None
    
    def get_pending_advertisements(self) -> list[Advertisement]:
        """Получает все объявления на модерации"""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM advertisements WHERE status = 'pending' ORDER BY created_at ASC"
            ).fetchall()
            return [self._row_to_ad(row) for row in rows]
    
    def get_user_advertisements(self, user_id: int) -> list[Advertisement]:
        """Получает все объявления пользователя"""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM advertisements WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,)
            ).fetchall()
            return [self._row_to_ad(row) for row in rows]
    
    def approve_advertisement(self, ad_id: int, message_id: int) -> bool:
        """Одобряет объявление"""
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE advertisements 
                SET status = 'approved', moderated_at = ?, published_message_id = ?
                WHERE id = ?
                """,
                (datetime.now(), message_id, ad_id)
            )
            conn.commit()
            return conn.total_changes > 0
    
    def reject_advertisement(self, ad_id: int, reason: str) -> bool:
        """Отклоняет объявление с указанием причины"""
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE advertisements 
                SET status = 'rejected', reject_reason = ?, moderated_at = ?
                WHERE id = ?
                """,
                (reason, datetime.now(), ad_id)
            )
            conn.commit()
            return conn.total_changes > 0
    
    def get_pending_count(self) -> int:
        """Возвращает количество объявлений на модерации"""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as count FROM advertisements WHERE status = 'pending'"
            ).fetchone()
            return row['count']
    
    def get_user_ads_today(self, user_id: int) -> int:
        """Возвращает количество объявлений пользователя за сегодня"""
        with self._get_connection() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) as count FROM advertisements 
                WHERE user_id = ? AND date(created_at) = date('now', 'localtime')
                """,
                (user_id,)
            ).fetchone()
            return row['count']
    
    def ban_user(self, user_id: int, username: Optional[str], reason: str, banned_by: int) -> bool:
        """Банит пользователя"""
        with self._get_connection() as conn:
            try:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO banned_users (user_id, username, reason, banned_at, banned_by)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (user_id, username, reason, datetime.now(), banned_by)
                )
                conn.commit()
                return True
            except Exception:
                return False
    
    def unban_user(self, user_id: int) -> bool:
        """Разбанивает пользователя"""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM banned_users WHERE user_id = ?", (user_id,))
            conn.commit()
            return conn.total_changes > 0
    
    def is_banned(self, user_id: int) -> bool:
        """Проверяет, забанен ли пользователь"""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM banned_users WHERE user_id = ?",
                (user_id,)
            ).fetchone()
            return row is not None
    
    def get_ban_info(self, user_id: int) -> Optional[BannedUser]:
        """Получает информацию о бане пользователя"""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM banned_users WHERE user_id = ?",
                (user_id,)
            ).fetchone()
            if row:
                return BannedUser(
                    user_id=row['user_id'],
                    username=row['username'],
                    reason=row['reason'],
                    banned_at=datetime.fromisoformat(row['banned_at']) if row['banned_at'] else None,
                    banned_by=row['banned_by']
                )
            return None
    
    def get_banned_users(self) -> list[BannedUser]:
        """Получает список всех забаненных пользователей"""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM banned_users ORDER BY banned_at DESC"
            ).fetchall()
            return [
                BannedUser(
                    user_id=row['user_id'],
                    username=row['username'],
                    reason=row['reason'],
                    banned_at=datetime.fromisoformat(row['banned_at']) if row['banned_at'] else None,
                    banned_by=row['banned_by']
                )
                for row in rows
            ]
    
    def _row_to_ad(self, row: sqlite3.Row) -> Advertisement:
        """Конвертирует строку БД в объект Advertisement"""
        return Advertisement(
            id=row['id'],
            user_id=row['user_id'],
            username=row['username'],
            first_name=row['first_name'],
            description=row['description'],
            photo_ids=json.loads(row['photo_ids']),
            status=AdStatus(row['status']),
            reject_reason=row['reject_reason'],
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            moderated_at=datetime.fromisoformat(row['moderated_at']) if row['moderated_at'] else None,
            published_message_id=row['published_message_id']
        )


# Глобальный экземпляр базы данных
db = Database()

