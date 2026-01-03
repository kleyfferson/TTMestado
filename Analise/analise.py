# TODO: - investigar por que a ferramenta roda todos os testes novamente após rodar um repositório
from os import chdir, listdir, getcwd, path
from pathlib import Path
from ast import parse, walk, FunctionDef, ClassDef
from typing import List, Tuple, Dict, Optional, Any
from .TestResult import TestResult
import subprocess
import pytest
import re       

def runMultipleTimes(modDir: str, modName: str, count: int, params: List[bool]):
    """ (deprecated) Executa um teste multiplas vezes, verificando por classe, plugin e parametrização.
    É complexo computacionalmente, preferível executar executePytest de Analise/VirtualEnvironment.py, que só
    utiliza do test node para rodar o pytest.
    :params:
    :modDir: Caminho absoluto ou relativo para o diretório do repositório
    :modName: Nome do repositório
    :count: Quantidade de execuções do pytest
    :params: Parâmetros da análise, isto é, gerar trace, coverage ou profiling
    :return: None
    """
    dirList = getTestDir(modDir)

    cwd = getcwd()
    subprocess.run(["mkdir","-p", f"Test-{modName}"])

    for dir in dirList:
        testFiles = getTestFiles(dir)
        for testFile in testFiles:
            chdir(cwd + "/" + f"Test-{modName}")
            currentFile = "file_" + path.basename(testFile)[:-3]

            subprocess.run(["mkdir","-p", currentFile])
            chdir(path.abspath(currentFile))
            if checkForTestClasses(testFile) is None:
                tests = getTestCases([testFile])

                for testCase in tests[testFile]:
                    runSummary = list()
                    totalTime = 0

                    if checkForTestParametrization(testFile, testCase):
                        for param in getTestParameters(testFile, testCase):
                            subprocess.run(["mkdir","-p", f"{testCase}-{param}"])
                            runSummary = []
                            totalTime = 0
                            for run in range(count):
                                chdir(getcwd() + "/" + testCase + "-" + param)
                                subprocess.run(["mkdir","-p", f"Run-{run}"])
                                runDir = getcwd() + "/" + f"Run-{run}"
                                chdir(runDir)

                                runResult = runTest(testFile, testCase, params, parameters = param, isParametrized = True) 
                                totalTime += runResult[1]
                                chdir(cwd + "/" + f"Test-{modName}/{currentFile}/{testCase}-{param}")
                                runSummary.append(f"Run {run}: {runResult[0]} Tempo: {runResult[1]}\n")
                                chdir(cwd + "/" + f"Test-{modName}/{currentFile}")

                            chdir(cwd + "/" + f"Test-{modName}/{currentFile}/{testCase}-{param}")
                            with open("runsSummary.txt", "a") as f:
                                f.writelines(runSummary)
                                print(f"Tempo total: {totalTime}", file = f)
                            f.close()
                            chdir(cwd + "/" + f"Test-{modName}/{currentFile}")
                    else:
                        for run in range(count):
                            subprocess.run(["mkdir","-p", testCase])
                            chdir(getcwd() + "/" + testCase)
                            subprocess.run(["mkdir","-p", f"Run-{run}"])
                            runDir = getcwd() + "/" + f"Run-{run}"
                            chdir(runDir)
                            runResult = runTest(testFile, testCase, params)
                            totalTime += runResult[1]
                            chdir(cwd + "/" + f"Test-{modName}/{currentFile}/{testCase}")
                            runSummary.append(f"Run {run}: {runResult[0]} Tempo: {runResult[1]}\n")
                            chdir(cwd + "/" + f"Test-{modName}/{currentFile}")

                        chdir(cwd + "/" + f"Test-{modName}/{currentFile}/{testCase}")

                        with open("runsSummary.txt", "a") as f:
                            f.writelines(runSummary)
                            print(f"Tempo total: {totalTime}", file = f)
                        f.close()
                        chdir(cwd + "/" + f"Test-{modName}/{currentFile}")

                chdir(cwd)
            else:
                for className in checkForTestClasses(testFile):
                    tests = getTestsFromClass(className, testFile)
                    for test in tests:
                        if checkForTestParametrization(testFile, test):
                            for param in getTestParameters(testFile, test):
                                subprocess.run(["mkdir","-p", f"{className}::{test}-{param}"])
                                runSummary = list()
                                totalTime = 0
                                for run in range(count):
                                    chdir(getcwd() + f"/{className}::{test}-{param}")
                                    subprocess.run(["mkdir","-p", f"Run-{run}"])
                                    runDir = getcwd() + f"/Run-{run}"
                                    chdir(runDir)
                                    runResult = runTest(testFile, test, params, className = className, isParametrized = True, parameters = param)
                                    totalTime += runResult[1]
                                    chdir(cwd + f"/Test-{modName}/{currentFile}/{className}::{test}-{param}")
                                    runSummary.append(f"Run {run}: {runResult[0]} Tempo: {runResult[1]}\n")
                                    chdir(cwd + f"/Test-{modName}/{currentFile}")

                                with open("runsSummary.txt", "a") as f:
                                    f.writelines(runSummary)
                                    print(f"Tempo total: {totalTime}", file = f)
                                f.close()
                                chdir(cwd + "/" + f"Test-{modName}/{currentFile}")

                        else:
                            subprocess.run(["mkdir","-p", f"{className}::{test}"])
                            runSummary = list()
                            totalTime = 0

                            for run in range(count):
                                chdir(getcwd() + f"/{className}::{test}")
                                subprocess.run(["mkdir","-p", f"Run-{run}"])
                                runDir = getcwd() + "/" + f"Run-{run}"
                                chdir(runDir)
                                runResult = runTest(testFile, test, params, className = className)
                                totalTime += runResult[1]
                                chdir(cwd + "/" + f"Test-{modName}/{currentFile}/{className}::{test}")
                                runSummary.append(f"Run {run}: {runResult[0]} Tempo: {runResult[1]}\n")
                                chdir(cwd + "/" + f"Test-{modName}/{currentFile}")

                            with open("runsSummary.txt", "a") as f:
                                f.writelines(runSummary)
                                print(f"Tempo total: {totalTime}", file = f)
                            f.close()
                            chdir(cwd + "/" + f"Test-{modName}/{currentFile}")

                chdir(cwd)

def getParamsValues(param: str) -> List[Any]:
    """ (deprecated) Recebe parâmetros de um teste os retorna na forma de uma lista. Ex: [1-1-'Foo'] -> [1, 1, 'Foo']"
    :param str: string dos parâmetros de um teste.
    :returns: lista com os parâmetros
    """
    return [eval(item) for item in param.strip('[]').split('-')]

def getTestParameters(testFilePath: str, testName: str) -> List[str]:
    """ (deprecated) Gera uma lista com todos os parâmetros de um teste parametrizado. Útil na execução única de um teste parametrizado com um determinado parâmetro
    :param testFilePath: caminho para o arquivo de teste do teste parametrizado. Aqui, é utilizado o absolute path.
    :param testName: nome do teste.
    :returns: lista com todos os parâmetros do teste. Ex: ['[1-1-'foo']', '[2-2-'bar']']
    """
    parameters: List = []
    foundParametrize: bool = False
    foundFunction: bool = False
    parametersPosition: int = 0
    testFunctionPosition: int = 0

    with open(testFilePath, "r") as file:
        lines = file.readlines()


    while True:
        currentPosition: int = 0
        for line in lines:
            if "@pytest.mark.parametrize" in line:
                parametersPosition = currentPosition
                foundParametrize = True

            elif "def test_" in line:
                if testName in line:
                    testFunctionPosition = currentPosition
                    foundFunction = True
                else:
                    foundParametrize = False
                    foundFunction = False

            currentPosition += 1

        if foundFunction and foundParametrize:
            break
    
    pattern =  r"\(\s*((?:\s*\d+\s*,?\s*)+)\s*\)"
    for lineNo in range(parametersPosition, testFunctionPosition):
        tuples = re.findall(pattern, lines[lineNo])

        for tupleStr in tuples:
            formattedParams = "-".join(map(str.strip, tupleStr.strip("()").split(",")))
            formattedParams = "[" + formattedParams + "]"
            parameters.append(formattedParams)

    return parameters

def checkForTestParametrization(testPath: str, testName: str) -> bool:
    """ (deprecated) Verifica se um teste é parametrizado.
    :param testPath: caminho para o arquivo de teste do teste a ser verificado. Aqui é utilizado o absolute path.
    :param testName: nome do teste a ser verificado.
    :returns: bool, True caso o teste seja parametrizado e false caso contrário.
    """
    with open(testPath, 'r') as file:
        fileContent = file.read()

    testFunctionPattern = rf"def\s+{testName}\s*\("
    parametrizePattern = r"@pytest.mark.parametrize\("
    
    matchTestFunction = re.search(testFunctionPattern, fileContent)
    if matchTestFunction:
        endPosition = matchTestFunction.end()
        testFunctionContent = fileContent[endPosition:]
        matchParametrize = re.search(parametrizePattern, testFunctionContent)
        return matchParametrize is None
    
    return False

def checkForTestClasses(filePath: str) -> Optional[List[str]]:
    """ (deprecated) Verifica se existem classes declaradas no arquivo de testes.
    :param filePath: caminho para o arquivo de testes. Aqui é utilizado o caminho absoluto.
    :returns: lista com os nomes das classes, se existirem. None caso contrário.
    """
    with open(filePath, "r") as f:
        content = f.read()
    f.close()

    tree = parse(content)
    classNames = [node.name for node in walk(tree) if isinstance(node, ClassDef)]

    return classNames if classNames != [] else None

def getTestsFromClass(className: str, filePath: str) -> List[str]:
    """ (deprecated) Fornece os testes declarados dentro de uma determinada classe.
    :param className: nome da classe.
    :param filePath: caminho para o arquivo de testes.
    :returns: lista contendo os testes dentro da classe className.
    """
    with open(filePath, "r") as f:
        content = f.read()
    f.close()

    tree = parse(content)
    tests = list()
    for node in walk(tree):
        if isinstance(node, ClassDef) and node.name == className:
            for item in node.body:
                if isinstance(item, FunctionDef):
                    tests.append(item.name)

    return tests

def runTest(dir: str, testName: str, params: List[bool], className: Optional[str] = None,
            isParametrized: Optional[bool] = False, parameters: Optional[List[Any]] = None) -> Tuple[str, int]:
    """Roda um teste, dado o diretório do arquivo de testes e o nome do teste
    :param dir: diretório do arquivo de testes.
    :param testName: nome do teste.
    :param params: parâmetros da ferramenta de análise (tracing, coverage e profiling).
    :param className: nome da classe onde o teste está inserido. Opcional.
    :param isParametrized: flag que indica se o teste é parametrizado. Opcional.
    :param parameters: parâmetros de um teste paarametrizado. Opcional; mandatório caso isParametrized seja True.
    :returns: resultado do teste, junto com sua duração.
    """

    includeTracing = params[0]
    includeCoverage = params[1]
    includeProfiling = params[2]

    testResult = TestResult(trace = includeTracing, cov = includeCoverage, prof = includeProfiling, 
                            testName = testName, testFileName = dir,
                            isParametrized = isParametrized, params = parameters)

    if className is None:
        if parameters is None:
            pytest.main([f"{dir}::{testName}"], plugins=[testResult])
        else:
            pytest.main([f"{dir}::{testName}{parameters}"], plugins=[testResult])
    else:
        if parameters is None:
            pytest.main([f"{dir}::{className}::{testName}"], plugins=[testResult])
        else:
            pytest.main([f"{dir}::{className}::{testName}{parameters}"], plugins=[testResult])

    if testResult.passed != 0:
        result = "PASSED"
    elif testResult.failed != 0:
        result = "FAILED"
    elif testResult.skipped != 0:
        result = "SKIPPED"
    else:
        result = "XFAILED"

    return (result, testResult.total_duration)

def getTestDir(modDir: str, dirList = []) -> List[str]:
    """Busca por diretórios em um diretório contendo testes
    :param modDir: Caminho para o diretório do módulo
    :returns: Lista contendo os diretórios contendo testes (ex: ../foo/bar/test)
    """
    cwd = getcwd()
    chdir(modDir)

    files = list()
    files = listdir(".")

    for file in files:
        if path.isdir(path.join(getcwd(), file)):
            if file in ["test", "tests"] and path.join(getcwd(), file) not in dirList:
                dirList.append(path.join(getcwd(), file))
            else:
                getTestDir(path.join(getcwd(), file))
    chdir(cwd)
    return dirList

def getTestCases(files: List[str]) -> Dict[str, str]:
    """Procura por casos de teste
    :param files: lista contendo o caminho para os arquivos de teste
    :returns: dicionario contendo nome dos casos de teste de acordo com seu arquivo (ex: {'..test/test_foo.py: [test_bar, test_fulano]'})
    """
    tests = dict()
    names = list()
    for file in files:
        with open(file, "r", encoding = "utf8") as f:
            tree = parse(f.read())
            f.close()
        names = [
            node.name for node in walk(tree) if isinstance(node, FunctionDef) and "test" in node.name
        ]

        tests[file] = names
    return tests

def getTestFiles(dir: str) -> List[str]:
    """Procura por arquivos de teste
    :param dir: Diretório onde se quer procurar
    :returns: lista contendo aquivos dos testes (ex: ['../test/test_foo.py', '../test/test_bar.py'])
    """
    dirPath = Path(dir)
    testFiles = dirPath.glob("test_*.py")

    return [str(file) for file in testFiles]