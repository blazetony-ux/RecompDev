#include "native_discovery.hpp"
// RecompDev v0.4.5: native discovery controller with explicit legacy fallback.
// The preserved Python analysis/recovery services are deliberately retained.
// No shell invocation: all forwarded arguments remain literal even with spaces.
#include <filesystem>
#include <fstream>
#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>
#include <system_error>
#include <stdexcept>
#include <cerrno>
#include <cstring>
#ifdef _WIN32
#define NOMINMAX
#include <windows.h>
#include "recompdev_python_config.h"
#else
#include <unistd.h>
#include <sys/wait.h>
#include <limits.h>
#endif
namespace fs = std::filesystem;
#ifdef _WIN32
using NativeString = std::wstring;
static fs::path self_path() {
    std::wstring buffer(32768, L'\0');
    DWORD count = GetModuleFileNameW(nullptr,buffer.data(),static_cast<DWORD>(buffer.size()));
    if(count==0 || count==buffer.size()) throw std::runtime_error("Cannot determine RecompDev executable path");
    buffer.resize(count);return fs::path(buffer);
}
static std::wstring quote(const std::wstring& value) {
    // Windows argv quoting (CommandLineToArgvW / MSVCRT conventions).
    std::wstring out=L"\"";size_t slashes=0;
    for(wchar_t c:value){
        if(c==L'\\'){++slashes;continue;}
        if(c==L'"'){out.append(slashes*2+1,L'\\');out+=L'"';slashes=0;continue;}
        out.append(slashes,L'\\');slashes=0;out+=c;
    }
    out.append(slashes*2,L'\\');out+=L'"';return out;
}
static int spawn(const fs::path& root, const std::vector<std::wstring>& args){
    // Prefer the interpreter CMake actually found (which may not be on PATH).
    // Important: "py.exe -3" is not universally safe on Windows: some py.exe
    // shims delegate directly to python.exe, which rejects the -3 option.
    struct Candidate { std::wstring executable; std::vector<std::wstring> options; };
    std::vector<Candidate> candidates;
    const std::wstring configured = RECOMPDEV_CONFIGURED_PYTHON;
    if(!configured.empty()) candidates.push_back({configured,{L"-u"}});
    candidates.push_back({L"python.exe",{L"-u"}});
    candidates.push_back({L"python3.exe",{L"-u"}});
    // Use the Python launcher only as a last resort. Do not repeat failed
    // jobs: only move to the next candidate when process creation fails.
    candidates.push_back({L"py.exe",{L"-3",L"-u"}});
    for(const auto& candidate:candidates){
        std::wstring command=quote(candidate.executable);
        for(const auto& arg:candidate.options){command+=L" ";command+=quote(arg);}
        for(const auto& arg:args){command+=L" ";command+=quote(arg);}
        std::vector<wchar_t> mutable_command(command.begin(),command.end());mutable_command.push_back(L'\0');
        STARTUPINFOW si{};si.cb=sizeof(si);PROCESS_INFORMATION pi{};
        std::wstring working=root.wstring();
        // Provide the exact image path when CMake discovered an absolute path.
        // For unqualified fallbacks, use Windows' normal executable search.
        const bool has_path=candidate.executable.find(L'\\')!=std::wstring::npos ||
                            candidate.executable.find(L'/')!=std::wstring::npos;
        const wchar_t* app=has_path?candidate.executable.c_str():nullptr;
        if(!CreateProcessW(app,mutable_command.data(),nullptr,nullptr,TRUE,0,nullptr,
                           working.c_str(),&si,&pi)) continue;
        WaitForSingleObject(pi.hProcess,INFINITE);
        DWORD code=1;
        GetExitCodeProcess(pi.hProcess,&code);
        CloseHandle(pi.hThread);CloseHandle(pi.hProcess);
        return static_cast<int>(code);
    }
    std::wcerr<<L"Cannot launch Python 3; install Python 3 and its Windows launcher.\n";
    return 127;
}
#else
static fs::path self_path(){
    char buf[PATH_MAX+1]{};ssize_t n=readlink("/proc/self/exe",buf,PATH_MAX);
    if(n<0) throw std::runtime_error("Cannot determine executable path");
    return fs::path(std::string(buf,static_cast<size_t>(n)));
}
static int spawn(const fs::path& root,const std::vector<std::string>& args){
    pid_t pid=fork();if(pid<0)return 127;
    if(pid==0){
        if(chdir(root.c_str())!=0)_exit(127);
        std::vector<char*> av;av.reserve(args.size()+2);
        av.push_back(const_cast<char*>("python3"));
        for(const auto& s:args)av.push_back(const_cast<char*>(s.c_str()));
        av.push_back(nullptr);execvp("python3",av.data());_exit(127);
    }
    int status=0;while(waitpid(pid,&status,0)<0){if(errno!=EINTR)return 127;}
    if(WIFEXITED(status))return WEXITSTATUS(status);
    return WIFSIGNALED(status)?128+WTERMSIG(status):1;
}
#endif
static bool is_source_root(const fs::path& root){
    return fs::is_regular_file(root/"modular"/"cli.py") &&
           fs::is_regular_file(root/"RELEASE_ID.txt");
}
static fs::path project_root(fs::path exe){
    // Deployed exe lives outside the Git checkout. A text pointer in the
    // runtime directory selects that checkout without embedding local paths.
    fs::path at=exe.parent_path();
    const fs::path pointer=at/"source-root.txt";
    if(fs::is_regular_file(pointer)){
        std::ifstream fp(pointer);
        std::string line;
        if(!std::getline(fp,line) || line.empty())
            throw std::runtime_error("Invalid runtime source-root.txt");
        fs::path root=fs::absolute(fs::path(line)).lexically_normal();
        if(!is_source_root(root))
            throw std::runtime_error("Runtime source-root.txt does not identify a source checkout");
        return root;
    }
    if(const char* env=std::getenv("RECOMPDEV_SOURCE_ROOT")){
        if(*env && is_source_root(fs::path(env)))return fs::path(env);
    }
    // Preserve compatibility with older in-tree test installations.
    for(int i=0;i<7;++i){
        if(is_source_root(at))return at;
        if(at==at.parent_path()) break;
        at=at.parent_path();
    }
    throw std::runtime_error("RecompDev source checkout not found; runtime needs source-root.txt");
}
static void usage(){
    std::cout<<"RecompDev v0.4.5 native controller (legacy services retained)\n"
      "Usage: RecompDev.exe --rom FILE --stage discover|prepare|recover [options]\n"
      "  --steps N --frames N --max-recoveries N --timeout N --capture-hardware\n"
      "  --auto-continue --max-rounds N (continue source-verified recovery in bounded batches)\n"
      "  --catalogue FILE --out DIR --ghidra FILE --export FILE --budget N\n"
      "  --analyze-evidence DIR [--out DIR] [--reference-image PNG] [--reference-session JSON]\n"
      "  --plugins | --verify | --status | --help\n"
      "  plugin build|test|activate|rollback|bump|status|release [args]\n"
      "Native --stage discover loads native format/CPU/machine DLLs; use --stage legacy-discover for historical Python pipeline.\n";
}
#ifdef _WIN32
int wmain(int argc,wchar_t** argv)
#else
int main(int argc,char** argv)
#endif
{
    try{
        if(argc==1){usage();return 0;}
        std::string op="run-rom";
#ifdef _WIN32
        auto equals=[](const wchar_t* a,const wchar_t* b){return wcscmp(a,b)==0;};
#else
        auto equals=[](const char* a,const char* b){return strcmp(a,b)==0;};
#endif
        if(equals(argv[1],
#ifdef _WIN32
          L"--help"
#else
          "--help"
#endif
          )){usage();return 0;}
#ifdef _WIN32
        if(equals(argv[1],L"--version")){std::cout<<"RecompDev 0.4.5\n";return 0;}
        if(equals(argv[1],L"plugin"))op="plugin-manager";
        if(equals(argv[1],L"--plugins"))op="plugins";
        if(equals(argv[1],L"--verify"))op="verify";
        if(equals(argv[1],L"--status"))op="status";
        if(equals(argv[1],L"--analyze-evidence"))op="review-evidence";
#else
        if(equals(argv[1],"--version")){std::cout<<"RecompDev 0.4.5\n";return 0;}
        if(equals(argv[1],"plugin"))op="plugin-manager";
        if(equals(argv[1],"--plugins"))op="plugins";
        if(equals(argv[1],"--verify"))op="verify";
        if(equals(argv[1],"--status"))op="status";
        if(equals(argv[1],"--analyze-evidence"))op="review-evidence";
#endif
        // Detect native discovery before resolving the Python checkout. The native
        // path requires only the binary and independently deployed DLL providers.
        bool native_discover=false,legacy_discover=false;
        for(int i=1;i+1<argc;++i){
#ifdef _WIN32
          if(equals(argv[i],L"--stage")){native_discover=equals(argv[i+1],L"discover");legacy_discover=equals(argv[i+1],L"legacy-discover");}
#else
          if(equals(argv[i],"--stage")){native_discover=equals(argv[i+1],"discover");legacy_discover=equals(argv[i+1],"legacy-discover");}
#endif
        }
        if(native_discover){
           std::vector<std::string> args;
#ifdef _WIN32
           for(int i=1;i<argc;++i){
              int n=WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,argv[i],-1,nullptr,0,nullptr,nullptr);
              if(!n)throw std::runtime_error("ARGUMENT_UTF8_CONVERSION_FAILED");
              std::string u(size_t(n), '\0');
              if(!WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,argv[i],-1,u.data(),n,nullptr,nullptr))throw std::runtime_error("ARGUMENT_UTF8_CONVERSION_FAILED");
              u.pop_back();args.push_back(std::move(u));
           }
#else
           for(int i=1;i<argc;++i)args.emplace_back(argv[i]);
#endif
           return rd_native_discover(args,self_path());
        }
        fs::path root=project_root(self_path());
#ifdef _WIN32
        std::vector<std::wstring> forwarded;
        if(op=="plugin-manager"){
            forwarded.emplace_back((root/L"workspace"/L"manager.py").wstring());
            for(int i=2;i<argc;++i)forwarded.emplace_back(argv[i]);
        }else{
            forwarded={(root/L"modular"/L"cli.py").wstring(),std::wstring(op.begin(),op.end())};
            if(op=="run-rom")for(int i=1;i<argc;++i){if(legacy_discover&&i>1&&equals(argv[i-1],L"--stage"))forwarded.emplace_back(L"discover");else forwarded.emplace_back(argv[i]);}
            if(op=="review-evidence") {for(int i=1;i<argc;++i) {if(i==1) forwarded.emplace_back(L"--evidence-dir"); else forwarded.emplace_back(argv[i]);}}
        }
#else
        std::vector<std::string> forwarded;
        if(op=="plugin-manager"){
            forwarded.emplace_back((root/"workspace"/"manager.py").string());
            for(int i=2;i<argc;++i)forwarded.emplace_back(argv[i]);
        }else{
            forwarded={(root/"modular"/"cli.py").string(),op};
            if(op=="run-rom")for(int i=1;i<argc;++i){if(legacy_discover&&i>1&&equals(argv[i-1],"--stage"))forwarded.emplace_back("discover");else forwarded.emplace_back(argv[i]);}
            if(op=="review-evidence") {for(int i=1;i<argc;++i) {if(i==1) forwarded.emplace_back("--evidence-dir"); else forwarded.emplace_back(argv[i]);}}
        }
#endif
        return spawn(root,forwarded);
    }catch(const std::exception& e){std::cerr<<"RecompDev controller error: "<<e.what()<<'\n';return 1;}
}
