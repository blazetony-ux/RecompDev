#include "artifact_store.hpp"
#include "rd_sha256.hpp"
#include "rd_tiny_json.hpp"
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cctype>
#include <fstream>
#include <limits>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>
namespace fs=std::filesystem;
namespace {
using rdjson::V;
struct StoreError:std::runtime_error{using std::runtime_error::runtime_error;};
constexpr std::size_t kMaxObject=128u*1024u*1024u;
constexpr std::size_t kMaxCapsule=256u*1024u*1024u;
constexpr std::size_t kMaxManifest=256u*1024u;
constexpr std::size_t kMaxFiles=180;
std::string sha(const std::string& s){return rdhash::sha256(reinterpret_cast<const uint8_t*>(s.data()),s.size());}
void hexsha(const std::string& s){
 if(s.size()!=64||!std::all_of(s.begin(),s.end(),[](unsigned char c){return std::isdigit(c)||(c>='a'&&c<='f');}))
     throw StoreError("ARTIFACT_INVALID_SHA256");
}
void identifier(const std::string& s){
 if(s.empty()||s.size()>100||!std::all_of(s.begin(),s.end(),[](unsigned char c){
   return std::isalnum(c)||c=='_'||c=='-'||c=='.'||c=='+'||c==':';}))throw StoreError("ARTIFACT_INVALID_IDENTIFIER");
}
fs::path rootpath(const fs::path& p){
 const auto path=fs::absolute(p).lexically_normal();
 if(path==path.root_path()||path.empty())throw StoreError("ARTIFACT_UNSAFE_ROOT");
 std::error_code ec;
 // Reject symbolic links anywhere in a pre-existing root hierarchy.
 fs::path walk;
 for(const auto& bit:path){walk/=bit;if(fs::is_symlink(walk,ec))throw StoreError("ARTIFACT_SYMLINK_ROOT");}
 return path;
}
void safepath(const fs::path& p,const fs::path& base){
 if(p.is_absolute())throw StoreError("ARTIFACT_ABSOLUTE_ENTRY");
 if(p.empty())throw StoreError("ARTIFACT_EMPTY_ENTRY");
 for(const auto& bit:p)if(bit=="."||bit==".."||bit.empty())throw StoreError("ARTIFACT_TRAVERSAL");
 auto walk=base;
 for(const auto& bit:p){walk/=bit;if(fs::is_symlink(walk))throw StoreError("ARTIFACT_ENTRY_SYMLINK");}
}
std::string read(const fs::path& p,std::size_t cap){
 std::error_code ec;
 if(fs::is_symlink(p,ec)||!fs::is_regular_file(p,ec))throw StoreError("ARTIFACT_FILE_MISSING_OR_UNSAFE");
 const auto n=fs::file_size(p,ec);
 if(ec||n>cap)throw StoreError("ARTIFACT_FILE_TOO_LARGE");
 std::ifstream in(p,std::ios::binary);if(!in)throw StoreError("ARTIFACT_UNREADABLE");
 std::string data(static_cast<size_t>(n),'\0');
 if(n&&!in.read(&data[0],static_cast<std::streamsize>(n)))throw StoreError("ARTIFACT_SHORT_READ");
 return data;
}
void immutable(const fs::path& path,const std::string& data){
 if(fs::exists(path)){
   if(read(path,data.size())!=data)throw StoreError("ARTIFACT_IMMUTABLE_COLLISION");
   return;
 }
 fs::create_directories(path.parent_path());
 static std::atomic<unsigned> seq{0};
 // Use a short sibling name for the atomic write. Appending the nonce to
 // a 64-character content-addressed basename pushed the full path beyond
 // Win32 MAX_PATH in capsules/<64-byte-hash>/<64-byte-hash>.json, even though
 // the committed path itself was valid. Keeping the temporary name short and
 // in the same directory preserves the atomic rename and Windows portability.
 const auto pending=path.parent_path()/(".rd-pending-"+
     std::to_string(std::chrono::steady_clock::now().time_since_epoch().count())+
     "-"+std::to_string(++seq));
 {std::ofstream out(pending,std::ios::binary|std::ios::trunc);
   if(!out)throw StoreError("ARTIFACT_WRITE_FAILED");
   out.write(data.data(),static_cast<std::streamsize>(data.size()));out.flush();
   if(!out){fs::remove(pending);throw StoreError("ARTIFACT_WRITE_FAILED");}}
 std::error_code ec;fs::rename(pending,path,ec);
 if(ec){fs::remove(pending);if(!fs::exists(path)||read(path,data.size())!=data)throw StoreError("ARTIFACT_COMMIT_FAILED");}
}
std::string str(const V& v,const std::string& key){return v.get(key).string();}
int cnt(const V& v,const std::string& key){auto value=v.get(key).integer();if(value<0||value>1000000000)throw StoreError("ARTIFACT_INVALID_COUNTER");return static_cast<int>(value);}
std::string quote(const std::string& s){return rdjson::escape(s);}
// Stable normalisation of an audited orchestration document. This is not
// execution provenance rewriting: the original report is hashed separately;
// only source-verified local recovery-seed locators become relative entries.
std::string encode(const V& v){
 switch(v.t){
  case V::Null:return "null";
  case V::Bool:return v.n?"true":"false";
  case V::Int:return std::to_string(v.n);
  case V::String:return quote(v.s);
  case V::Array:{std::string out="[";for(const auto& entry:v.a){if(out.size()>1)out+=",";out+=encode(entry);}return out+"]";}
  case V::Object:{std::string out="{";for(const auto& entry:v.o){if(out.size()>1)out+=",";out+=quote(entry.first)+":"+encode(entry.second);}return out+"}";}
 }
 throw StoreError("CAPSULE_BAD_JSON_VALUE");
}
bool equivalent(const V& a,const V& b){
 if(a.t!=b.t)return false;
 switch(a.t){
  case V::Null:return true;
  case V::Bool:case V::Int:return a.n==b.n;
  case V::String:return a.s==b.s;
  case V::Array:
   if(a.a.size()!=b.a.size())return false;
   for(std::size_t i=0;i<a.a.size();++i)if(!equivalent(a.a[i],b.a[i]))return false;
   return true;
  case V::Object:
   if(a.o.size()!=b.o.size())return false;
   for(const auto& item:a.o){auto it=b.o.find(item.first);if(it==b.o.end()||!equivalent(item.second,it->second))return false;}
   return true;
 }
 return false;
}
std::string blob_document(const rdartifact::Blob& b){
 return "{\"schema\":\"recompdev.artifact.blob.v1\",\"digest\":"+quote(b.digest)+
  ",\"kind\":"+quote(b.kind)+",\"producer\":"+quote(b.producer)+",\"target\":"+quote(b.target)+
  ",\"abi\":"+quote(b.abi)+",\"bytes\":"+std::to_string(b.bytes)+"}\n";
}
fs::path object_path(const fs::path& root,const std::string& digest){hexsha(digest);return root/"objects"/digest.substr(0,2)/digest;}
std::string safe_source(const fs::path& base,const std::string& rel){
 auto sub=fs::u8path(rel);safepath(sub,base);
 return read(base/sub,kMaxObject);
}
void add_if(std::map<std::string,std::string>& contents,const fs::path& session,const std::string& rel,bool required){
 auto target=session/fs::u8path(rel);
 if(!fs::exists(target)){
   if(required)throw StoreError("CAPSULE_REQUIRED_INPUT_MISSING: "+rel);
   return;
 }
 contents.emplace(rel,safe_source(session,rel));
}
std::string compat(const V& report,const std::string& name){
 const auto& analysis=report.get("analysis");
 if(analysis.t!=V::Object||analysis.get(name).t!=V::String)throw StoreError("CAPSULE_MISSING_PROVIDER_ID");
 auto s=str(analysis,name);identifier(s);return s;
}
struct Entry{std::string rel,digest;std::size_t bytes;};
struct Verified {rdartifact::Capsule info;std::vector<Entry> files;};
Verified verify_manifest(const fs::path& root,const fs::path& manifest){
 auto raw=read(manifest,kMaxManifest);auto v=rdjson::Reader(raw).parse();
 if(str(v,"schema")!="recompdev.artifact.capsule.v1")throw StoreError("CAPSULE_SCHEMA_MISMATCH");
 auto digest=sha(raw);
 if(manifest.stem().string()!=digest)throw StoreError("CAPSULE_MANIFEST_HASH_MISMATCH");
 auto source=str(v,"source_sha256");hexsha(source);
 if(manifest.parent_path().filename()!=source)throw StoreError("CAPSULE_SOURCE_INDEX_MISMATCH");
 auto arch=str(v,"architecture"),platform=str(v,"platform");identifier(arch);identifier(platform);
 Verified result;result.info.digest=digest;result.info.architecture=arch;result.info.platform=platform;
 result.info.emitted=cnt(v,"emitted");result.info.frames=cnt(v,"frames");
 if(result.info.emitted<1)throw StoreError("CAPSULE_EMPTY_COVERAGE");
 const auto& file_list=v.get("files").array();
 if(file_list.empty()||file_list.size()>kMaxFiles)throw StoreError("CAPSULE_FILE_COUNT_INVALID");
 std::size_t total=0;std::string last;
 for(const auto& e:file_list){
  auto rel=str(e,"path"),hash=str(e,"sha256");auto size=e.get("bytes").integer();
  safepath(fs::u8path(rel),root);hexsha(hash);
  if(!last.empty()&&rel<=last)throw StoreError("CAPSULE_DUPLICATE_OR_UNSORTED_ENTRY");
  last=rel;
  if(size<0||static_cast<std::uint64_t>(size)>kMaxObject||total>kMaxCapsule-static_cast<std::size_t>(size))throw StoreError("CAPSULE_SIZE_LIMIT");
  total+=static_cast<std::size_t>(size);
  auto content=read(object_path(root,hash),kMaxObject);
  if(content.size()!=static_cast<std::size_t>(size)||sha(content)!=hash)throw StoreError("CAPSULE_OBJECT_HASH_MISMATCH");
  result.files.push_back({rel,hash,static_cast<std::size_t>(size)});
 }
 if(std::none_of(result.files.begin(),result.files.end(),[](const Entry& item){return item.rel=="orchestration.json";}))throw StoreError("CAPSULE_ORCHESTRATION_REQUIRED");
 return result;
}
fs::path materialize(const fs::path& root,const Verified& v){
 const auto dest=root/"materialized"/v.info.digest;
 // Each file is verified on every lookup, including previously materialised files.
 for(const auto& e:v.files){
  auto relative=fs::u8path(e.rel);safepath(relative,dest);
  auto path=dest/relative;
  auto original=read(object_path(root,e.digest),kMaxObject);
  if(sha(original)!=e.digest)throw StoreError("CAPSULE_OBJECT_CHANGED");
  if(fs::exists(path)){
   if(read(path,kMaxObject)!=original)throw StoreError("CAPSULE_MATERIALIZED_TAMPERED");
  }else immutable(path,original);
 }
 return dest;
}
}
namespace rdartifact {
Blob put(const fs::path& root,const std::string& kind,const std::string& producer,
         const std::string& target,const std::string& abi,const std::string& data){
 identifier(kind);identifier(producer);identifier(target);identifier(abi);
 if(data.empty()||data.size()>kMaxObject)throw StoreError("ARTIFACT_PAYLOAD_SIZE_INVALID");
 auto base=rootpath(root);auto digest=sha(data);
 immutable(object_path(base,digest),data);
 Blob b{digest,kind,producer,target,abi,static_cast<std::uint64_t>(data.size())};
 immutable(base/"blobs"/(sha(blob_document(b))+".json"),blob_document(b));
 return b;
}
std::string get(const fs::path& root,const Blob& blob){
 auto base=rootpath(root);hexsha(blob.digest);
 identifier(blob.kind);identifier(blob.producer);identifier(blob.target);identifier(blob.abi);
 if(read(base/"blobs"/(sha(blob_document(blob))+".json"),kMaxManifest)!=blob_document(blob))throw StoreError("ARTIFACT_DESCRIPTOR_CHANGED");
 auto raw=read(object_path(base,blob.digest),kMaxObject);
 if(raw.size()!=blob.bytes||sha(raw)!=blob.digest)throw StoreError("ARTIFACT_HASH_MISMATCH");
 return raw;
}
std::optional<std::string> promote(const fs::path& root,const fs::path& session,const std::string& source_sha256){
 hexsha(source_sha256);auto base=rootpath(root);
 if(!fs::is_directory(session)||fs::is_symlink(session))throw StoreError("CAPSULE_INVALID_SOURCE_ROOT");
 const auto source=fs::canonical(session);
 const auto raw=read(source/"orchestration.json",8*1024*1024);
 auto report=rdjson::Reader(raw).parse();
 if(str(report,"schema")!="recompdev.native.orchestrator.v1"||str(report,"source_sha256")!=source_sha256)
   throw StoreError("CAPSULE_SOURCE_IDENTITY_MISMATCH");
 if(str(report,"status")!="MAX_RECOVERY_ROUNDS_REACHED"&&str(report,"status")!="FRAME_BUDGET_REACHED_PARITY_UNVERIFIED")
   throw StoreError("CAPSULE_SOURCE_STATUS_INVALID");
 // Historical synthetic/partial reports are not promotion candidates. An
 // incomplete capsule is NEVER represented as a successful cache hit.
 if(report.get("analysis").t!=V::Object||report.get("analysis").get("cache_contract").t!=V::Object)
   return std::nullopt;
 const auto& analysis=report.get("analysis");
 if(str(analysis,"schema")!="recompdev.analysis.providers.v1")throw StoreError("CAPSULE_ANALYSIS_SCHEMA_INVALID");
 const auto& contract=analysis.get("cache_contract");
 if(str(contract,"source_sha256")!=source_sha256)throw StoreError("CAPSULE_ANALYSIS_SOURCE_INVALID");
 auto arch=compat(report,"architecture"),platform=compat(report,"platform");
 std::map<std::string,std::string> files;
 add_if(files,source,"orchestration.json",true);
 add_if(files,source,"analysis/provider-manifest.json",true);
 add_if(files,source,"analysis/ghidra-functions.json",true);
 // Reject tampered analysis before admitting it into persistent retention.
 const auto provider_manifest=rdjson::Reader(files.at("analysis/provider-manifest.json")).parse();
 if(!equivalent(provider_manifest,analysis))throw StoreError("CAPSULE_PROVIDER_MANIFEST_CHANGED");
 if(sha(files.at("analysis/ghidra-functions.json"))!=str(analysis,"ghidra_export_sha256"))
   throw StoreError("CAPSULE_GHIDRA_EXPORT_HASH_MISMATCH");
 const auto tools=contract.get("tools");
 if(tools.t!=V::Object)throw StoreError("CAPSULE_TOOLS_INVALID");
 if(tools.get("rizin").t==V::Object){
   add_if(files,source,"analysis/rizin/rizin-aflj.json",true);
   add_if(files,source,"analysis/reconciled-functions.json",true);
   if(sha(files.at("analysis/reconciled-functions.json"))!=str(analysis,"reconciliation_sha256")||
      sha(files.at("analysis/rizin/rizin-aflj.json"))!=str(analysis.get("rizin_execution"),"export_sha256"))
      throw StoreError("CAPSULE_RECONCILIATION_HASH_MISMATCH");
 }
 const auto& rounds=report.get("rounds").array();
 if(rounds.empty()||rounds.size()>8)throw StoreError("CAPSULE_ROUNDS_INVALID");
 int emitted=0,frames=0;
 for(std::size_t i=0;i<rounds.size();++i){
   emitted=std::max(emitted,cnt(rounds[i],"emitted"));
   frames=std::max(frames,cnt(rounds[i],"frames"));
   std::string n=std::to_string(i+1);if(i<9)n="0"+n;
   const std::string seed="round-"+n+"-observed-stop.json";
   add_if(files,source,seed,rounds[i].get("recovery_seed").t==V::String);
   if(rounds[i].get("recovery_seed").t==V::String){
       // Keep a bounded, source-local relative locator instead of the old
       // absolute evidence path. This is what makes Python provider replay
       // truly independent of deleted or relocated diagnostic folders.
       report.o["rounds"].a[i].o["recovery_seed"].s=seed;
   }
   if(rounds[i].get("ghidra_focused_region").t==V::Object){
     add_if(files,source,"round-"+n+"-ghidra-recovery/source-verified-bank-functions.json",true);
     add_if(files,source,"round-"+n+"-ghidra-recovery/recovery-audit.json",true);
   }
   // Actual generated translation sources and native code provenance are kept
   // as immutable artifacts for future compiler/ABI-compatible reuse. They are
   // NOT currently dispatched directly; current native translator re-attests.
   add_if(files,source,"round-"+n+"/translation-manifest.json",false);
   add_if(files,source,"round-"+n+"/translated.cpp",false);
   add_if(files,source,"round-"+n+"/rd_game_pcode.cpp",false);
 }
 auto inherited=source/"imported-history";
 if(fs::exists(inherited)){
   if(fs::is_symlink(inherited)||!fs::is_directory(inherited))throw StoreError("CAPSULE_INHERITED_UNSAFE");
   add_if(files,source,"imported-history/history-import.json",true);
   for(const auto& p:fs::directory_iterator(inherited)){
     if(p.is_symlink()||!p.is_regular_file())throw StoreError("CAPSULE_INHERITED_FILE_UNSAFE");
     auto leaf=p.path().filename().string();
     if(leaf=="history-import.json")continue;
     // Closed allowlist: source-verified stop and bank-overlay JSON only.
     if((leaf.rfind("stop-",0)!=0&&leaf.rfind("bank-",0)!=0)||p.path().extension()!=".json")
       throw StoreError("CAPSULE_UNEXPECTED_INHERITED_INPUT");
     add_if(files,source,"imported-history/"+leaf,true);
   }
 }
 files["orchestration.json"]=encode(report)+"\n";
 if(emitted<1||files.size()>kMaxFiles)return std::nullopt;
 std::size_t total=0;std::vector<Entry> entries;
 for(const auto& item:files){
   if(item.second.empty()||item.second.size()>kMaxObject||total>kMaxCapsule-item.second.size())throw StoreError("CAPSULE_LIMIT_EXCEEDED");
   total+=item.second.size();
   auto digest=sha(item.second);
   immutable(object_path(base,digest),item.second);
   entries.push_back({item.first,digest,item.second.size()});
 }
 std::string manifest="{\"schema\":\"recompdev.artifact.capsule.v1\",\"source_sha256\":"+quote(source_sha256)+
  ",\"architecture\":"+quote(arch)+",\"platform\":"+quote(platform)+
  ",\"emitted\":"+std::to_string(emitted)+",\"frames\":"+std::to_string(frames)+",\"files\":[";
 for(std::size_t i=0;i<entries.size();++i){
  if(i)manifest+=",";
  manifest+="{\"path\":"+quote(entries[i].rel)+",\"sha256\":"+quote(entries[i].digest)+",\"bytes\":"+std::to_string(entries[i].bytes)+"}";
 }
 manifest+="]}\n";
 if(manifest.size()>kMaxManifest)throw StoreError("CAPSULE_MANIFEST_TOO_LARGE");
 const auto digest=sha(manifest);
 immutable(base/"capsules"/source_sha256/(digest+".json"),manifest);
 return digest;
}
std::optional<Capsule> best(const fs::path& root,const std::string& source_sha256){
 hexsha(source_sha256);auto base=rootpath(root);
 auto dir=base/"capsules"/source_sha256;
 if(!fs::exists(dir))return std::nullopt;
 if(fs::is_symlink(dir)||!fs::is_directory(dir))throw StoreError("CAPSULE_INDEX_UNSAFE");
 std::vector<fs::path> records;
 for(const auto& entry:fs::directory_iterator(dir)){
   if(entry.is_symlink()||!entry.is_regular_file()||entry.path().extension()!=".json")throw StoreError("CAPSULE_INDEX_ENTRY_INVALID");
   records.push_back(entry.path());
   if(records.size()>4096)throw StoreError("CAPSULE_INDEX_LIMIT");
 }
 std::sort(records.begin(),records.end());
 std::optional<Verified> winner;
 for(const auto& record:records){
   auto v=verify_manifest(base,record);
   if(!winner||v.info.emitted>winner->info.emitted||
       (v.info.emitted==winner->info.emitted&&v.info.frames>winner->info.frames)||
       (v.info.emitted==winner->info.emitted&&v.info.frames==winner->info.frames&&v.info.digest>winner->info.digest))winner=std::move(v);
 }
 if(!winner)return std::nullopt;
 winner->info.session=materialize(base,*winner);
 return winner->info;
}
}
