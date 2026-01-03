import csv
import re
import subprocess
import contextlib
import ast
import os
from os import path, getcwd, chdir
from sys import builtin_module_names
from typing import List, Tuple, Generator, Any, Optional
from pathlib import Path
from shutil import rmtree
import pytest
import sys
from time import time
import gzip
import cProfile
import pstats

# ===================================================================
# Classe TestResult
# ===================================================================
class TestResult:
    def __init__(self, trace: bool = False, prof: bool = False, cov: bool = False, 
                 outputDir: str = ".", testName: str = "", 
                 automation_root: Path = None, project_root_dir: str = ""):
        self.testName = testName; self.outputDir = outputDir; self.cov = cov
        self.trace = trace; self.prof = prof; self.automation_root = automation_root
        if not self.automation_root or not self.automation_root.is_dir():
            raise ValueError("O caminho raiz do projeto de automação é inválido ou não foi fornecido.")
        self.project_root_dir = project_root_dir
        if self.trace and not self.project_root_dir:
            raise ValueError("`project_root_dir` deve ser fornecido para habilitar o tracing.")
        self.passed = 0; self.failed = 0; self.xfailed = 0; self.skipped = 0
        self.total_duration = 0.0; self.profiler = cProfile.Profile() if self.prof else None
        self.traceBuffer = []
        self.test_was_run = False
        self.trace_depth = 0

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item, call):
        outcome = yield; report = outcome.get_result()
        if report.when == 'call':
            self.total_duration = report.duration
            self.test_was_run = True

    def pytest_runtest_setup(self, item):
        if self.prof: self.profiler.enable()
        if self.trace: sys.settrace(self.hierarchical_trace)

    def pytest_runtest_teardown(self, item, nextitem):
        if self.prof: self.profiler.disable()
        if self.trace: sys.settrace(None)

    def pytest_sessionfinish(self, session, exitstatus):
        if not self.test_was_run:
            print("AVISO: Nenhum teste foi executado, pulando pós-processamento de análise.")
            return
        if self.prof and self.profiler: self.process_profiling_data()
        if self.trace: self.process_tracing_data()

    def process_profiling_data(self):
        raw_stats_file = Path(self.outputDir) / f"{self.testName}.pstat"
        human_readable_stats_file = Path(self.outputDir) / f"{self.testName}-stats.txt"
        profiling_csv = Path(self.outputDir) / f"{self.testName}-profiling.csv"
        self.profiler.dump_stats(raw_stats_file)
        if os.path.getsize(raw_stats_file) > 0:
            stats = pstats.Stats(str(raw_stats_file))
            with open(human_readable_stats_file, "w") as f:
                stats.stream = f; stats.sort_stats("ncalls").print_stats()
            parse_script = self.automation_root / "parse_profiling.py"
            if parse_script.exists():
                subprocess.run([sys.executable, str(parse_script), "--input_file", str(human_readable_stats_file), "--output_file", str(profiling_csv)], check=True, capture_output=True, text=True)
        os.remove(raw_stats_file)

    def process_tracing_data(self):
        if self.traceBuffer:
            calls_gz_file = Path(self.outputDir) / "calls.gz"
            tracing_csv = Path(self.outputDir) / f"{self.testName}-tracing.csv"
            with gzip.open(calls_gz_file, "wt", encoding='utf-8') as f: f.writelines(self.traceBuffer)
            parse_script = self.automation_root / "parse_tracing.py"
            if parse_script.exists():
                subprocess.run([sys.executable, str(parse_script), "--input_file", str(calls_gz_file), "--output_file", str(tracing_csv)], check=True, capture_output=True, text=True)


    def hierarchical_trace(self, frame, event, arg):
        """
        Função de callback para sys.settrace que cria um log hierárquico e filtrado de forma robusta.
        """
        if event not in ('call', 'return'):
            return self.hierarchical_trace

        code = frame.f_code
        filename = code.co_filename
        
        try:
            project_path = Path(self.project_root_dir).resolve()
            file_path = Path(filename).resolve()
            is_in_project = project_path in file_path.parents or project_path == file_path.parent
            
        except (TypeError, OSError):
            is_in_project = False
        
        if not is_in_project:
            return self.hierarchical_trace

        func_name = code.co_name

        if event == 'call':
            self.trace_depth += 1
            indent = ">" * self.trace_depth
            try:
                relative_path = file_path.relative_to(project_path)
            except ValueError:
                relative_path = os.path.basename(filename) # Fallback

            indent = ">" * self.trace_depth
            self.traceBuffer.append(f"{indent} {func_name} in {relative_path}\n")
            self.trace_depth += 1
        
        elif event == 'return':
            if self.trace_depth > 0:
                self.trace_depth -= 1
            
            indent = "<" * self.trace_depth
            
            try:
                return_value_str = repr(arg)
            except Exception:
                return_value_str = "[Unrepresentable object]"

            if len(return_value_str) > 150:
                return_value_str = return_value_str[:150] + "..."
                
            self.traceBuffer.append(f"{indent} {func_name} returned: {return_value_str}\n")

        return self.hierarchical_trace
    
    def pytest_terminal_summary(self, terminalreporter, exitstatus):
        self.passed = len(terminalreporter.stats.get('passed', []))
        self.failed = len(terminalreporter.stats.get('failed', []))
        self.xfailed = len(terminalreporter.stats.get('xfailed', []))
        self.skipped = len(terminalreporter.stats.get('skipped', []))

# ===================================================================
# Classe VirtualEnvironment
# ===================================================================
class VirtualEnvironment:
    def __init__(self, venv_dir: Path, root_dir: str, requirements: Optional[List[Path]] = None) -> None:
        self._venv_dir = venv_dir.resolve()
        self._requirements = requirements if requirements is not None else []
        self._root_dir = root_dir
        if not self._venv_dir.exists():
            raise FileNotFoundError(f"O diretório do ambiente virtual esperado não existe: {self._venv_dir}")

    @property
    def venv_dir(self) -> Path:
        return self._venv_dir
    
    def executePytest(self, test_node: str, params: List[bool], output_dir: str, origin_dir: str, count: int, test_result_plugin) -> Tuple[str, float, int, int, int, int]:
        current_dir = getcwd()
        chdir(origin_dir)

        include_coverage = params[1]
        project_name = Path(origin_dir).name
        prefix_to_remove = f"{project_name}/"

        if test_node.startswith(prefix_to_remove):
            final_test_node = test_node[len(prefix_to_remove):]
        else:
            final_test_node = test_node
            
        print(f"\nExecutando teste via pytest.main (Run {count})")
        print(f"  - Node Original do CSV: {test_node}")
        print(f"  - Node Corrigido para Pytest: {final_test_node}")
        
        
        pytest_args = ["-p", "no:cacheprovider"]

        json_output_file = None
        if include_coverage:
            sanitized_test_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', final_test_node.split('/')[-1].split("::")[-1])
            test_dir_for_cov = final_test_node.split('/')[0]
            
            run_output_dir = Path(output_dir)
            json_output_file = run_output_dir / f"{sanitized_test_name}-cov.json"
            pytest_args.extend([f"--cov={test_dir_for_cov}", f"--cov-report=json:{json_output_file}"])

        pytest_args.append(final_test_node)
        
        pytest.main(pytest_args, plugins=[test_result_plugin])
            
        passed, failed, skipped, xfailed = (test_result_plugin.passed, test_result_plugin.failed, test_result_plugin.skipped, test_result_plugin.xfailed)
        
        if failed > 0: result = "FAILED"
        elif passed > 0: result = "PASSED"
        elif xfailed > 0: result = "XFAILED"
        elif skipped > 0: result = "SKIPPED"
        else: result = "ERROR" 

        if include_coverage and json_output_file and json_output_file.exists():
            sanitized_test_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', final_test_node.split('/')[-1].split("::")[-1])
            csv_output_file = json_output_file.with_name(f"{sanitized_test_name}-coverage.csv")
            parse_script = test_result_plugin.automation_root / "parse_coverage.py"
            if parse_script.exists():
                try:
                    subprocess.run(
                        [sys.executable, str(parse_script), "--input_file", str(json_output_file), "--output_file", str(csv_output_file), "--result", result],
                        check=True, capture_output=True, text=True
                    )
                except subprocess.CalledProcessError as e:
                    print(f"!!!!!! ERRO ao executar o script de parse de coverage !!!!!!\nErro (stderr):\n{e.stderr}\n")

        chdir(current_dir)
        return (result, test_result_plugin.total_duration, passed, failed, skipped, xfailed)

# ===================================================================
# Classes e Funções Utilitárias
# ===================================================================
class NoRepositoryNameException(Exception):
    def __init__(self, *args: object) -> None: super().__init__(*args)

class Repository:
    def __init__(self, url: str, noruns: str, githash = ".", isgitrepo = False) -> None:
        self._url = url; self._noruns = noruns; self._githash = githash; self._isgitrepo = isgitrepo
        if isgitrepo: self._name = getRepoName(url)
        else: self._name = url
    @property
    def url(self): return self._url
    @property
    def noruns(self): return self._noruns
    @property
    def githash(self): return self._githash
    @property
    def name(self): return self._name

@contextlib.contextmanager
def venv(venv_dir: Path, root_dir: str, requirements: List[Path]) -> Generator[VirtualEnvironment, Any, None]:
    v = VirtualEnvironment(Path(venv_dir), root_dir, requirements);
    try: yield v
    finally: pass

def getRepoName(gitUrl: str) -> str:
    print(f"Extraindo nome da URL: {gitUrl}")
    urlPattern = r'/([^/]+?)(?:\.git)?$'
    match = re.search(urlPattern, gitUrl)
    if match: return match.group(1)
    else: raise NoRepositoryNameException(f"Nenhum nome de repositório encontrado para {gitUrl}")

def cloning(repo: Repository) -> None:
    cwd = getcwd()
    if os.path.exists(repo.name): print(f"Diretório '{repo.name}' já existe. Pulando clone."); return
    subprocess.run(["git", "clone", repo.url, repo.name], check=True, capture_output=True)
    chdir(repo.name)
    subprocess.run(["git", "checkout", repo.githash], check=True, capture_output=True)
    chdir(cwd)

def getRepoRequirements(repo: Repository) -> List[Path]:
    project_path = Path(repo.name)
    if not project_path.is_dir(): return []
    abs_project_path = project_path.resolve()
    return list(abs_project_path.rglob("*requirements*.txt"))

def runSpecificTests(repo: Repository, mod_name: str, params: List[bool], test_node: str, no_runs: int,
                     env_path: Path) -> None:
    cwd = getcwd()
    
    if not path.exists(repo.name):
        print(f"Clonando repositório '{repo.name}'...")
        cloning(repo)

    requirements_files = getRepoRequirements(repo)
    pip_executable = str(env_path.resolve() / "bin" / "pip")
    project_dir = (Path(cwd) / repo.name).resolve()

    print(f"\n>>> Verificando e instalando dependências para '{repo.name}'...")
    
    setup_file_path = project_dir / "setup.py"
    if setup_file_path.exists():
        print(f">>> Instalando o projeto '{repo.name}'...")
        try:
            subprocess.run([pip_executable, "install", "--no-cache-dir", "--no-build-isolation", "."], check=True, cwd=str(project_dir), capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            print(f"!!!!!! ERRO CRÍTICO ao instalar o projeto (setup.py) !!!!!!\nErro (stderr):\n{e.stderr}\n"); raise
        
    if requirements_files:
        print(f">>> Encontrados {len(requirements_files)} arquivos de dependências...")
        for req_file in requirements_files:
            print(f"--- Processando arquivo: {req_file.relative_to(project_dir)}")
            
            protected_packages = {'pytest', 'pytest-cov', 'coverage', 'setuptools', 'wheel'}
            filtered_requirements = []
            try:
                with open(req_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#') or line.startswith('-e'):
                            continue
                        
                        package_name = re.split(r'[=<>!~]', line)[0].strip()
                        
                        if package_name not in protected_packages:
                            filtered_requirements.append(line)
                        else:
                            print(f"      - Ignorando dependência protegida: {line}")
            except Exception as e:
                print(f"Erro ao ler o arquivo de requirements '{req_file.name}': {e}"); raise

            if filtered_requirements:
                temp_req_path = project_dir / "temp_filtered_reqs.txt"
                with open(temp_req_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(filtered_requirements))

                print(f"--- Instalando {len(filtered_requirements)} dependências filtradas...")
                try:
                    subprocess.run(
                        [pip_executable, "install", "--no-cache-dir", "--no-build-isolation", "-r", str(temp_req_path)],
                        check=True, capture_output=True, text=True, cwd=str(project_dir)
                    )
                except subprocess.CalledProcessError as e:
                    print(f"!!!!!! AVISO: Falha ao instalar dependências filtradas de '{req_file.name}' !!!!!!\nErro (stderr):\n{e.stderr}\n"); raise
                finally:
                    os.remove(temp_req_path)
            else:
                print("      - Nenhuma dependência não protegida para instalar.")

    print(">>> Instalação de dependências concluída.")
    
    include_tracing, include_coverage, include_profiling = params
    
    sanitized_test_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', test_node.split("::")[-1])
    
    output_test_dir = (Path(cwd) / f"Test-{mod_name}" / sanitized_test_name).resolve()
    output_test_dir.mkdir(parents=True, exist_ok=True)

    run_summary = []
    test_type = "Tracing" if include_tracing else "Coverage" if include_coverage else "Profiling"
    run_summary.append(f"Teste: {test_type}\n")

    total_time, passed_count, failed_count, skipped_count, xfailed_count = 0.0, 0, 0, 0, 0

    with venv(env_path, cwd, requirements_files) as env:
        for run in range(no_runs):
            run_output_dir = output_test_dir / f"Run-{run}"
            run_output_dir.mkdir(parents=True, exist_ok=True)
            
            automation_project_root = Path(cwd).resolve()
            
            test_result = TestResult(
                trace=include_tracing, prof=include_profiling, cov=include_coverage,
                outputDir=str(run_output_dir), testName=sanitized_test_name,
                automation_root=automation_project_root,
                project_root_dir=str(project_dir)
            )

            results = env.executePytest(
                test_node=test_node,
                params=params,
                output_dir=str(run_output_dir),
                origin_dir=str(project_dir),
                count=run,
                test_result_plugin=test_result
            )
            
            run_verdict, run_duration, run_passed, run_failed, run_skipped, run_xfailed = results
            total_time += run_duration
            passed_count += run_passed
            failed_count += run_failed
            skipped_count += run_skipped
            xfailed_count += run_xfailed
            run_summary.append(f"Run {run}: {run_verdict} Tempo: {run_duration}\n")

    run_summary.append(f"\nTempo total: {total_time:.4f}s\n")
    
    final_verdict = ""
    if skipped_count > 0: final_verdict = "SKIPPED"
    elif xfailed_count > 0: final_verdict = "XFAILED"
    else:
        if passed_count > 0 and failed_count > 0: final_verdict = "FLAKY"
        elif passed_count > 0 and failed_count == 0: final_verdict = "PASSED"
        elif passed_count == 0 and failed_count > 0: final_verdict = "FAILED"
        else: final_verdict = "ERROR"
    run_summary.append(f"Resultado Final: {final_verdict}\n") # Renomeado para "Resultado Final"
    
    summary_file_path = output_test_dir / "runsSummary.txt"
    with open(summary_file_path, "a", encoding='utf-8') as f:
        f.writelines(run_summary)
    
    print(f"\nSumário da execução salvo em: {summary_file_path}")