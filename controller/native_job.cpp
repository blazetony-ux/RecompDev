#include "native_job.hpp"
#include "rd_tiny_json.hpp"
#include "rd_sha256.hpp"
#include <algorithm>
#include <chrono>
#include <cctype>
#include <cstdlib>
#include <ctime>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <vector>
#ifdef _WIN32
#define NOMINMAX
#include <windows.h>
#else
#include <unistd.h>
#endif
namespace fs=std::filesystem;
namespace {
using rdjson::V;
constexpr size_t kMaxJson=2*1024*1024,kMaxRom=64*1024*1024,kMaxLog=16*1024*1024;
struct Error:std::runtime_error{using std::runtime_error::runtime_error;};
std::string iso_utc(){
    auto now=std::chrono::system_clock::now();std::time_t t=std::chrono::system_clock::to_time_t(now);
    std::tm x{};
#ifdef _WIN32
    gmtime_s(&x,&t);
#else
    gmtime_r(&t,&x);
#endif
    std::ostringstream s;s<<std::put_time(&x,"%Y-%m-%dT%H:%M:%SZ");return s.str();
}
std::string compact_time(){auto s=iso_utc();s.erase(std::remove_if(s.begin(),s.end(),[](char c){return c=='-'||c==':';}),s.end());return s;}
std::string q(const std::string& s){return rdjson::escape(s);}
std::string read_bound(const fs::path& path,size_t cap=kMaxJson){
    std::error_code ec;
    if(!fs::is_regular_file(path,ec)||fs::file_size(path,ec)>cap||ec)throw Error("JOB_FILE_MISSING_OR_TOO_LARGE: "+path.filename().string());
    std::ifstream in(path,std::ios::binary);if(!in)throw Error("JOB_FILE_UNREADABLE");
    return std::string(std::istreambuf_iterator<char>(in),{});
}
V read_json(const fs::path& p){auto contents=read_bound(p);return rdjson::Reader(contents).parse();}
std::string getstr(const V&v,const std::string&k){return v.get(k).string();}
int as_int(const V&v,const std::string&k){auto n=v.get(k).integer();if(n<0||n>1000000000)throw Error("INVALID_JOB_INTEGER_"+k);return int(n);}
std::string safe_job_id(const std::string&s){
    if(s.empty()||s.size()>100||s.find("job-")!=0)throw Error("INVALID_JOB_ID");
    for(auto c:s)if(!std::isalnum(static_cast<unsigned char>(c))&&c!='-'&&c!='_')throw Error("INVALID_JOB_ID");
    return s;
}
std::string hash_rom(const fs::path& p){
    std::error_code ec;auto sz=fs::file_size(p,ec);
    if(ec||!sz||sz>kMaxRom)throw Error("ROM_SIZE_UNSUPPORTED_OR_MISSING");
    std::ifstream in(p,std::ios::binary);if(!in)throw Error("ROM_UNREADABLE");
    std::vector<uint8_t> buf(static_cast<size_t>(sz));in.read(reinterpret_cast<char*>(buf.data()),static_cast<std::streamsize>(sz));
    if(!in)throw Error("ROM_READ_FAILED");
    return rdhash::sha256(buf.data(),buf.size());
}
fs::path full(const std::string& p){if(p.empty())throw Error("EMPTY_PATH");return fs::canonical(fs::u8path(p));}
fs::path home(){
    const char* env=std::getenv("RECOMPDEV_HOME");
    if(env&&*env)return fs::absolute(fs::u8path(env)).lexically_normal();
#ifdef _WIN32
    env=std::getenv("LOCALAPPDATA");if(env&&*env)return fs::path(env)/"RecompDev";
#else
    env=std::getenv("XDG_STATE_HOME");if(env&&*env)return fs::path(env)/"recompdev";
    env=std::getenv("HOME");if(env&&*env)return fs::path(env)/".local/state/recompdev";
#endif
    throw Error("RECOMPDEV_HOME_NOT_AVAILABLE");
}
void atomic_write(const fs::path& p,const std::string& data){
    if(data.size()>kMaxJson)throw Error("JOB_STATE_TOO_LARGE");
    fs::create_directories(p.parent_path());
    auto tmp=p;tmp+=".pending";
    if(fs::exists(tmp))throw Error("PENDING_STATE_ALREADY_EXISTS");
    {std::ofstream out(tmp,std::ios::binary|std::ios::trunc);if(!out)throw Error("STATE_WRITE_FAILED");out<<data;out.flush();if(!out)throw Error("STATE_FLUSH_FAILED");}
#ifdef _WIN32
    if(!MoveFileExW(tmp.c_str(),p.c_str(),MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH)){
        fs::remove(tmp);throw Error("STATE_REPLACE_FAILED");
    }
#else
    std::error_code ec;fs::rename(tmp,p,ec);if(ec){fs::remove(tmp);throw Error("STATE_REPLACE_FAILED");}
#endif
}
std::string jsonarr(const std::vector<std::string>&items){std::string s="[";for(auto &i:items){if(s.size()>1)s+=",";s+=q(i);}return s+"]";}
struct Options{
    std::string rom,job,logging="info",ghidra,rizin,plugin_dir,import_history,workspace,evidence_root;
    std::vector<std::string> roots;
    int max_cycles=8,rounds=4,target_frames=1800,timeout=600,step_budget=20000000;
    bool have_cycles=false;
};
int number(const std::string&name,const std::string&s,int lo,int hi){
    if(s.empty()||!std::all_of(s.begin(),s.end(),[](char c){return c>='0'&&c<='9';}))throw Error("INVALID_"+name);
    try{auto n=std::stoll(s);if(n<lo||n>hi)throw Error("OUT_OF_RANGE_"+name);return static_cast<int>(n);}
    catch(const std::out_of_range&){throw Error("OUT_OF_RANGE_"+name);}
}
Options parse(const std::vector<std::string>&argv){
    Options opt;
    for(size_t i=1;i<argv.size();i++){
        auto key=argv[i];if(i+1>=argv.size())throw Error("MISSING_VALUE_"+key);
        auto val=argv[++i];
        if(key=="--rom")opt.rom=val;
        else if(key=="--job")opt.job=safe_job_id(val);
        else if(key=="--logging")opt.logging=val;
        else if(key=="--ghidra")opt.ghidra=val;
        else if(key=="--rizin")opt.rizin=val;
        else if(key=="--plugin-dir")opt.plugin_dir=val;
        else if(key=="--import-history")opt.import_history=val;
        else if(key=="--workspace")opt.workspace=val;
        else if(key=="--evidence-root")opt.evidence_root=val;
        else if(key=="--allow-tool-root")opt.roots.push_back(val);
        else if(key=="--max-cycles"){opt.max_cycles=number("MAX_CYCLES",val,1,16);opt.have_cycles=true;}
        else if(key=="--rounds-per-cycle")opt.rounds=number("ROUNDS_PER_CYCLE",val,1,8);
        else if(key=="--target-frames")opt.target_frames=number("TARGET_FRAMES",val,1,36000);
        else if(key=="--timeout")opt.timeout=number("TIMEOUT",val,30,7200);
        else if(key=="--step-budget")opt.step_budget=number("STEP_BUDGET",val,1,20000000);
        else throw Error("UNKNOWN_JOB_OPTION_"+key);
    }
    if(opt.logging!="debug"&&opt.logging!="info"&&opt.logging!="warning"&&opt.logging!="error")throw Error("INVALID_LOGGING_LEVEL");
    return opt;
}
std::string config_json(const Options&o){
    return "{\"schema\":\"recompdev.controller.config.v1\",\"ghidra\":"+q(o.ghidra)+",\"rizin\":"+q(o.rizin)+",\"allow_tool_roots\":"+jsonarr(o.roots)+",\"workspace\":"+q(o.workspace)+",\"evidence_root\":"+q(o.evidence_root)+"}\n";
}
Options load_config(const fs::path&h){
    V v=read_json(h/"config.json");
    if(getstr(v,"schema")!="recompdev.controller.config.v1")throw Error("CONFIG_SCHEMA_MISMATCH");
    Options opt;opt.ghidra=getstr(v,"ghidra");opt.rizin=getstr(v,"rizin");
    if(v.get("workspace").t==V::String)opt.workspace=getstr(v,"workspace");
    if(v.get("evidence_root").t==V::String)opt.evidence_root=getstr(v,"evidence_root");
    for(auto& x:v.get("allow_tool_roots").array())opt.roots.push_back(x.string());
    if(opt.roots.empty()||opt.roots.size()>16)throw Error("CONFIG_TOOL_ROOTS_INVALID");
    return opt;
}
bool within(const fs::path& p,const fs::path& root){auto i=p.begin(),j=root.begin();for(;j!=root.end();++i,++j)if(i==p.end()||*i!=*j)return false;return true;}
// Evidence lives under <configured-root>/v0.4.9.18, independently of old job locations.
// The prior --workspace value is recognised but never rewritten automatically.
// A version-like trailing directory is treated as an older release workspace,
// allowing existing owner configuration to transparently select v0.4.9.18.
constexpr const char* kEvidenceVersion = "v0.4.9.18";
bool is_version_folder(const std::string& name){
    if(name.size()<6||name[0]!='v')return false;
    int dots=0;
    for(size_t i=1;i<name.size();i++){
        if(name[i]=='.'){++dots;continue;}
        if(!std::isdigit(static_cast<unsigned char>(name[i])))return false;
    }
    return dots>=2&&dots<=3;
}
fs::path evidence_root(const fs::path& h,const fs::path& source){
    Options opt=load_config(h);
    fs::path proposed;
    if(!opt.evidence_root.empty())proposed=fs::u8path(opt.evidence_root);
    else if(!opt.workspace.empty()){
        proposed=fs::u8path(opt.workspace);
        if(is_version_folder(proposed.filename().u8string()))proposed=proposed.parent_path();
    }else proposed=source.parent_path()/"RecompDev-Evidence";
    if(!proposed.is_absolute())throw Error("EVIDENCE_ROOT_MUST_BE_ABSOLUTE");
    auto root=fs::weakly_canonical(proposed);
    if(root==root.root_path()||within(root,source)||within(root,h)||within(h,root))throw Error("EVIDENCE_ROOT_LOCATION_UNSAFE");
    return root;
}
fs::path workspace(const fs::path& h,const fs::path& source){
    return evidence_root(h,source)/kEvidenceVersion;
}
fs::path locate_jobs(const fs::path& preferred,const fs::path& h,const std::string& id){
    safe_job_id(id);
    auto candidate=[&](const fs::path& jobs)->bool{
        std::error_code ec;
        auto dir=jobs/id;
        return !fs::is_symlink(dir,ec)&&fs::is_regular_file(dir/"job.json",ec);
    };
    if(candidate(preferred/"jobs"))return preferred/"jobs";
    // Support any previous version folder under the same configured root,
    // without rewriting/moving old evidence or recursively searching the disk.
    std::error_code ec;int inspected=0;
    auto root=preferred.parent_path();
    if(fs::is_directory(root,ec)){
        for(const auto& dir:fs::directory_iterator(root)){
            if(++inspected>128)throw Error("LEGACY_JOB_WORKSPACE_LIMIT");
            if(dir.is_symlink(ec)||!dir.is_directory(ec)||!is_version_folder(dir.path().filename().u8string()))continue;
            if(candidate(dir.path()/"jobs"))return dir.path()/"jobs";
        }
    }
    // Pre-v0.4.9.18 workspaces may be unversioned paths.
    Options opt=load_config(h);
    if(!opt.workspace.empty()&&candidate(fs::u8path(opt.workspace)/"jobs"))return fs::u8path(opt.workspace)/"jobs";
    if(candidate(h/"jobs"))return h/"jobs";
    throw Error("JOB_NOT_FOUND_IN_EVIDENCE_OR_LEGACY_HOME");
}
void authorize(const Options&o){
    if(o.ghidra.empty()||o.rizin.empty())throw Error("CONFIGURE_GHIDRA_AND_RIZIN_FIRST");
    for(auto& tool:{o.ghidra,o.rizin}){
        auto f=full(tool);if(!fs::is_regular_file(f))throw Error("TOOL_NOT_A_FILE");
        bool good=false;for(auto& root:o.roots)if(within(f,full(root)))good=true;
        if(!good)throw Error("TOOL_OUTSIDE_AUTHORIZED_ROOT");
    }
}
struct Log{
    fs::path path;std::string job_id;int threshold=1;
    explicit Log(fs::path p,std::string id,std::string level):path(std::move(p)),job_id(std::move(id)){
        if(level=="debug")threshold=0;else if(level=="info")threshold=1;else if(level=="warning")threshold=2;else threshold=3;
    }
    void emit(int lvl,const std::string&code,const std::string&message){
        static const char*level[]={"debug","info","warning","error"};
        auto event="{\"schema\":\"recompdev.controller.event.v1\",\"timestamp\":"+q(iso_utc())+
            ",\"level\":"+q(level[lvl])+",\"job_id\":"+q(job_id)+",\"component\":\"controller.jobs\",\"code\":"+q(code)+",\"message\":"+q(message)+"}\n";
        if(fs::exists(path)&&fs::file_size(path)+event.size()>kMaxLog)throw Error("LOG_LIMIT_REACHED");
        std::ofstream out(path,std::ios::binary|std::ios::app);if(!out)throw Error("LOG_OPEN_FAILED");out<<event;out.flush();if(!out)throw Error("LOG_WRITE_FAILED");
        if(lvl>=threshold)std::cout<<"["<<level[lvl]<<"] "<<code<<": "<<message<<"\n";
    }
};
struct Attempt{int cycle=0,frames=0,emitted=0;std::string status,reason,output,frontier;};
struct Job{
    std::string id,rom,sha,status="READY",plugin_dir,ghidra,rizin,import_history;
    std::vector<std::string> roots;int max_cycles=8,rounds=4,target_frames=1800,timeout=600,step_budget=20000000,stagnant=0;
    std::vector<Attempt> attempts;
};
std::string save_doc(const Job&j){
    std::string s="{\"schema\":\"recompdev.controller.job.v1\",\"id\":"+q(j.id)+",\"rom\":"+q(j.rom)+
      ",\"rom_sha256\":"+q(j.sha)+",\"status\":"+q(j.status)+",\"plugin_dir\":"+q(j.plugin_dir)+
      ",\"ghidra\":"+q(j.ghidra)+",\"rizin\":"+q(j.rizin)+",\"import_history\":"+q(j.import_history)+",\"allow_tool_roots\":"+jsonarr(j.roots)+
      ",\"max_cycles\":"+std::to_string(j.max_cycles)+",\"rounds_per_cycle\":"+std::to_string(j.rounds)+
      ",\"target_frames\":"+std::to_string(j.target_frames)+",\"timeout\":"+std::to_string(j.timeout)+
      ",\"step_budget\":"+std::to_string(j.step_budget)+",\"stagnant\":"+std::to_string(j.stagnant)+",\"attempts\":[";
    for(auto& a:j.attempts){if(s.back()!='[')s+=",";s+="{\"cycle\":"+std::to_string(a.cycle)+",\"frames\":"+std::to_string(a.frames)+
      ",\"emitted\":"+std::to_string(a.emitted)+",\"status\":"+q(a.status)+",\"reason\":"+q(a.reason)+",\"output\":"+q(a.output)+",\"frontier\":"+q(a.frontier)+"}";}
    return s+"]}\n";
}
Job load_job(const fs::path& jobs,const std::string&id){
    auto v=read_json(jobs/safe_job_id(id)/"job.json");
    if(getstr(v,"schema")!="recompdev.controller.job.v1"||getstr(v,"id")!=id)throw Error("JOB_SCHEMA_OR_ID_MISMATCH");
    Job j;j.id=id;j.rom=getstr(v,"rom");j.sha=getstr(v,"rom_sha256");j.status=getstr(v,"status");
    j.ghidra=getstr(v,"ghidra");j.rizin=getstr(v,"rizin");j.plugin_dir=getstr(v,"plugin_dir");
    if(v.get("import_history").t==V::String)j.import_history=getstr(v,"import_history");
    for(auto&x:v.get("allow_tool_roots").array())j.roots.push_back(x.string());
    j.max_cycles=as_int(v,"max_cycles");j.rounds=as_int(v,"rounds_per_cycle");j.target_frames=as_int(v,"target_frames");j.timeout=as_int(v,"timeout");
    j.step_budget=as_int(v,"step_budget");j.stagnant=as_int(v,"stagnant");
    if(j.max_cycles<1||j.max_cycles>16||j.rounds<1||j.rounds>8||j.target_frames<1||j.target_frames>36000||j.attempts.size()>16)throw Error("JOB_BOUNDS_INVALID");
    for(auto&x:v.get("attempts").array()){
        Attempt a;a.cycle=as_int(x,"cycle");a.frames=as_int(x,"frames");a.emitted=as_int(x,"emitted");a.status=getstr(x,"status");a.reason=getstr(x,"reason");a.output=getstr(x,"output");
        if(x.get("frontier").t==V::String)a.frontier=getstr(x,"frontier");
        if(a.cycle!=int(j.attempts.size())+1||a.output!=(jobs/id/"sessions"/(std::string("cycle-")+(a.cycle<10?"0":"")+std::to_string(a.cycle))).u8string())throw Error("JOB_SESSION_PATH_OR_ORDER_INVALID");
        j.attempts.push_back(a);
    }
    if(j.attempts.size()>16)throw Error("JOB_ATTEMPTS_INVALID");
    return j;
}
std::string last_id(const fs::path&h){auto s=read_bound(h/"last-job.txt",200);while(!s.empty()&&(s.back()=='\r'||s.back()=='\n'))s.pop_back();return safe_job_id(s);}
void report(const Job&j,bool details){
    std::cout<<"RECOMPDEV_JOB_ID="<<j.id<<"\nRECOMPDEV_JOB_STATUS="<<j.status<<"\nRECOMPDEV_CYCLES="<<j.attempts.size()<<"/"<<j.max_cycles<<"\n";
    int best=0;for(auto&a:j.attempts)best=std::max(best,a.frames);
    std::cout<<"RECOMPDEV_BEST_FRAMES="<<best<<"\nRECOMPDEV_TARGET_FRAMES="<<j.target_frames<<"\n";
    if(details){std::cout<<"RECOMPDEV_ROM_SHA256="<<j.sha<<"\n";for(auto&a:j.attempts)std::cout<<"CYCLE="<<a.cycle<<" FRAMES="<<a.frames<<" EMITTED="<<a.emitted<<" STATUS="<<a.status<<" OUTPUT="<<a.output<<"\n";}
}
int execute(Job&j,const fs::path&jobs,const fs::path&diagnostic_dir,const fs::path&exe,const std::function<int(const std::vector<std::string>&)>&bridge,const std::string&logging){
    const auto dir=jobs/j.id;Log log(dir/"events.jsonl",j.id,logging);
    if(hash_rom(full(j.rom))!=j.sha)throw Error("ROM_SOURCE_CHANGED_REFUSE_RESUME");
    if(full(j.plugin_dir)!=fs::canonical(exe.parent_path()))throw Error("JOB_PLUGIN_DIR_MISMATCH");
    Options cfg;cfg.ghidra=j.ghidra;cfg.rizin=j.rizin;cfg.roots=j.roots;authorize(cfg);
    if(j.status=="TARGET_REACHED_PARITY_UNVERIFIED"){report(j,true);return 0;}
    if(j.status=="BLOCKED"||j.status=="BLOCKED_STAGNATION"||j.status=="RUNNING")throw Error("JOB_BLOCKED_OR_INTERRUPTED_INSPECT_EVIDENCE");
    auto persist=[&]{atomic_write(dir/"job.json",save_doc(j));};
    auto export_on_terminal=[&]{
        try{
            int result=bridge({"--stage","job-diagnostics","--job-dir",dir.u8string(),"--out-dir",diagnostic_dir.u8string()});
            if(result!=0)log.emit(2,"DIAGNOSTICS_EXPORT_FAILED","Diagnostic exporter returned a nonzero code");
        }catch(const std::exception&e){
            try{log.emit(2,"DIAGNOSTICS_EXPORT_FAILED",e.what());}catch(...){}
        }
    };
    j.status="RUNNING";persist();log.emit(1,"JOB_STARTED",std::string("Starting native recovery, cycle ")+std::to_string(j.attempts.size()+1));
    while(j.attempts.size()<static_cast<size_t>(j.max_cycles)){
        const int n=static_cast<int>(j.attempts.size())+1;
        auto out=dir/"sessions"/("cycle-"+(n<10?std::string("0"):std::string())+std::to_string(n));
        if(fs::exists(out))throw Error("IMMUTABLE_SESSION_OUTPUT_ALREADY_EXISTS");
        std::vector<std::string> cmd={"--stage","native-orchestrate","--rom",j.rom,"--out",out.u8string(),"--plugin-dir",j.plugin_dir,
            "--ghidra",j.ghidra,"--rizin",j.rizin,"--max-rounds",std::to_string(j.rounds),
            "--target-frames",std::to_string(j.target_frames),"--timeout",std::to_string(j.timeout),"--step-budget",std::to_string(j.step_budget)};
        for(auto& root:j.roots){cmd.push_back("--allow-tool-root");cmd.push_back(root);}
        if(!j.attempts.empty()){cmd.push_back("--resume-from");cmd.push_back(j.attempts.back().output);}
        else if(!j.import_history.empty()){
            auto prior=read_json(full(j.import_history)/"orchestration.json");
            if(getstr(prior,"schema")!="recompdev.native.orchestrator.v1"||getstr(prior,"source_sha256")!=j.sha)throw Error("INITIAL_HISTORY_SOURCE_IDENTITY_MISMATCH");
            cmd.push_back("--resume-from");cmd.push_back(j.import_history);
        }
        log.emit(0,"RECOVERY_START",std::string("Invoking bounded analyzer batch ")+std::to_string(n));
        try {
        int code=bridge(cmd); // One provider batch, exit 2 is its bounded recovery / fail-closed signal.
        auto doc=read_json(out/"orchestration.json");
        auto status=getstr(doc,"status");
        Attempt attempt;attempt.cycle=n;attempt.output=out.u8string();attempt.status=status;
        if(doc.get("reason").t==V::String)attempt.reason=getstr(doc,"reason");
        if(doc.get("rounds").t!=V::Array||doc.get("rounds").array().empty())throw Error("INVALID_ORCHESTRATION_ROUNDS");
        for(auto&r:doc.get("rounds").array()){
            if(r.get("frames").t==V::Int)attempt.frames=std::max(attempt.frames,as_int(r,"frames"));
            if(r.get("emitted").t==V::Int)attempt.emitted=std::max(attempt.emitted,as_int(r,"emitted"));
        }
        auto& stop=doc.get("rounds").array().back();
        if(stop.get("pc").t==V::Int&&stop.get("physical_offset").t==V::Int&&stop.get("mapper").t==V::Array){
            attempt.frontier=std::to_string(as_int(stop,"pc"))+":"+std::to_string(as_int(stop,"physical_offset"))+":";
            for(auto& bank:stop.get("mapper").array())attempt.frontier+=std::to_string(bank.integer())+",";
        }
        if(doc.get("source_sha256").t!=V::String||getstr(doc,"source_sha256")!=j.sha)throw Error("ORCHESTRATION_SOURCE_IDENTITY_MISMATCH");
        if(code!=0&&code!=2)throw Error("ANALYSIS_PROVIDER_PROCESS_FAILED");
        if(hash_rom(full(j.rom))!=j.sha)throw Error("ROM_CHANGED_DURING_ANALYSIS");
        int best_frames=0,best_emitted=0;
        for(auto& older:j.attempts){best_frames=std::max(best_frames,older.frames);best_emitted=std::max(best_emitted,older.emitted);}
        bool repeat_frontier=attempt.frontier.size()>0 && j.attempts.size()>=2 &&
            j.attempts.back().frontier==attempt.frontier && j.attempts[j.attempts.size()-2].frontier==attempt.frontier &&
            attempt.frames<=best_frames;
        j.attempts.push_back(attempt);
        log.emit(1,"RECOVERY_RESULT","Cycle "+std::to_string(n)+" frames="+std::to_string(attempt.frames)+" emitted="+std::to_string(attempt.emitted)+" status="+status);
        if(status=="FRAME_BUDGET_REACHED_PARITY_UNVERIFIED"){
            j.status="TARGET_REACHED_PARITY_UNVERIFIED";persist();log.emit(2,"PARITY_UNVERIFIED","Frame target reached; runtime/gameplay parity is NOT proven");export_on_terminal();report(j,true);return 0;
        }
        if(status!="MAX_RECOVERY_ROUNDS_REACHED"){
            j.status="BLOCKED";persist();log.emit(3,"PROVIDER_BLOCKED",attempt.reason.empty()?status:attempt.reason);export_on_terminal();report(j,true);return 2;
        }
        j.stagnant=(attempt.frames>best_frames||attempt.emitted>best_emitted)?0:j.stagnant+1;
        if(j.stagnant>=2||repeat_frontier){
            j.status="BLOCKED_STAGNATION";persist();
            log.emit(2,"STAGNATION",repeat_frontier?"Repeated identical execution frontier across three sessions":"Two sessions without improvement over the job's best frame or emitted coverage");
            export_on_terminal();report(j,true);return 2;
        }
        j.status="RECOVERY_PENDING";persist();
        if(j.attempts.size()<static_cast<size_t>(j.max_cycles))log.emit(1,"AUTO_RESUME","Reattesting previous evidence and scheduling the next bounded session");
        }catch(const std::exception& e){
            j.status="BLOCKED";persist();
            try {log.emit(3,"CYCLE_ABORTED",e.what());}catch(...){}
            export_on_terminal();
            throw;
        }
    }
    j.status="RECOVERY_LIMIT_REACHED";persist();
    log.emit(2,"CYCLE_LIMIT","Controller recovery cycle limit reached; resume only with higher --max-cycles");
    export_on_terminal();report(j,true);return 2;
}
} // anonymous namespace
int rd_native_job(const std::vector<std::string>& args,const fs::path&source,const fs::path&exe,
                  const std::function<int(const std::vector<std::string>&)>&bridge){
    try{
        if(args.empty())throw Error("JOB_COMMAND_MISSING");
        const bool diagnostics=args[0]=="diagnostics";
        std::vector<std::string> parsed=args;
        if(diagnostics){if(args.size()<2||args[1]!="export")throw Error("USE_DIAGNOSTICS_EXPORT");parsed.erase(parsed.begin()+1);}
        auto opt=parse(parsed);auto h=home();
        if(h==source||within(h,source))throw Error("JOB_HOME_CANNOT_BE_INSIDE_SOURCE");
        const auto& op=args.front();
        if(op=="configure"){
            if(!opt.job.empty()||!opt.rom.empty()||opt.have_cycles||!opt.import_history.empty()||(!opt.workspace.empty()&&!opt.evidence_root.empty()))throw Error("CONFIG_OPTION_NOT_SUPPORTED");
            if((opt.ghidra.empty()||opt.rizin.empty())&&fs::is_regular_file(h/"config.json")){
                auto previous=load_config(h);
                if(opt.ghidra.empty())opt.ghidra=previous.ghidra;
                if(opt.rizin.empty())opt.rizin=previous.rizin;
                if(opt.roots.empty())opt.roots=previous.roots;
                if(opt.workspace.empty()&&opt.evidence_root.empty()){opt.workspace=previous.workspace;opt.evidence_root=previous.evidence_root;}
            }
            if(opt.ghidra.empty()||opt.rizin.empty())throw Error("CONFIGURE_REQUIRES_GHIDRA_AND_RIZIN");
            opt.ghidra=full(opt.ghidra).u8string();opt.rizin=full(opt.rizin).u8string();
            if(opt.roots.empty()){opt.roots.push_back(fs::u8path(opt.ghidra).parent_path().u8string());opt.roots.push_back(fs::u8path(opt.rizin).parent_path().u8string());}
            for(auto&root:opt.roots)root=full(root).u8string();
            authorize(opt);
            if(!opt.workspace.empty()){
                auto value=fs::u8path(opt.workspace);
                if(!value.is_absolute())throw Error("WORKSPACE_MUST_BE_ABSOLUTE");
                auto canon=fs::weakly_canonical(value);
                if(canon==canon.root_path()||within(canon,source)||within(canon,h)||within(h,canon))throw Error("WORKSPACE_LOCATION_UNSAFE");
                opt.workspace=canon.u8string();
            }
            if(!opt.evidence_root.empty()){
                auto value=fs::u8path(opt.evidence_root);
                if(!value.is_absolute())throw Error("EVIDENCE_ROOT_MUST_BE_ABSOLUTE");
                auto canon=fs::weakly_canonical(value);
                if(canon==canon.root_path()||within(canon,source)||within(canon,h)||within(h,canon))throw Error("EVIDENCE_ROOT_LOCATION_UNSAFE");
                opt.evidence_root=canon.u8string();
                // A new explicit root supersedes a previously configured legacy workspace.
                opt.workspace.clear();
            }
            atomic_write(h/"config.json",config_json(opt));
            std::cout<<"RECOMPDEV_CONFIGURATION=VERIFIED\nRECOMPDEV_CONFIG_PATH="<<(h/"config.json").string()<<"\n";
            std::cout<<"RECOMPDEV_EVIDENCE_ROOT="<<evidence_root(h,source).string()<<"\n";
            std::cout<<"RECOMPDEV_WORKSPACE="<<workspace(h,source).string()<<"\n";return 0;
        }
        if(op=="run"){
            if(opt.rom.empty()||!opt.job.empty())throw Error("RUN_REQUIRES_ROM_ONLY");
            if(!opt.ghidra.empty()||!opt.rizin.empty()||!opt.roots.empty()||!opt.workspace.empty()||!opt.evidence_root.empty())throw Error("USE_CONFIGURE_FOR_TOOL_SETTINGS");
            auto cfg=load_config(h);authorize(cfg);auto rom=full(opt.rom);
            auto jobs=workspace(h,source)/"jobs";
            auto sha=hash_rom(rom);
            auto id="job-"+compact_time()+"-"+sha.substr(0,8)+"-";
#ifdef _WIN32
            id+=std::to_string(GetCurrentProcessId());
#else
            id+=std::to_string(getpid());
#endif
            auto base_id=id;fs::path dir;bool created=false;
            for(int serial=0;serial<1000;++serial){
                id=base_id+"-"+std::to_string(serial);dir=jobs/id;
                if(fs::create_directories(dir)){created=true;break;}
            }
            if(!created)throw Error("JOB_ID_COLLISION_LIMIT");
            fs::create_directories(dir/"sessions");
            Job j;j.id=id;j.rom=rom.u8string();j.sha=sha;j.ghidra=cfg.ghidra;j.rizin=cfg.rizin;j.roots=cfg.roots;
            if(!opt.import_history.empty()){
                auto initial=full(opt.import_history);
                if(!fs::is_directory(initial))throw Error("INITIAL_HISTORY_NOT_DIRECTORY");
                auto prior=read_json(initial/"orchestration.json");
                if(getstr(prior,"schema")!="recompdev.native.orchestrator.v1"||getstr(prior,"source_sha256")!=sha)throw Error("INITIAL_HISTORY_SOURCE_IDENTITY_MISMATCH");
                j.import_history=initial.u8string();
            }
            j.plugin_dir=opt.plugin_dir.empty()?fs::canonical(exe.parent_path()).u8string():full(opt.plugin_dir).u8string();
            j.max_cycles=opt.max_cycles;j.rounds=opt.rounds;j.target_frames=opt.target_frames;j.timeout=opt.timeout;j.step_budget=opt.step_budget;
            atomic_write(dir/"job.json",save_doc(j));atomic_write(h/"last-job.txt",id+"\n");
            return execute(j,jobs,workspace(h,source)/"diagnostics",exe,bridge,opt.logging);
        }
        if(op=="resume"||op=="status"||op=="inspect"||diagnostics){
            if(!opt.rom.empty()||!opt.ghidra.empty()||!opt.rizin.empty()||!opt.roots.empty()||!opt.plugin_dir.empty()||!opt.import_history.empty()||!opt.workspace.empty()||!opt.evidence_root.empty()||opt.rounds!=4||opt.target_frames!=1800||opt.timeout!=600||opt.step_budget!=20000000)throw Error("INVALID_JOB_COMMAND_OPTIONS");
            auto id=opt.job.empty()?last_id(h):opt.job;
            auto jobs=locate_jobs(workspace(h,source),h,id);
            Job j=load_job(jobs,id);
            if(diagnostics){
                if(opt.have_cycles)throw Error("INVALID_DIAGNOSTICS_OPTION");
                int rc=bridge({"--stage","job-diagnostics","--job-dir",(jobs/id).u8string(),"--out-dir",(workspace(h,source)/"diagnostics").u8string()});
                if(rc!=0)throw Error("DIAGNOSTICS_EXPORT_FAILED");
                return 0;
            }
            if(op!="resume"){if(opt.have_cycles)throw Error("INVALID_STATUS_OPTION");report(j,op=="inspect");return 0;}
            if(opt.have_cycles){if(opt.max_cycles<int(j.attempts.size())||opt.max_cycles<j.max_cycles)throw Error("CANNOT_REDUCE_JOB_CYCLE_LIMIT");j.max_cycles=opt.max_cycles;}
            if(j.attempts.size()>=static_cast<size_t>(j.max_cycles))throw Error("INCREASE_MAX_CYCLES_TO_RESUME");
            return execute(j,jobs,workspace(h,source)/"diagnostics",exe,bridge,opt.logging);
        }
        throw Error("UNKNOWN_JOB_COMMAND_"+op);
    }catch(const std::exception&e){std::cerr<<"RECOMPDEV_JOB_ERROR="<<e.what()<<"\n";return 2;}
}
