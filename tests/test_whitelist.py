"""
Тесты механизма защиты от ложных срабатываний eBPF-монитора.

Логика двухуровневая:
  1. Whitelist процессов — легитимные инструменты с высокой I/O (gcc, git, borg...)
  2. Suspicious extensions — .locked, .enc, .wncry, ... — пробивают whitelist.

Это отвечает на вопрос профессора об overhead и ложных срабатываниях.
"""

import pytest

from ebpf_monitor import EBPFMonitor, _PROC_WHITELIST, _SUSPICIOUS_EXTENSIONS


class TestSuspiciousExtensions:
    @pytest.mark.parametrize("fname", [
        "document.locked",
        "photo.encrypted",
        "data.enc",
        "archive.wncry",
        "file.cerber",
        "backup.ransom",
        "readme.crypted",
        "storage.vault",
    ])
    def test_ransomware_extensions_detected(self, fname):
        assert EBPFMonitor._is_suspicious_ext(fname), (
            f"{fname!r} должен определяться как подозрительный"
        )

    @pytest.mark.parametrize("fname", [
        "main.c",
        "agent.py",
        "Makefile",
        "README.md",
        "archive.tar.gz",
        "database.sqlite",
        "config.json",
    ])
    def test_normal_extensions_not_flagged(self, fname):
        assert not EBPFMonitor._is_suspicious_ext(fname), (
            f"{fname!r} не должен определяться как подозрительный"
        )

    def test_no_extension_is_safe(self):
        assert not EBPFMonitor._is_suspicious_ext("Makefile")
        assert not EBPFMonitor._is_suspicious_ext("LICENSE")

    def test_detection_is_case_insensitive(self):
        assert EBPFMonitor._is_suspicious_ext("FILE.LOCKED")
        assert EBPFMonitor._is_suspicious_ext("DATA.ENC")
        assert EBPFMonitor._is_suspicious_ext("document.Encrypted")


class TestProcessWhitelist:
    @pytest.mark.parametrize("comm", [
        "gcc", "g++", "clang", "make", "cmake", "ninja",
        "python3", "node", "cargo", "rustc", "go",
        "git", "borg", "rsync", "tar",
        "systemd", "dockerd", "postgres",
    ])
    def test_build_tools_whitelisted_with_normal_files(self, comm):
        assert EBPFMonitor._is_whitelisted(comm, "output.o"), (
            f"Процесс {comm!r} должен быть в whitelist"
        )

    @pytest.mark.parametrize("comm", [
        "gcc", "make", "git", "borg", "python3",
    ])
    def test_whitelist_broken_by_suspicious_extension(self, comm):
        # Даже gcc не должен писать .locked файлы — это признак ransomware
        assert not EBPFMonitor._is_whitelisted(comm, "file.locked"), (
            f"{comm!r} с расширением .locked не должен быть в whitelist"
        )

    def test_unknown_process_not_whitelisted(self):
        assert not EBPFMonitor._is_whitelisted("cryptolocker", "data.db")
        assert not EBPFMonitor._is_whitelisted("malware", "document.txt")

    def test_whitelist_is_frozenset(self):
        # Защита от случайного изменения whitelist во время работы
        assert isinstance(_PROC_WHITELIST, frozenset)
        assert isinstance(_SUSPICIOUS_EXTENSIONS, frozenset)

    def test_whitelist_contains_borg(self):
        # Borg — наш backup агент, критично не ложно срабатывать во время резервирования
        assert "borg" in _PROC_WHITELIST

    def test_whitelist_does_not_contain_common_malware_names(self):
        for name in ("cryptolocker", "wannacry", "petya", "locky"):
            assert name not in _PROC_WHITELIST
