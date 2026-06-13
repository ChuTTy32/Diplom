"""
Аутентификация машина-машина по bearer-токену.

Защищает мутирующие эндпоинты (приём метрик, регистрация инцидента, сброс
lockdown) от вызова произвольным узлом сети. Реализует требование Zero Trust:
запись и управляющие действия — только с действительным токеном.
"""

from fastapi import Header, HTTPException, status

from app.core.config import settings


def require_token(authorization: str = Header(default="")):
    """
    Проверяет заголовок `Authorization: Bearer <RG_TOKEN>`.
    Если RG_TOKEN не задан в конфигурации — проверка отключена (демо-режим
    без секретов), чтобы не ломать локальный запуск без setup.sh.
    """
    token = settings.rg_token
    if not token:
        return
    if authorization != f"Bearer {token}":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing bearer token",
        )
