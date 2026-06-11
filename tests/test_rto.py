"""
Тесты расчёта RTO (Recovery Time Objective) — оценки времени восстановления.

Формула:
  RTO = compressed_size / (restore_speed_MB_s × 1024²) + overhead_30s

Если размер неизвестен — fallback: RTO ≈ время создания бэкапа.
"""

import pytest

from backup import estimate_rto, RESTORE_SPEED_MB_PER_SEC, BORG_OVERHEAD_SEC


class TestEstimateRTO:
    def test_zero_bytes_zero_duration_returns_one_minute(self):
        # Нижняя граница — всегда хотя бы 1 минута
        assert estimate_rto(0, 0) == 1

    def test_zero_bytes_uses_duration_fallback(self):
        # 120 секунд → max(1, 120//60 + 1) = 3
        assert estimate_rto(0, 120) == 3

    def test_fallback_long_backup(self):
        # 10 минут бэкапа → max(1, 600//60 + 1) = 11
        assert estimate_rto(0, 600) == 11

    def test_fallback_short_backup(self):
        # 45 секунд → max(1, 45//60 + 1) = max(1, 0+1) = 1
        assert estimate_rto(0, 45) == 1

    def test_100mb_archive_takes_one_minute(self):
        # 100 МБ / 100 МБ/с = 1.0с + 30с overhead = 31с → 1 мин
        size = 100 * 1024 * 1024
        assert estimate_rto(size, 10) == 1

    def test_10gb_archive_rto_minutes(self):
        # 10 ГБ / 100 МБ/с = 102.4с + 30 = 132.4с → 2 мин
        size = 10 * 1024 * 1024 * 1024
        rto = estimate_rto(size, 300)
        assert rto == 2

    def test_60gb_archive_rto_minutes(self):
        # 60 ГБ / 100 МБ/с = 614.4с + 30 = 644.4с → 10 мин
        size = 60 * 1024 * 1024 * 1024
        rto = estimate_rto(size, 300)
        assert rto == 10

    def test_rto_minimum_is_one_minute(self):
        # Даже для 1 байта — не меньше 1 минуты
        assert estimate_rto(1, 0) >= 1
        assert estimate_rto(1024, 0) >= 1

    def test_restore_speed_constant_is_positive(self):
        assert RESTORE_SPEED_MB_PER_SEC > 0

    def test_overhead_constant_is_positive(self):
        assert BORG_OVERHEAD_SEC > 0

    def test_rto_grows_with_archive_size(self):
        # Монотонность: больше архив → больше RTO
        small = estimate_rto(100 * 1024 * 1024, 10)
        large = estimate_rto(100 * 1024 * 1024 * 1024, 10)
        assert large > small

    def test_rto_formula_manual(self):
        # Ручная верификация формулы
        size_bytes = 5 * 1024 * 1024 * 1024  # 5 ГБ
        speed_bps = RESTORE_SPEED_MB_PER_SEC * 1024 * 1024
        expected_sec = (size_bytes / speed_bps) + BORG_OVERHEAD_SEC
        expected_min = max(1, int(expected_sec / 60))
        assert estimate_rto(size_bytes, 0) == expected_min
