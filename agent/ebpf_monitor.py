"""
eBPF-мониторинг на уровне ядра Linux.

Kprobe на vfs_write — перехватывает запись в файлы на уровне VFS,
до завершения системного вызова. Выявляет подозрительные процессы
по частоте записи (поведенческий анализ).

Требования: privileged-контейнер, CAP_BPF, монтирование
/sys/kernel/debug, /lib/modules, /usr/src.
"""

import collections
import logging
import threading
import time
from typing import Callable, Optional

log = logging.getLogger("ebpf")

# ─── BPF-программа ────────────────────────────────────────────────────
BPF_PROGRAM = r"""
#include <uapi/linux/ptrace.h>

/*
 * Ядро 7.x: clang из bcc неверно вычисляет layout struct filename
 * (новые аннотации в fs.h), и static_assert(sizeof % 64 == 0) валит
 * компиляцию. Мы struct filename не используем (только file/inode/dentry),
 * поэтому отключаем compile-time проверки перед включением fs.h.
 */
#include <linux/build_bug.h>
#undef static_assert
#define static_assert(expr, ...)

#include <linux/fs.h>
#include <linux/sched.h>
#include <linux/stat.h>

#define FNAME_LEN 128

struct write_event_t {
    u32  pid;
    u32  uid;
    u64  bytes;
    u64  ts_ns;
    char comm[TASK_COMM_LEN];
    char fname[FNAME_LEN];
};

BPF_PERF_OUTPUT(write_events);
BPF_HASH(pid_write_count, u32, u64);
BPF_HASH(pid_bytes_total, u32, u64);

int trace_vfs_write(struct pt_regs *ctx,
                    struct file *file,
                    const char __user *buf,
                    size_t count, loff_t *pos)
{
    u32 pid = bpf_get_current_pid_tgid() >> 32;
    // Пропускаем ядерные потоки
    if (pid < 3) return 0;

    // Только обычные файлы (S_ISREG)
    struct inode *inode = NULL;
    bpf_probe_read_kernel(&inode, sizeof(inode), &file->f_inode);
    if (!inode) return 0;

    umode_t mode = 0;
    bpf_probe_read_kernel(&mode, sizeof(mode), &inode->i_mode);
    if (!S_ISREG(mode)) return 0;

    struct write_event_t ev = {};
    ev.pid   = pid;
    ev.uid   = bpf_get_current_uid_gid() & 0xFFFFFFFF;
    ev.bytes = (u64)count;
    ev.ts_ns = bpf_ktime_get_ns();
    bpf_get_current_comm(&ev.comm, sizeof(ev.comm));

    // Имя файла из dentry (только последний компонент пути)
    struct dentry *dentry = NULL;
    bpf_probe_read_kernel(&dentry, sizeof(dentry), &file->f_path.dentry);
    if (dentry) {
        const unsigned char *name = NULL;
        bpf_probe_read_kernel(&name, sizeof(name), &dentry->d_name.name);
        if (name)
            bpf_probe_read_kernel_str(&ev.fname, sizeof(ev.fname), name);
    }

    // Атомарные счётчики per-PID
    pid_write_count.increment(pid);
    pid_bytes_total.increment(pid, (u64)count);

    write_events.perf_submit(ctx, &ev, sizeof(ev));
    return 0;
}
"""

# ─── Пороги детекции ──────────────────────────────────────────────────
WINDOW_SEC            = 10      # скользящее окно анализа, секунды
SUSPECT_WRITES        = 50      # записей в окне → подозрительно
SUSPECT_BYTES_PER_SEC = 5 * 1024 * 1024  # 5 MB/s → подозрительно
COOLDOWN_SEC          = 30      # не повторять алерт для того же PID раньше

# ─── Whitelist процессов ───────────────────────────────────────────────
# comm в Linux обрезается до 15 символов (TASK_COMM_LEN - 1).
# Легитимные процессы с высокой частотой записи не должны триггерить алерт,
# если они не пишут в файлы с подозрительными расширениями.
_PROC_WHITELIST: frozenset[str] = frozenset({
    # Компиляторы и сборка
    "gcc", "cc", "cc1", "cc1plus", "g++", "c++", "collect2",
    "clang", "clang++", "lld", "ld", "as", "ar", "ranlib", "objcopy",
    "make", "cmake", "ninja", "meson", "bazel", "scons",
    # Интерпретаторы
    "python3", "python3.11", "python3.12", "python", "pip3", "pip",
    "node", "npm", "yarn", "pnpm", "bun", "deno",
    # Системы сборки языков
    "rustc", "cargo", "go", "gofmt", "javac", "kotlinc",
    # Системы контроля версий
    "git", "git-upload-pac", "git-remote-htt", "svn", "hg",
    # Пакетные менеджеры
    "apt", "apt-get", "dpkg", "rpm", "yum", "dnf",
    # Редакторы
    "vim", "vi", "nano", "emacs", "code", "gedit",
    # Утилиты копирования и архивации
    "cp", "mv", "rsync", "tar", "gzip", "bzip2", "xz", "zip",
    # Наш собственный бэкап-агент
    "borg",
    # Системные
    "systemd", "journald", "dockerd", "containerd", "postgres",
    "sqlite3", "mysqld", "mongod",
    # Агент мониторинга (сам себя не должен детектить; python3 уже выше)
    "agent",
})

# Расширения файлов — признак ransomware.
# Пробивают whitelist: даже gcc, пишущий ".locked" — подозрительно.
_SUSPICIOUS_EXTENSIONS: frozenset[str] = frozenset({
    ".locked", ".enc", ".encrypted", ".crypto", ".crypt",
    ".ransom", ".wnry", ".wncry", ".zepto", ".cerber",
    ".crypted", ".cryp1", ".aaa", ".abc", ".xyz",
    ".cryptolocker", ".vault", ".pay2decrypt",
})


class EBPFMonitor:
    """
    Запускает eBPF kprobe на vfs_write. При обнаружении процесса
    с аномальной частотой записи вызывает on_suspect_callback.

    Если eBPF недоступен (нет привилегий / старое ядро) — start()
    возвращает False, агент продолжает работать только на watchdog.
    """

    def __init__(self, on_suspect: Callable):
        self._callback   = on_suspect
        self._b          = None
        self._thread: Optional[threading.Thread] = None
        self._running    = False
        # pid → deque[(timestamp, bytes, fname)]
        self._pid_window: dict = collections.defaultdict(collections.deque)
        # pid → last_alert_time (cooldown)
        self._last_alert: dict = {}
        # Периодическая чистка завершившихся PID, иначе словари растут вечно
        self._last_purge = time.time()

    # ──────────────────────────────────────────────────────────────────

    def start(self) -> bool:
        """Загрузить BPF-программу и запустить поток опроса буфера."""
        try:
            from bcc import BPF  # type: ignore
            self._b = BPF(text=BPF_PROGRAM)
            self._b.attach_kprobe(event="vfs_write", fn_name="trace_vfs_write")
            self._b["write_events"].open_perf_buffer(
                self._handle_event, page_cnt=256
            )
            self._running = True
            self._thread = threading.Thread(
                target=self._poll_loop, daemon=True, name="ebpf-poll"
            )
            self._thread.start()
            log.info("eBPF: kprobe/vfs_write attached — kernel-level monitoring active")
            return True
        except Exception as exc:
            log.warning(f"eBPF unavailable ({exc}), watchdog-only mode")
            return False

    def stop(self):
        self._running = False
        if self._b:
            try:
                self._b.cleanup()
            except Exception:
                pass

    def get_pid_stats(self) -> list[dict]:
        """Сводка накопленных счётчиков из BPF-хешей (для логов/дашборда)."""
        if not self._b:
            return []
        stats = []
        try:
            wc = self._b["pid_write_count"]
            bc = self._b["pid_bytes_total"]
            for k, v in wc.items():
                stats.append({
                    "pid":          k.value,
                    "write_count":  v.value,
                    "bytes_total":  bc[k].value if k in bc else 0,
                })
        except Exception:
            pass
        return stats

    # ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _is_suspicious_ext(fname: str) -> bool:
        """True если расширение файла типично для ransomware-шифровальщика."""
        dot = fname.rfind(".")
        if dot == -1:
            return False
        return fname[dot:].lower() in _SUSPICIOUS_EXTENSIONS

    @staticmethod
    def _is_whitelisted(comm: str, fname: str) -> bool:
        """
        True если процесс легитимен И файл не имеет подозрительного расширения.
        Whitelist пробивается ransomware-расширениями — даже gcc не должен
        писать .locked файлы.
        """
        if EBPFMonitor._is_suspicious_ext(fname):
            return False
        return comm in _PROC_WHITELIST

    PURGE_INTERVAL_SEC = 60

    def _purge_stale(self, now: float):
        """Удаляет окна и cooldown-метки PID, неактивных дольше окна анализа."""
        cutoff = now - WINDOW_SEC
        stale = [
            pid for pid, dq in self._pid_window.items()
            if not dq or dq[-1][0] < cutoff
        ]
        for pid in stale:
            self._pid_window.pop(pid, None)

        alert_cutoff = now - COOLDOWN_SEC * 2
        self._last_alert = {
            pid: ts for pid, ts in self._last_alert.items() if ts >= alert_cutoff
        }
        self._last_purge = now

    def _handle_event(self, cpu, data, size):
        event = self._b["write_events"].event(data)  # type: ignore
        pid   = event.pid
        now   = time.time()

        if now - self._last_purge >= self.PURGE_INTERVAL_SEC:
            self._purge_stale(now)

        fname = event.fname.decode("utf-8", errors="replace").strip("\x00")
        comm  = event.comm.decode("utf-8", errors="replace").strip("\x00")

        # Легитимный процесс без подозрительного расширения → пропускаем
        if self._is_whitelisted(comm, fname):
            return

        dq = self._pid_window[pid]
        dq.append((now, event.bytes, fname, comm))

        # Обрезаем скользящее окно
        cutoff = now - WINDOW_SEC
        while dq and dq[0][0] < cutoff:
            dq.popleft()

        # Анализ поведения
        write_count = len(dq)
        total_bytes = sum(e[1] for e in dq)
        bps         = total_bytes / WINDOW_SEC

        # Подозрительно: высокая частота записи ИЛИ ransomware-расширение
        suspicious = (
            write_count >= SUSPECT_WRITES
            or bps >= SUSPECT_BYTES_PER_SEC
            or self._is_suspicious_ext(fname)
        )

        if suspicious:
            last = self._last_alert.get(pid, 0)
            if now - last >= COOLDOWN_SEC:
                self._last_alert[pid] = now
                reason = (
                    "suspicious_ext" if self._is_suspicious_ext(fname)
                    else f"writes={write_count} bps={bps/1024:.0f}KB/s"
                )
                log.warning(
                    f"[eBPF] SUSPECT pid={pid} comm={comm} "
                    f"reason={reason} file={fname}"
                )
                self._callback(
                    pid=pid,
                    comm=comm,
                    writes=write_count,
                    bytes_per_sec=bps,
                    sample_file=fname,
                )

    def _poll_loop(self):
        while self._running:
            try:
                self._b.perf_buffer_poll(timeout=100)  # type: ignore
            except Exception as exc:
                log.error(f"eBPF poll error: {exc}")
                self._running = False
                break
