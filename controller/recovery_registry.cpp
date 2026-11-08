#include "recovery_registry.hpp"
#include "rd_sha256.hpp"
#include "rd_tiny_json.hpp"
#include <algorithm>
#include <cctype>
#include <fstream>
#include <stdexcept>
#include <string>
#include <vector>
namespace fs=std::filesystem;
namespace {
constexpr std::size_t kMaxReport=8*1024*1024;
constexpr std::size_t kMaxIndex=8192;
struct RegistryError:std::runtime_error{using std::runtime_error::runtime_error;};
void validate_sha(const std::string& sha){
    if(sha.size()!=64||!std::all_of(sha.begin(),sha.end(),[](unsigned char c){return (c>='0'&&c<='9')||(c>='a'&&c<='f');}))
        throw RegistryError("REGISTRY_ROM_SHA_INVALID");
}
bool within(const fs::path& p,const fs::path& root){
    auto i=p.begin(),j=root.begin();for(;j!=root.end();++j,++i)if(i==p.end()||*i!=*j)return false;return true;
}
fs::path safe_root(const fs::path& root){
    const auto p=fs::weakly_canonical(root);
    if(!p.is_absolute()||p==p.root_path())throw RegistryError("REGISTRY_ROOT_UNSAFE");
    return p;
}
fs::path safe_path(const fs::path& root,const fs::path& candidate){
    if(!candidate.is_absolute())throw RegistryError("REGISTRY_PATH_NOT_ABSOLUTE");
    const auto canon=fs::canonical(candidate);
    if(!within(canon,root)||canon==root)throw RegistryError("REGISTRY_PATH_ESCAPE");
    auto walk=root;auto relative=candidate.lexically_normal().lexically_relative(root);
    if(relative.empty()||relative.is_absolute())throw RegistryError("REGISTRY_PATH_ESCAPE");
    for(const auto& part:relative){
        if(part==".."||part==".")throw RegistryError("REGISTRY_PATH_ESCAPE");
        walk/=part;
        std::error_code ec;if(fs::is_symlink(walk,ec))throw RegistryError("REGISTRY_PATH_SYMLINK");
    }
    return canon;
}
std::string bytes(const fs::path& path,std::size_t limit=kMaxReport){
    std::error_code ec;
    if(fs::is_symlink(path,ec)||!fs::is_regular_file(path,ec)||fs::file_size(path,ec)>limit||ec)
        throw RegistryError("REGISTRY_FILE_INVALID");
    std::ifstream in(path,std::ios::binary);if(!in)throw RegistryError("REGISTRY_FILE_UNREADABLE");
    return std::string(std::istreambuf_iterator<char>(in),{});
}
std::string sha(const std::string& content){return rdhash::sha256(reinterpret_cast<const uint8_t*>(content.data()),content.size());}
rdjson::V parse(const std::string& content){return rdjson::Reader(content).parse();}
int bounded(const rdjson::V& v,const std::string& field){
    auto n=v.get(field).integer();if(n<0||n>1000000000)throw RegistryError("REGISTRY_COUNT_INVALID");return static_cast<int>(n);
}
std::string name(const rdjson::V&v,const std::string&field){return v.get(field).string();}
struct Attested{rdregistry::Hit hit;std::string hash;};
Attested inspect(const fs::path& root,const fs::path& session,const std::string& rom_sha){
    const auto path=safe_path(root,session);auto raw=bytes(path/"orchestration.json");auto doc=parse(raw);
    if(name(doc,"schema")!="recompdev.native.orchestrator.v1"||name(doc,"source_sha256")!=rom_sha)
        throw RegistryError("REGISTRY_ORCHESTRATION_SOURCE_MISMATCH");
    const auto status=name(doc,"status");
    if(status!="MAX_RECOVERY_ROUNDS_REACHED"&&status!="FRAME_BUDGET_REACHED_PARITY_UNVERIFIED")
        throw RegistryError("REGISTRY_ORCHESTRATION_STATUS_INVALID");
    const auto& rounds=doc.get("rounds").array();
    if(rounds.empty()||rounds.size()>8)throw RegistryError("REGISTRY_ORCHESTRATION_ROUNDS_INVALID");
    int emitted=0,frames=0;
    for(const auto& round:rounds){
        emitted=std::max(emitted,bounded(round,"emitted"));frames=std::max(frames,bounded(round,"frames"));
    }
    if(emitted<1)throw RegistryError("REGISTRY_NO_TRANSLATED_INSTRUCTIONS");
    return {{path,emitted,frames},sha(raw)};
}
bool version(const std::string& s){
    if(s.size()<5||s[0]!='v')return false;int dots=0;
    for(std::size_t i=1;i<s.size();++i){
        if(s[i]=='.'){++dots;continue;}
        if(!std::isdigit(static_cast<unsigned char>(s[i])))return false;
    }
    return dots>=2&&dots<=3;
}
void select(std::optional<rdregistry::Hit>&best,const rdregistry::Hit&hit){
    if(!best||hit.emitted>best->emitted||(hit.emitted==best->emitted&&hit.frames>best->frames)||
      (hit.emitted==best->emitted&&hit.frames==best->frames&&hit.session.u8string()>best->session.u8string()))best=hit;
}
std::vector<fs::path> sorted_children(const fs::path& p,std::size_t limit){
    std::vector<fs::path> items;std::error_code ec;
    if(!fs::is_directory(p,ec))return items;
    for(const auto& item:fs::directory_iterator(p)){
        if(items.size()>=limit)throw RegistryError("REGISTRY_SCAN_LIMIT");
        if(item.is_symlink(ec))throw RegistryError("REGISTRY_SCAN_SYMLINK");
        items.push_back(item.path());
    }
    std::sort(items.begin(),items.end());return items;
}
} // namespace
namespace rdregistry {
void remember(const fs::path& evidence_root,const std::string& rom_sha256,
              const fs::path& session,const std::string& job_id,int cycle){
    validate_sha(rom_sha256);
    if(job_id.size()>100||job_id.rfind("job-",0)!=0||
      !std::all_of(job_id.begin(),job_id.end(),[](unsigned char c){return std::isalnum(c)||c=='-'||c=='_';})||cycle<1||cycle>128)
        throw RegistryError("REGISTRY_ID_INVALID");
    auto root=safe_root(evidence_root);auto candidate=inspect(root,session,rom_sha256);
    auto relative=candidate.hit.session.lexically_relative(root).generic_u8string();
    if(relative.empty()||relative.rfind("..",0)==0)throw RegistryError("REGISTRY_PATH_ESCAPE");
    auto dir=root/"translation-registry"/"v1"/rom_sha256;
    // Reject a redirected registry parent BEFORE attempting any writes.
    for(auto p=root/"translation-registry"; p!=dir; p=(p==root/"translation-registry"?p/"v1":p/rom_sha256)){
        if(fs::is_symlink(p))throw RegistryError("REGISTRY_DIRECTORY_SYMLINK");
    }
    if(fs::is_symlink(dir))throw RegistryError("REGISTRY_DIRECTORY_SYMLINK");
    fs::create_directories(dir);
    if(safe_path(root,dir)!=dir)throw RegistryError("REGISTRY_DIRECTORY_CHANGED");
    const auto path=dir/(job_id+"-cycle-"+std::to_string(cycle)+".json");
    const std::string contents="{\"schema\":\"recompdev.recovery.registry.v1\",\"rom_sha256\":"+
       rdjson::escape(rom_sha256)+",\"session\":"+rdjson::escape(relative)+
       ",\"orchestration_sha256\":"+rdjson::escape(candidate.hash)+
       ",\"emitted\":"+std::to_string(candidate.hit.emitted)+",\"frames\":"+std::to_string(candidate.hit.frames)+"}\n";
    if(fs::exists(path)){
        if(bytes(path,4096)!=contents)throw RegistryError("REGISTRY_IMMUTABLE_ENTRY_MISMATCH");
        return;
    }
    auto pending=path;pending+=".pending";
    if(fs::exists(pending))throw RegistryError("REGISTRY_PENDING_COLLISION");
    {std::ofstream out(pending,std::ios::binary|std::ios::trunc);
     if(!out)throw RegistryError("REGISTRY_WRITE_FAILED");out<<contents;out.flush();if(!out)throw RegistryError("REGISTRY_WRITE_FAILED");}
    std::error_code ec;fs::rename(pending,path,ec);
    if(ec){fs::remove(pending);throw RegistryError("REGISTRY_COMMIT_FAILED");}
}
std::optional<Hit> find(const fs::path& evidence_root,const std::string& rom_sha256){
    validate_sha(rom_sha256);auto root=safe_root(evidence_root);
    std::optional<Hit> best;
    auto records=root/"translation-registry"/"v1"/rom_sha256;
    if(fs::exists(records)){
      if(fs::is_symlink(records)||!fs::is_directory(records))throw RegistryError("REGISTRY_INDEX_UNSAFE");
      for(const auto& p:sorted_children(records,kMaxIndex)){
        if(p.extension()!=".json")throw RegistryError("REGISTRY_UNKNOWN_INDEX_FILE");
        const auto doc=parse(bytes(p,4096));
        if(name(doc,"schema")!="recompdev.recovery.registry.v1"||name(doc,"rom_sha256")!=rom_sha256)
            throw RegistryError("REGISTRY_INDEX_SOURCE_MISMATCH");
        const auto rel=fs::u8path(name(doc,"session"));
        if(rel.is_absolute()||rel.empty())throw RegistryError("REGISTRY_INDEX_PATH_INVALID");
        const auto att=inspect(root,root/rel,rom_sha256);
        if(att.hash!=name(doc,"orchestration_sha256")||att.hit.emitted!=bounded(doc,"emitted")||att.hit.frames!=bounded(doc,"frames"))
            throw RegistryError("REGISTRY_INDEX_ATTESTATION_FAILED");
        select(best,att.hit);
      }
      if(best)return best;
    }
    // First-use compatibility bridge: bounded, read-only discovery of older
    // installed evidence sessions. No reliance on manually supplied log files.
    std::size_t checked=0;
    for(const auto& folder:sorted_children(root,128)){
        if(!version(folder.filename().u8string())||!fs::is_directory(folder))continue;
        for(const auto& job:sorted_children(folder/"jobs",4096)){
            if(++checked>8192)throw RegistryError("REGISTRY_LEGACY_SCAN_LIMIT");
            if(job.filename().u8string().rfind("job-",0)!=0||!fs::is_directory(job))continue;
            const auto state=job/"job.json";
            if(!fs::is_regular_file(state))continue;
            const auto j=parse(bytes(state,2*1024*1024));
            if(j.get("schema").t!=rdjson::V::String||j.get("rom_sha256").t!=rdjson::V::String||
               name(j,"schema")!="recompdev.controller.job.v1"||name(j,"rom_sha256")!=rom_sha256)continue;
            for(const auto& session:sorted_children(job/"sessions",128)){
                if(session.filename().u8string().rfind("cycle-",0)!=0||!fs::is_directory(session)||!fs::is_regular_file(session/"orchestration.json"))continue;
                // Some historical attempts were rightly rejected by their
                // provider. They are *not* translation reuse candidates.
                const auto report=parse(bytes(session/"orchestration.json"));
                if(report.get("schema").t!=rdjson::V::String||report.get("status").t!=rdjson::V::String||
                   report.get("source_sha256").t!=rdjson::V::String||
                   name(report,"schema")!="recompdev.native.orchestrator.v1"||
                   name(report,"source_sha256")!=rom_sha256)continue;
                const auto status=name(report,"status");
                if(status!="MAX_RECOVERY_ROUNDS_REACHED"&&status!="FRAME_BUDGET_REACHED_PARITY_UNVERIFIED")continue;
                auto hit=inspect(root,session,rom_sha256);
                select(best,hit.hit);
            }
        }
    }
    return best;
}
}
