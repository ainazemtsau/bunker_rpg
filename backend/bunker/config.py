import os
from pathlib import Path


class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    DEBUG = False
    # Для будущей БД/Redis можно задать здесь:
    # SQLALCHEMY_DATABASE_URI = 'sqlite:///' + str(Path(__file__).with_suffix('.db'))
    # CELERY_BROKER_URL = 'redis://localhost:6379/0'


class DevConfig(BaseConfig):
    DEBUG = True
