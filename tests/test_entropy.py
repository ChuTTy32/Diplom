"""
Тесты алгоритма энтропии Шеннона — центрального детектора ransomware.

H = -Σ p_i · log₂(p_i)

Нормальный текст:       H ≈ 3–5 бит
Сжатые/зашифрованные:  H ≈ 7.5–8.0 бит
Порог алерта:          H ≥ 7.2 бит
"""

import os
import math
import tempfile

import pytest

from agent import shannon_entropy, file_entropy, ENTROPY_THRESHOLD


class TestShannonEntropy:
    def test_empty_bytes_returns_zero(self):
        assert shannon_entropy(b"") == 0.0

    def test_single_unique_byte_returns_zero(self):
        # Единственный символ → p=1.0 → -1·log2(1) = 0
        assert shannon_entropy(b"\x00" * 1000) == 0.0

    def test_two_equal_probability_bytes(self):
        # p=0.5, p=0.5 → H = 1.0 бит
        result = shannon_entropy(b"\x00\xff")
        assert result == pytest.approx(1.0, abs=1e-6)

    def test_uniform_256_bytes_equals_eight(self):
        # Все 256 значений по одному разу → H = log₂(256) = 8.0 бит
        data = bytes(range(256))
        result = shannon_entropy(data)
        assert result == pytest.approx(8.0, abs=0.01)

    def test_english_text_low_entropy(self):
        text = b"The quick brown fox jumps over the lazy dog. " * 50
        h = shannon_entropy(text)
        assert h < ENTROPY_THRESHOLD, (
            f"Обычный текст (H={h:.4f}) не должен превышать порог {ENTROPY_THRESHOLD}"
        )

    def test_random_bytes_high_entropy(self):
        # os.urandom() — криптографически случайные байты, близко к 8.0
        data = os.urandom(4096)
        h = shannon_entropy(data)
        assert h >= 7.0, (
            f"Случайные байты (H={h:.4f}) должны быть выше 7.0 бит"
        )

    def test_threshold_triggers_at_correct_level(self):
        # Порог должен быть 7.2 — стандартный для encrypted/ransomware контента
        assert ENTROPY_THRESHOLD == pytest.approx(7.2, abs=1e-6)

    def test_encrypted_content_above_threshold(self):
        # Имитация зашифрованного блока: все 256 значений равновероятны
        import random
        random.seed(42)
        data = bytes([random.randint(0, 255) for _ in range(8192)])
        h = shannon_entropy(data)
        assert h >= ENTROPY_THRESHOLD, (
            f"Зашифрованное содержимое (H={h:.4f}) должно быть выше порога {ENTROPY_THRESHOLD}"
        )

    def test_repeated_pattern_low_entropy(self):
        # Паттерн из 4 символов: H ≤ log₂(4) = 2.0
        data = b"\x01\x02\x03\x04" * 1000
        h = shannon_entropy(data)
        assert h <= 2.1


class TestFileEntropy:
    def test_plaintext_file_low_entropy(self, tmp_path):
        f = tmp_path / "readme.txt"
        f.write_bytes(b"Hello world. This is a normal file with predictable content.\n" * 100)
        h = file_entropy(str(f))
        assert 0.0 < h < ENTROPY_THRESHOLD

    def test_missing_file_returns_zero(self):
        h = file_entropy("/nonexistent/path/file.bin")
        assert h == 0.0

    def test_binary_file_high_entropy(self, tmp_path):
        f = tmp_path / "encrypted.bin"
        f.write_bytes(os.urandom(32768))
        h = file_entropy(str(f))
        assert h >= 7.0

    def test_max_bytes_limit(self, tmp_path):
        # Файл 1 МБ — должен читать только первые 65536 байт
        f = tmp_path / "large.bin"
        f.write_bytes(os.urandom(1024 * 1024))
        h = file_entropy(str(f), max_bytes=65536)
        assert h > 0.0
