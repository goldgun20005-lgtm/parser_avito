import sqlite3

from loguru import logger

from models import Item


class SQLiteDBHandler:
    """Работа с БД sqlite (память уже просмотренных объявлений).

    Дедупликация по составному ключу (id, price): смена цены => объявление
    считается новым. PRIMARY KEY (id, price) исключает дубли строк и
    неограниченный рост таблицы. Включён режим WAL для надёжности записи.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(SQLiteDBHandler, cls).__new__(cls)
        return cls._instance

    def __init__(self, db_name="database.db"):
        if not hasattr(self, "_initialized"):
            self.db_name = db_name
            self._init_db()
            self._initialized = True

    def _init_db(self):
        """Создаёт/мигрирует таблицу и включает WAL (в autocommit, без транзакций)."""
        conn = sqlite3.connect(self.db_name, isolation_level=None)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            self._create_table(conn)
            self._migrate_if_needed(conn)
        finally:
            conn.close()

    @staticmethod
    def _create_table(conn):
        """Создаёт таблицу viewed с составным первичным ключом, если её нет."""
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS viewed (
                id INTEGER,
                price INTEGER,
                PRIMARY KEY (id, price)
            )
            """
        )

    def _migrate_if_needed(self, conn):
        """Мигрирует БД, созданную старой версией без PRIMARY KEY (с дедупом строк)."""
        cols = conn.execute("PRAGMA table_info(viewed)").fetchall()
        # элемент c[5] == pk: 0 если столбец не входит в первичный ключ
        pk_cols = {c[1] for c in cols if c[5] > 0}
        if pk_cols == {"id", "price"}:
            return  # схема уже актуальная

        logger.info("Миграция таблицы viewed -> PRIMARY KEY (id, price) + дедупликация строк")
        conn.execute("ALTER TABLE viewed RENAME TO viewed_old")
        self._create_table(conn)
        conn.execute(
            "INSERT OR IGNORE INTO viewed (id, price) "
            "SELECT DISTINCT id, price FROM viewed_old"
        )
        conn.execute("DROP TABLE viewed_old")
        logger.info("Миграция viewed завершена")

    def add_record(self, ad: Item):
        """Добавляет новую запись в таблицу viewed (без дублей)."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO viewed (id, price) VALUES (?, ?)",
                (ad.id, ad.priceDetailed.value),
            )
            conn.commit()

    def add_record_from_page(self, ads: list[Item]):
        """Добавляет несколько записей в таблицу viewed (без дублей)."""
        records = [(ad.id, ad.priceDetailed.value) for ad in ads]

        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.executemany(
                "INSERT OR IGNORE INTO viewed (id, price) VALUES (?, ?)",
                records,
            )
            conn.commit()

    def record_exists(self, record_id, price):
        """Проверяет, существует ли запись с заданными id и price."""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM viewed WHERE id = ? AND price = ?",
                (record_id, price),
            )
            return cursor.fetchone() is not None
