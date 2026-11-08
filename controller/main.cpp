#include "native_discovery.hpp"
#include "native_execute.hpp"
#include "native_translate.hpp"
#include "native_job.hpp"
// RecompDev v0.4.8: native P-code translation and game execution and discovery controller with explicit legacy fallback.
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
    std::cout<<"RecompDev v0.4.9.21 native controller (compiled job lifecycle + plugin discovery)\n"
      "Usage: RecompDev.exe --rom FILE --stage discover|prepare|recover [options]\n"
      "  --steps N --frames N --max-recoveries N --timeout N --capture-hardware\n"
      "  --auto-continue --max-rounds N (continue source-verified recovery in bounded batches)\n"
      "  --catalogue FILE --out DIR --ghidra FILE --export FILE --budget N\n"
      "  --analyze-evidence DIR [--out DIR] [--reference-image PNG] [--reference-session JSON]\n"
      "  --plugins | --verify | --status | --help\n"
      "  run --rom FILE [--logging debug|info|warning|error] [--max-cycles N]\n"
      "  configure --ghidra PATH --rizin PATH [--evidence-root DIR] [--workspace LEGACY_DIR] [--allow-tool-root DIR]\n"
      "  resume [--job ID] [--max-cycles 1..128] [--preview-stop ZIP]; status [--job ID]; inspect [--job ID]\n"
      "  diagnostics export [--job ID] (redacted upload-ready ZIP; no ROM)\n"
      "  preview [--job ID] [--cycle N] [--frames N] [--steps N] [--monitor-every N]\n"
      "    [--video window|capture] [--input live|neutral] [--no-viewer] [--hold-window]\n"
      "  plugin build|test|activate|rollback|bump|status|release [args]\n"
      "Native --stage native-execute requires --rom FILE --game rd_NAME --out PREFIX; source identity is verified.\n"
      "Native --stage native-orchestrate: --rom ROM --out DIR --plugin-dir DLLS [--ghidra HEADLESS --rizin EXE --allow-tool-root DIR | --export JSON] [--history-root DIR] [--max-rounds N] [--target-frames N].\n"
      "Native --stage native-translate --rom FILE --export GHIDRA_JSON --out DIR [--bank-export JSON] creates and compiles a source-bound game DLL.\n"
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
        if(equals(argv[1],L"--version")){std::cout<<"RecompDev 0.4.9.21\n";return 0;}
        if(equals(argv[1],L"plugin"))op="plugin-manager";
        if(equals(argv[1],L"--plugins"))op="plugins";
        if(equals(argv[1],L"--verify"))op="verify";
        if(equals(argv[1],L"--status"))op="status";
        if(equals(argv[1],L"--analyze-evidence"))op="review-evidence";
#else
        if(equals(argv[1],"--version")){std::cout<<"RecompDev 0.4.9.21\n";return 0;}
        if(equals(argv[1],"plugin"))op="plugin-manager";
        if(equals(argv[1],"--plugins"))op="plugins";
        if(equals(argv[1],"--verify"))op="verify";
        if(equals(argv[1],"--status"))op="status";
        if(equals(argv[1],"--analyze-evidence"))op="review-evidence";
#endif
        // Detect native discovery before resolving the Python checkout. The native
        // path requires only the binary and independently deployed DLL providers.
        bool native_discover=false,native_execute=false,native_translate=false,native_orchestrate=false,legacy_discover=false;
        for(int i=1;i+1<argc;++i){
#ifdef _WIN32
          if(equals(argv[i],L"--stage")){native_discover=equals(argv[i+1],L"discover");native_execute=equals(argv[i+1],L"native-execute");native_translate=equals(argv[i+1],L"native-translate");native_orchestrate=equals(argv[i+1],L"native-orchestrate");legacy_discover=equals(argv[i+1],L"legacy-discover");}
#else
          if(equals(argv[i],"--stage")){native_discover=equals(argv[i+1],"discover");native_execute=equals(argv[i+1],"native-execute");native_translate=equals(argv[i+1],"native-translate");native_orchestrate=equals(argv[i+1],"native-orchestrate");legacy_discover=equals(argv[i+1],"legacy-discover");}
#endif
        }
        if(native_discover||native_execute||native_translate){
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
           return native_execute?rd_native_execute(args,self_path()):native_translate?rd_native_translate(args,self_path()):rd_native_discover(args,self_path());
        }
        fs::path root=project_root(self_path());
#ifdef _WIN32
        const bool native_job=equals(argv[1],L"run")||equals(argv[1],L"resume")||equals(argv[1],L"status")||equals(argv[1],L"inspect")||equals(argv[1],L"configure")||equals(argv[1],L"diagnostics")||equals(argv[1],L"preview");
#else
        const bool native_job=equals(argv[1],"run")||equals(argv[1],"resume")||equals(argv[1],"status")||equals(argv[1],"inspect")||equals(argv[1],"configure")||equals(argv[1],"diagnostics")||equals(argv[1],"preview");
#endif
        if(native_job){
           std::vector<std::string> job_args;
#ifdef _WIN32
           for(int i=1;i<argc;++i){
              int n=WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,argv[i],-1,nullptr,0,nullptr,nullptr);
              if(n<=0)throw std::runtime_error("ARGUMENT_UTF8_CONVERSION_FAILED");
              std::string v(size_t(n),'\0');
              if(!WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,argv[i],-1,v.data(),n,nullptr,nullptr))throw std::runtime_error("ARGUMENT_UTF8_CONVERSION_FAILED");
              v.pop_back();job_args.push_back(std::move(v));
           }
           auto invoke=[&](const std::vector<std::string>&cmd)->int{
              std::vector<std::wstring> forwarded={(cmd.size()>1 && cmd[0]=="--stage" && cmd[1]=="job-diagnostics" ? (root/L"workspace"/L"diagnostics_export.py") :
                 cmd.size()>1 && cmd[0]=="--stage" && cmd[1]=="job-preview" ? (root/L"execution_monitor"/L"job_preview.py") :
                 cmd.size()>1 && cmd[0]=="--stage" && cmd[1]=="preview-verify" ? (root/L"analysis_integration"/L"preview_frontier.py") : (root/L"analysis_integration"/L"cli.py")).wstring()};
              for(auto&str:cmd){
                  int n=MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,str.c_str(),-1,nullptr,0);
                  if(n<=0)throw std::runtime_error("PROVIDER_ARGUMENT_UTF8_INVALID");
                  std::wstring w(size_t(n),L'\0');
                  if(!MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,str.c_str(),-1,w.data(),n))throw std::runtime_error("PROVIDER_ARGUMENT_UTF8_INVALID");
                  w.pop_back();forwarded.push_back(std::move(w));
              }
              if(!(cmd.size()>1 && (cmd[1]=="job-diagnostics"||cmd[1]=="job-preview"||cmd[1]=="preview-verify"))){forwarded.emplace_back(L"--controller-exe");forwarded.emplace_back(self_path().wstring());
              forwarded.emplace_back(L"--source-root");forwarded.emplace_back(root.wstring());}
              return spawn(root,forwarded);
           };
#else
           for(int i=1;i<argc;++i)job_args.emplace_back(argv[i]);
           auto invoke=[&](const std::vector<std::string>&cmd)->int{
              std::vector<std::string> forwarded={(cmd.size()>1 && cmd[0]=="--stage" && cmd[1]=="job-diagnostics" ? (root/"workspace"/"diagnostics_export.py") :
                 cmd.size()>1 && cmd[0]=="--stage" && cmd[1]=="job-preview" ? (root/"execution_monitor"/"job_preview.py") :
                 cmd.size()>1 && cmd[0]=="--stage" && cmd[1]=="preview-verify" ? (root/"analysis_integration"/"preview_frontier.py") : (root/"analysis_integration"/"cli.py")).string()};
              forwarded.insert(forwarded.end(),cmd.begin(),cmd.end());
              if(!(cmd.size()>1 && (cmd[1]=="job-diagnostics"||cmd[1]=="job-preview"||cmd[1]=="preview-verify"))){forwarded.emplace_back("--controller-exe");forwarded.emplace_back(self_path().string());
              forwarded.emplace_back("--source-root");forwarded.emplace_back(root.string());}
              return spawn(root,forwarded);
           };
#endif
           return rd_native_job(job_args,root,self_path(),invoke);
        }
        if(native_orchestrate){
#ifdef _WIN32
            std::vector<std::wstring> forwarded={(root/L"analysis_integration"/L"cli.py").wstring()};
            for(int i=1;i<argc;++i)forwarded.emplace_back(argv[i]);
            forwarded.emplace_back(L"--controller-exe");forwarded.emplace_back(self_path().wstring());
            forwarded.emplace_back(L"--source-root");forwarded.emplace_back(root.wstring());
            return spawn(root,forwarded);
#else
            std::vector<std::string> forwarded={(root/"analysis_integration"/"cli.py").string()};
            for(int i=1;i<argc;++i)forwarded.emplace_back(argv[i]);
            forwarded.emplace_back("--controller-exe");forwarded.emplace_back(self_path().string());
            forwarded.emplace_back("--source-root");forwarded.emplace_back(root.string());
            return spawn(root,forwarded);
#endif
        }
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
