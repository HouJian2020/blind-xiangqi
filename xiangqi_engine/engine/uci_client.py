"""UCI 协议客户端

封装 UCI (Universal Chess Interface) 协议通信。
"""

import subprocess
import queue
import threading
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class UCIClient:
    """UCI 协议客户端"""

    def __init__(self, engine_path: str):
        """
        初始化 UCI 客户端

        Args:
            engine_path: 引擎可执行文件路径
        """
        self.engine_path = engine_path
        self.process: Optional[subprocess.Popen] = None
        self.input_queue: queue.Queue = queue.Queue()
        self.output_queue: queue.Queue = queue.Queue()
        self._reader_thread: Optional[threading.Thread] = None
        self._running = False

    def start(self) -> None:
        """启动引擎进程"""
        if self._running:
            return

        self.process = subprocess.Popen(
            [self.engine_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        self._running = True
        self._reader_thread = threading.Thread(
            target=self._reader_loop, daemon=True
        )
        self._reader_thread.start()

        # 初始化 UCI 协议
        self.send_command("uci")
        self.wait_for_response("uciok", timeout=10)

        logger.info(f"Engine started: {self.engine_path}")

    def stop(self) -> None:
        """停止引擎进程"""
        if not self._running:
            return

        self.send_command("quit")
        time.sleep(0.1)

        self._running = False
        if self.process:
            self.process.terminate()
            self.process.wait(timeout=5)
            self.process = None

        if self._reader_thread:
            self._reader_thread.join(timeout=2)
            self._reader_thread = None

        logger.info("Engine stopped")

    def send_command(self, command: str) -> None:
        """发送命令到引擎"""
        if not self.process or not self.process.stdin:
            raise RuntimeError("Engine not running")

        logger.debug(f"Sending: {command}")
        self.process.stdin.write(command + "\n")
        self.process.stdin.flush()

    def read_line(self, timeout: float = 0.1) -> Optional[str]:
        """从输出队列读取一行"""
        try:
            return self.output_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def wait_for_response(
        self, expected: str, timeout: float = 5.0
    ) -> list[str]:
        """等待特定响应"""
        lines = []
        start_time = time.time()

        while time.time() - start_time < timeout:
            line = self.read_line(timeout=0.1)
            if line:
                lines.append(line)
                if expected in line:
                    return lines

        raise TimeoutError(f"Timeout waiting for '{expected}'")

    def _reader_loop(self) -> None:
        """读取引擎输出的线程循环"""
        while self._running and self.process and self.process.stdout:
            try:
                line = self.process.stdout.readline()
                if line:
                    line = line.rstrip("\n")
                    logger.debug(f"Received: {line}")
                    self.output_queue.put(line)
            except Exception as e:
                logger.error(f"Reader error: {e}")
                break

    def is_running(self) -> bool:
        """检查引擎是否运行"""
        return self._running and self.process is not None

    def set_option(self, name: str, value: str | int) -> None:
        """设置引擎选项"""
        self.send_command(f"setoption name {name} value {value}")

    def is_ready(self) -> bool:
        """检查引擎是否就绪"""
        self.send_command("isready")
        try:
            self.wait_for_response("readyok", timeout=5)
            return True
        except TimeoutError:
            return False