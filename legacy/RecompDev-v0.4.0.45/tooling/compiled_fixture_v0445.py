"""Portable compiled-fixture runner using CMake's platform-selected C++ compiler.

Do not invoke MSVC cl.exe with GCC flags. Runtime availability is reported as an
explicit failure for mandatory release qualification, never a silent skip.
"""
from pathlib import Path
import shutil
import subprocess


def executable_in_build(build: Path, target: str) -> Path:
    """Find the one output for both single- and multi-configuration generators."""
    build = Path(build)
    files = [p for p in build.rglob("*") if p.is_file() and
             p.name.lower() in (target.lower(), (target + ".exe").lower())]
    if len(files) != 1:
        raise RuntimeError(f"Expected exactly one {target} executable in {build}; found {len(files)}")
    return files[0]


def run_cpp_fixture(source: str, root: Path, workspace: Path, target="RecompDevPsgFixture"):
    """Compile then execute C++ with CMake (MSVC, MinGW, Clang and GCC supported)."""
    if not shutil.which("cmake"):
        raise RuntimeError("Mandatory compiled fixture requires CMake and a supported C++ toolchain")
    workspace = Path(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    src = workspace / "test.cpp"
    src.write_text(source, encoding="utf-8")
    source_root = Path(root).resolve().as_posix()
    (workspace / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 3.17)\n"
        "project(RecompDevCompiledFixture LANGUAGES CXX)\n"
        f"add_executable({target} test.cpp)\n"
        f"target_compile_features({target} PRIVATE cxx_std_17)\n"
        f'target_include_directories({target} PRIVATE "{source_root}")\n',
        encoding="utf-8")
    build = workspace / "build"
    steps = (
        (["cmake", "-S", str(workspace), "-B", str(build), "-DCMAKE_BUILD_TYPE=Debug"], 120),
        (["cmake", "--build", str(build), "--config", "Debug"], 180),
    )
    for command, timeout in steps:
        try:
            p = subprocess.run(command, capture_output=True, text=True, timeout=timeout, errors="replace")
        except (OSError, subprocess.TimeoutExpired) as e:
            raise RuntimeError(f"CMake fixture command could not execute: {command}: {e}") from e
        if p.returncode:
            raise RuntimeError(f"CMake fixture failed ({p.returncode}): {(p.stdout + p.stderr)[-5000:]}")
    binary = executable_in_build(build, target)
    try:
        p = subprocess.run([str(binary)], capture_output=True, text=True, timeout=20, errors="replace")
    except (OSError, subprocess.TimeoutExpired) as e:
        raise RuntimeError(f"Compiled fixture could not execute: {binary}: {e}") from e
    if p.returncode:
        raise AssertionError(f"Compiled fixture returned {p.returncode}: {(p.stdout+p.stderr)[-5000:]}")
    return p
