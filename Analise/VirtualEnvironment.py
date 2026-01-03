from typing import List, Tuple, Optional
from pathlib import Path
from os import getcwd, chdir
from . import analise
import subprocess
import pytest
import shutil
import os
import sys
import pstats
import io

class VirtualEnvironment:
    """ 
    Motor de Ambiente Virtual: Vacinas + Suporte Total (Trace/Cov/Prof) + Parsers Automáticos
    Adaptado para o Mestrado.
    """
    
    # Dicionário de Correções (Vacinas de Instalação)
    CUSTOM_INSTALLS = {
        "airflow": ["pip install wheel", "pip install -e .[devel] --constraint constraints-3.8.txt", "pip install pytest-mock"],
        "sunpy": ["pip install 'numpy<1.24'", "pip install 'parfive[ftp]'", "pip install -e .[all]"],
        "scikit-image": ["pip install 'numpy<1.22'", "pip install 'scipy<1.8'", "pip install cython", "pip install -e ."],
        "xonsh": ["pip install -e ."],
        "fonttools": ["pip install -e ."],
        "hydra": ["pip install -e ."],
        "graphene": ["pip install -e ."],
        "celery": ["pip install -e ."]
    }

    def __init__(self, venv_dir: str, root_dir: str, requirements: Optional[List[Path]] = ["requirements.txt"]) -> None:
        self._venv_dir = f"{root_dir}/{venv_dir}"
        self._requirements = requirements
        self._root_dir = root_dir
        self._repo_name = os.path.basename(root_dir)

        print(f"Criando Venv em: {self._venv_dir}")
        create_venv_cmd = ["virtualenv", "--clear", self._venv_dir]
        subprocess.run(create_venv_cmd, check=True)

    @property
    def venv_name(self): return self._venv_dir.split("/")[-1]
    
    @property
    def requirements(self): return self._requirements
    
    @property
    def venv_dir(self): return self._venv_dir
    
    def cleanUp(self):
        if os.path.exists(self._venv_dir):
            shutil.rmtree(self._venv_dir)

    def runCommands(self, commands: Optional[List[str]] = None) -> Tuple[str, str]:
        activate_cmd = f"source '{self._venv_dir}/bin/activate'"
        full_command_script = [activate_cmd, "pip install --upgrade pip setuptools wheel"]

        # INSTALA DEPENDÊNCIAS DE ANÁLISE (Coverage precisa do pytest-cov)
        full_command_script.append("pip install pytest pytest-cov")

        # --- APLICAÇÃO DAS VACINAS ---
        receita_especial = None
        for key in self.CUSTOM_INSTALLS:
            if key.lower() in self._repo_name.lower():
                receita_especial = self.CUSTOM_INSTALLS[key]
                break
        
        if receita_especial:
            print(f"[VACINA] Aplicando instalação customizada para: {self._repo_name}")
            full_command_script.extend(receita_especial)
        else:
            print(f"[PADRÃO] Tentando instalação genérica para: {self._repo_name}")
            for req in self._requirements:
                if os.path.exists(f"{self._root_dir}/{req}"):
                    full_command_script.append(f"pip install -r {req}")
            full_command_script.append("pip install -e .")

        if commands:
            full_command_script.extend(commands)

        final_cmd = " && ".join(full_command_script)
        process = subprocess.run(final_cmd, shell=True, executable="/bin/bash", cwd=self._root_dir, capture_output=True, text=True)
        return process.stdout, process.stderr

    def executePytest(self, test_node: str, params: List[bool], output_dir: str, origin_dir: str, count: int = 0, test_result_plugin = None) -> Tuple[str, float, int, int, int, int]:
        cwd = getcwd()
        chdir(origin_dir)

        # params = [tracing, coverage, profiling]
        include_tracing = params[0]
        include_coverage = params[1]
        include_profiling = params[2]

        # Instancia o Plugin Híbrido
        test_result = analise.TestResult(
            trace=include_tracing,
            prof=include_profiling,
            cov=include_coverage,
            outputDir=output_dir,
            testName=test_node.split("/")[-1]
        )

        pytest_args = [
            "-p", "no:cacheprovider",
            "--ignore=docs",
            "-W", "ignore",
            test_node
        ]

        # Configuração do Coverage
        json_cov_path = f"{output_dir}/coverage.json"
        if include_coverage:
            pytest_args.extend([
                f"--cov=.", 
                f"--cov-report=json:{json_cov_path}"
            ])

        # --- EXECUÇÃO DO TESTE ---
        pytest.main(pytest_args, plugins=[test_result])
        
        # --- PÓS-PROCESSAMENTO (PARSERS) ---
        
        # 1. Coverage Parser
        script_cov = os.path.join(self._root_dir, "parse_coverage.py")
        if include_coverage and os.path.exists(script_cov) and os.path.exists(json_cov_path):
             csv_cov_path = f"{output_dir}/coverage.csv"
             subprocess.run([
                 "python3", script_cov,
                 "--input_file", json_cov_path,
                 "--output_file", csv_cov_path,
                 "--result", "PASSED" if test_result.passed > 0 else "FAILED"
             ])

        # 2. Profiling Parser
        # O parse_profiling.py espera texto, mas temos binário (.prof). Convertemos primeiro.
        script_prof = os.path.join(self._root_dir, "parse_profiling.py")
        if include_profiling and os.path.exists(script_prof):
            prof_files = [f for f in os.listdir(output_dir) if f.endswith(".prof")]
            for p_file in prof_files:
                bin_path = os.path.join(output_dir, p_file)
                txt_path = bin_path.replace(".prof", "_stats.txt")
                csv_path = bin_path.replace(".prof", ".csv")
                
                try:
                    # Converte Binário .prof -> Texto Formatado
                    with open(txt_path, 'w') as f_txt:
                        stats = pstats.Stats(bin_path, stream=f_txt)
                        stats.sort_stats('cumulative')
                        stats.print_stats()
                    
                    # Chama o script do usuário para converter Texto -> CSV
                    subprocess.run([
                        "python3", script_prof,
                        "--input_file", txt_path,
                        "--output_file", csv_path
                    ])
                except Exception as e:
                    print(f"Erro processando profiling: {e}")

        # 3. Tracing Parser
        script_trace = os.path.join(self._root_dir, "parse_tracing.py")
        if include_tracing and os.path.exists(script_trace):
            trace_files = [f for f in os.listdir(output_dir) if f.endswith(".trace.gz")]
            for t_file in trace_files:
                gz_path = os.path.join(output_dir, t_file)
                csv_path = gz_path.replace(".trace.gz", ".csv")
                
                subprocess.run([
                    "python3", script_trace,
                    "--input_file", gz_path,
                    "--output_file", csv_path
                ])

        passed = test_result.passed
        failed = test_result.failed
        skipped = test_result.skipped
        xfailed = test_result.xfailed
        total_time = test_result.total_duration

        if passed > 0: result = "PASSED"
        elif failed > 0: result = "FAILED"
        elif skipped > 0: result = "SKIPPED"
        else: result = "XFAILED"

        chdir(cwd)
        return (result, total_time, passed, failed, skipped, xfailed)
