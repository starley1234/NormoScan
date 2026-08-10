"""
Koseven (Kohana) RBAC adapter.

Koseven — любимый фреймворк заказчика (PHP). Интеграция через:
 1) Общая БД пользователей (таблица koseven_users) или
 2) HTTP header X-Koseven-Role / X-Koseven-UserId от прокси
 3) JWT bridge (Koseven подписывает JWT тем же SECRET_KEY)

Таблица koseven_users (пример):
  id INT PK
  username VARCHAR
  email VARCHAR
  password VARCHAR (bcrypt)
  role VARCHAR  -- 'admin','normocontrol','engineer','user'
  logins INT
  last_login INT

Маппинг ролей:
  Koseven 'admin'        -> NormoScan 'admin'
  Koseven 'normocontrol' -> NormoScan 'normocontroller'
  Koseven 'engineer'     -> NormoScan 'engineer'
  Koseven 'user'         -> NormoScan 'viewer'

Настройка в .env:
  KOSEVEN_ENABLED=true
  KOSEVEN_DB_DSN=mysql://user:pass@koseven-host/kosedb
  KOSEVEN_TABLE=koseven_users
  SECRET_KEY=совпадает с Koseven Auth::$hash_key
"""


from sqlalchemy import create_engine, text

ROLE_MAP = {
    "admin": "admin",
    "normocontrol": "normocontroller",
    "normocontroller": "normocontroller",
    "engineer": "engineer",
    "user": "viewer",
    "viewer": "viewer",
}

def map_koseven_role(koseven_role: str) -> str:
    return ROLE_MAP.get(koseven_role.lower(), "viewer")

def get_koseven_user(dsn: str, table: str, username: str) -> dict | None:
    """
    Запрос пользователя из Koseven БД (read-only).
    Возвращает dict или None.
    """
    if not dsn:
        return None
    engine = create_engine(dsn)
    with engine.connect() as conn:
        row = conn.execute(text(f"SELECT id, username, email, role FROM {table} WHERE username=:u LIMIT 1"), {"u": username}).mappings().first()
        if row:
            return dict(row)
    return None

def verify_koseven_session(cookie_value: str, secret: str) -> dict | None:
    """
    Проверка сессии Koseven (если используете Cookie-based auth).
    Koseven хранит сессию в cookie 'koseven_session' — base64 + hmac.
    Здесь упрощено: ожидается JWT подписанный тем же SECRET_KEY.
    """
    try:
        from jose import jwt
        payload = jwt.decode(cookie_value, secret, algorithms=["HS256"])
        return payload
    except Exception:
        return None

# Пример middleware (используется в security.py get_current_user_optional)
# headers:
#   X-Koseven-Role: normocontrol
#   X-Koseven-UserId: 42
#   X-Koseven-Username: ivan
