"""
Plugin "All-in-One": Tracing + Profiling + Coverage + Hash de Segurança
"""
from typing import List, Tuple, Optional, Any
from pathlib import Path
import pytest
import cProfile
import sys
import os
import hashlib
import time
import gzip
import inspect

class TestResult:
    def __init__(self, trace: bool = False, prof: bool = False, cov: bool = False, 
                 outputDir: str = ".", testName: str = "",
                 automation_root: Path = None, project_root_dir: str = ""):
        
        self.outputDir = outputDir
        self.prof = prof
        self.trace = trace
        self.cov = cov
        self.testName = testName
        
        # Buffer para Tracing
        self.traceBuffer = []
        self.trace_depth = 0
        
        # Contadores
        self.passed = 0
        self.failed = 0
        self.xfailed = 0
        self.skipped = 0
        self.total_duration = 0.0
        
        self.profiler = None
        self.start_time = 0

    def trace_calls(self, frame, event, arg):
        """ Callback para sys.settrace """
        if event != 'call' and event != 'return':
            return self.trace_calls

        co = frame.f_code
        func_name = co.co_name
        filename = co.co_filename
        
        # Filtra ruído interno
        if "site-packages" in filename or "<string>" in filename:
            return self.trace_calls

        indent = "  " * self.trace_depth
        
        if event == 'call':
            self.traceBuffer.append(f"{indent}> {func_name} in {filename}\n")
            self.trace_depth += 1
        elif event == 'return':
            self.trace_depth = max(0, self.trace_depth - 1)
            self.traceBuffer.append(f"{indent}< {func_name} returned\n")
            
        return self.trace_calls

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_protocol(self, item, nextitem):
        # --- INÍCIO ---
        if self.prof:
            self.profiler = cProfile.Profile()
            self.profiler.enable()
            
        if self.trace:
            self.traceBuffer = []
            sys.settrace(self.trace_calls)
        
        self.start_time = time.time()
        
        yield # Executa o teste
        
        # --- FIM ---
        duration = time.time() - self.start_time
        self.total_duration += duration
        
        if self.trace:
            sys.settrace(None)
            self._save_tracing(item)

        if self.prof and self.profiler:
            self.profiler.disable()
            self._save_profile(item)

    def _get_safe_filename(self, item, suffix):
        if not os.path.exists(self.outputDir):
            os.makedirs(self.outputDir, exist_ok=True)
            
        safe_name = item.nodeid.replace("/", "_").replace("::", "_").replace(".py", "")
        if len(safe_name) > 140:
            hash_digest = hashlib.md5(safe_name.encode('utf-8')).hexdigest()[:10]
            safe_name = safe_name[:100] + "_HASH_" + hash_digest
        return os.path.join(self.outputDir, f"{safe_name}.{suffix}")

    def _save_profile(self, item):
        filename = self._get_safe_filename(item, "prof")
        try:
            self.profiler.dump_stats(filename)
        except Exception as e:
            print(f"Erro salvando profile: {e}")

    def _save_tracing(self, item):
        filename = self._get_safe_filename(item, "trace.gz")
        try:
            with gzip.open(filename, "wt", encoding="utf-8") as f:
                f.writelines(self.traceBuffer)
        except Exception as e:
            print(f"Erro salvando tracing: {e}")

    def pytest_runtest_logreport(self, report):
        if report.when == 'call':
            if report.passed: self.passed += 1
            elif report.failed: self.failed += 1
            elif report.skipped: self.skipped += 1
