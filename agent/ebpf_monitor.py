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

    def _handle_event(self, cpu, data, size):
        event = self._b["write_events"].event(data)  # type: ignore
        pid   = event.pid
        now   = time.time()

        fname = event.fname.decode("utf-8", errors="replace").strip("\x00")
        comm  = event.comm.decode("utf-8", errors="replace").strip("\x00")

        dq = self._pid_window[pid]
        dq.append((now, event.bytes, fname, comm))

        # Обрезаем окно
        cutoff = now - WINDOW_SEC
        while dq and dq[0][0] < cutoff:
            dq.popleft()

        # Анализ поведения
        write_count = len(dq)
        total_bytes = sum(e[1] for e in dq)
        bps         = total_bytes / WINDOW_SEC

        suspicious = (
            write_count >= SUSPECT_WRITES or
            bps >= SUSPECT_BYTES_PER_SEC
        )

        if suspicious:
            last = self._last_alert.get(pid, 0)
            if now - last >= COOLDOWN_SEC:
                self._last_alert[pid] = now
                log.warning(
                    f"[eBPF] SUSPECT pid={pid} comm={comm} "
                    f"writes={write_count}/{WINDOW_SEC}s "
                    f"bps={bps/1024:.0f} KB/s file={fname}"
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
