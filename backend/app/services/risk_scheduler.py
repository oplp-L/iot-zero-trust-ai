import threading
import time
import traceback
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..models import Device

# 使用我们在 risk_engine.py 中新增的统一入口（若你没有添加 evaluate_device_risk 包装，
# 可以改为: from .risk_engine import compute_risk_for_device as evaluate_device_risk）
from .risk_engine import evaluate_device_risk


class SchedulerState:
    """
    保存调度器运行时状态信息，便于通过 /risk/scheduler/status 查询。
    """

    def __init__(self):
        self.thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.interval_seconds: int = 60
        self.running: bool = False
        self.last_run_start: Optional[float] = None
        self.last_run_end: Optional[float] = None
        self.last_run_duration: Optional[float] = None
        self.last_run_error: Optional[str] = None
        self.total_runs: int = 0


scheduler_state = SchedulerState()


def start_scheduler(interval_seconds: int = 60) -> bool:
    """
    启动调度器线程。若已在运行返回 False。
    """
    st = scheduler_state
    if st.running:
        return False
    st.interval_seconds = interval_seconds
    st.stop_event.clear()
    t = threading.Thread(target=_runner, name="RiskSchedulerThread", daemon=True)
    st.thread = t
    st.running = True
    t.start()
    return True


def stop_scheduler() -> bool:
    """
    停止调度器线程。若未运行返回 False。
    """
    st = scheduler_state
    if not st.running:
        return False
    st.stop_event.set()
    if st.thread and st.thread.is_alive():
        st.thread.join(timeout=5)
    st.running = False
    return True


def update_interval(interval_seconds: int) -> None:
    """
    动态更新调度间隔（秒）。
    """
    if interval_seconds < 10:
        raise ValueError("interval_seconds 不能少于 10 秒（避免过度频繁）")
    scheduler_state.interval_seconds = interval_seconds


def get_status() -> Dict[str, Any]:
    """
    返回当前调度器状态。
    """
    st = scheduler_state
    return {
        "running": st.running,
        "interval_seconds": st.interval_seconds,
        "last_run_start": st.last_run_start,
        "last_run_end": st.last_run_end,
        "last_run_duration": st.last_run_duration,
        "last_run_error": st.last_run_error,
        "total_runs": st.total_runs,
    }


def _runner():
    """
    后台线程主循环：按设定间隔调用 _evaluate_all_devices。
    """
    st = scheduler_state
    while not st.stop_event.is_set():
        start_ts = time.time()
        st.last_run_start = start_ts
        try:
            _evaluate_all_devices()
            st.last_run_error = None
        except Exception as e:
            st.last_run_error = f"{e.__class__.__name__}: {e}"
            traceback.print_exc()
        end_ts = time.time()
        st.last_run_end = end_ts
        st.last_run_duration = round(end_ts - start_ts, 4)
        st.total_runs += 1

        # 可中断的等待
        for _ in range(st.interval_seconds):
            if st.stop_event.is_set():
                break
            time.sleep(1)

    st.running = False


def _evaluate_all_devices():
    """
    遍历所有设备并执行一次风险评估。

    使用 evaluate_device_risk(db, 设备ID, window_minutes=5) 调用。
    说明：
    - evaluate_device_risk 内部（compute_risk_for_device）已经负责写 RiskScore / DeviceLog / 自动隔离/恢复 / commit。
    - 如后续想改为批量提交，可以在 risk_engine 中去掉内部 commit，改成这里统一提交。
    """
    db: Session = SessionLocal()
    t0 = time.time()
    try:
        devices: List[Device] = db.query(Device).all()
        print(f"[Scheduler] Start batch evaluate: devices={len(devices)}")

        errors = 0
        for idx, d in enumerate(devices, 1):
            try:
                rs = evaluate_device_risk(db, d.id, window_minutes=5)
                # rs 为 RiskScore ORM 实例
                print(
                    f"[Scheduler] ({idx}/{len(devices)}) "
                    f"device_id={d.id} score={rs.score} level={rs.level}"
                )
            except Exception as e:
                errors += 1
                # compute_risk_for_device 内部 commit 失败时这里回滚确保事务干净
                db.rollback()
                print(f"[Scheduler] ERROR device_id={d.id}: {e}")

        # 如果后面你改成自己批量处理并取消内部 commit，可在这里统一 db.commit()
        print(f"[Scheduler] Batch done errors={errors} " f"duration={round(time.time() - t0, 3)}s")
    finally:
        db.close()
