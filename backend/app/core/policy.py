"""
Доменная логика реагирования на инциденты.

Чистая функция без зависимостей от FastAPI/БД — слой domain
в терминах Clean Architecture. Используется эндпоинтом
/incidents/report и напрямую тестируется в tests/test_incident.py.
"""

# Пороги эскалации
LOCKDOWN_ALERT_COUNT = 10   # алертов в окне → блокировка директории
LOCKDOWN_ENTROPY     = 7.9  # энтропия уровня шифрования → блокировка
BACKUP_ALERT_COUNT   = 3    # алертов в окне → внеплановый бэкап


def determine_action(
    alert_count: int, entropy: float, suspicious_ext: bool = False
) -> tuple[str, str]:
    """
    Выбор действия по числу алертов, энтропии и признаку ransomware-расширения.

    suspicious_ext=True — eBPF зафиксировал запись в файл с расширением
    шифровальщика (.locked, .enc, ...). Это качественная улика уровня ядра:
    даже одиночное событие требует немедленного спасения данных.

    Возвращает (action, message):
      lockdown          — массовая атака или явное шифрование
      emergency_backup  — подозрительная активность, спасаем данные
      logged            — одиночное событие, только фиксация
    """
    if alert_count >= LOCKDOWN_ALERT_COUNT or entropy >= LOCKDOWN_ENTROPY:
        return "lockdown", "CRITICAL: lockdown initiated, emergency backup triggered"
    if alert_count >= BACKUP_ALERT_COUNT or suspicious_ext:
        return "emergency_backup", "WARNING: emergency backup triggered"
    return "logged", "INFO: incident logged"
