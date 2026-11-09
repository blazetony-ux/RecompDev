#include "rd_native_module_set.hpp"
#include "rd_sha256.hpp"
#include <algorithm>
#include <array>
#include <fstream>
#include <stdexcept>
#include <string>
#include <unordered_set>
#ifdef _WIN32
# define WIN32_LEAN_AND_MEAN
# include <windows.h>
#else
# include <dlfcn.h>
#endif
namespace fs=std::filesystem;
namespace recomp::native {
namespace {
std::string bound(const char* s){
 if(!s)throw std::runtime_error("NATIVE_MODULE_ID_MISSING");
 std::size_t n=0;
 while(n<256&&s[n])++n;
 if(!n||n==256)throw std::runtime_error("NATIVE_MODULE_ID_INVALID");
 return std::string(s,n);
}
bool digest(const std::string& s){
 return s.size()==64&&std::all_of(s.begin(),s.end(),[](char c){return (c>='0'&&c<='9')||(c>='a'&&c<='f');});
}
#ifdef _WIN32
using Handle=HMODULE;
Handle open(const fs::path& p){return LoadLibraryExW(p.c_str(),nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);}
void *symbol(Handle h){return reinterpret_cast<void*>(GetProcAddress(h,"rd_native_block_get_v1"));}
void close(Handle h){if(h)FreeLibrary(h);}
#else
using Handle=void*;
Handle open(const fs::path& p){return dlopen(p.c_str(),RTLD_NOW|RTLD_LOCAL);}
void *symbol(Handle h){return dlsym(h,"rd_native_block_get_v1");}
void close(Handle h){if(h)dlclose(h);}
#endif
struct ScopedHandle {
 Handle handle=nullptr;
 explicit ScopedHandle(Handle h):handle(h){}
 ScopedHandle(const ScopedHandle&)=delete;
 ~ScopedHandle(){close(handle);}
 Handle release(){auto v=handle;handle=nullptr;return v;}
};
}
struct ModuleSet::Entry {
 Handle handle=nullptr;
 RD_NativeBlockStepV1 invoke=nullptr;
 std::string sha256;
 Entry(Handle h,RD_NativeBlockStepV1 fn,std::string sha):handle(h),invoke(fn),sha256(std::move(sha)){}
 ~Entry(){close(handle);}
};
ModuleSet::ModuleSet(Identity id):id_(std::move(id)){
 if(id_.cpu_id.empty()||id_.cpu_semantics_version.empty()||id_.machine_id.empty()||
    id_.machine_state_abi.empty()||id_.target_abi.empty()||!id_.source_size||
    !digest(id_.source_sha256))throw std::invalid_argument("NATIVE_SESSION_ID_INVALID");
}
ModuleSet::~ModuleSet()=default;
std::string sha256_binary(const fs::path& path){
 if(!fs::is_regular_file(path)||fs::is_symlink(path)||fs::file_size(path)>256ull*1024*1024||!fs::file_size(path))
  throw std::runtime_error("NATIVE_MODULE_BINARY_UNSAFE");
 std::ifstream f(path,std::ios::binary);
 if(!f)throw std::runtime_error("NATIVE_MODULE_BINARY_UNREADABLE");
 // Deliberately bounded to 256 MiB; immutable source-attested modules may be
 // loaded only after their full bytes and expected digest are checked.
 std::vector<std::uint8_t> bytes(static_cast<std::size_t>(fs::file_size(path)));
 if(!f.read(reinterpret_cast<char*>(bytes.data()),std::streamsize(bytes.size())))
  throw std::runtime_error("NATIVE_MODULE_BINARY_UNREADABLE");
 return rdhash::sha256(bytes.data(),bytes.size());
}
void ModuleSet::activate(const fs::path& file,const std::string& expected_sha){
 if(!digest(expected_sha)||sha256_binary(file)!=expected_sha)throw std::runtime_error("NATIVE_MODULE_BINARY_SHA256_MISMATCH");
 for(const auto& e:entries_)if(e->sha256==expected_sha)throw std::runtime_error("NATIVE_MODULE_ALREADY_ACTIVE");
 ScopedHandle h(open(fs::absolute(file)));
 if(!h.handle)throw std::runtime_error("NATIVE_MODULE_LOAD_FAILED");
 auto entry=reinterpret_cast<RD_NativeBlockGetV1>(symbol(h.handle));
 if(!entry)throw std::runtime_error("NATIVE_MODULE_ENTRYPOINT_MISSING");
 const RD_NativeBlockV1* m=entry();
 if(!m||m->abi_version!=RD_NATIVE_BLOCK_ABI_V1||m->struct_size!=sizeof(RD_NativeBlockV1)||!m->step)
  throw std::runtime_error("NATIVE_MODULE_ABI_INCOMPATIBLE");
 if(bound(m->cpu_id)!=id_.cpu_id||bound(m->cpu_semantics_version)!=id_.cpu_semantics_version||
    bound(m->machine_id)!=id_.machine_id||bound(m->machine_state_abi)!=id_.machine_state_abi||
    bound(m->target_abi)!=id_.target_abi||bound(m->source_sha256)!=id_.source_sha256||
    m->source_size!=id_.source_size)
  throw std::runtime_error("NATIVE_MODULE_SOURCE_OR_CONTEXT_MISMATCH");
 // Forbid a file being modified in the interval between preflight and ABI
 // validation. The permanent artifact store must also enforce immutability.
 if(sha256_binary(file)!=expected_sha)throw std::runtime_error("NATIVE_MODULE_CHANGED_DURING_LOAD");
 auto p=std::make_unique<Entry>(h.handle,m->step,expected_sha);
 entries_.push_back(std::move(p));
 (void)h.release();
}
int ModuleSet::step(void* state,std::uint32_t physical)const{
 if(!state)return -1;
 for(auto i=entries_.rbegin();i!=entries_.rend();++i){
  const int outcome=(*i)->invoke(state,physical);
  if(outcome!=0)return outcome==1?1:-1;
 }
 return 0;
}
} // namespace recomp::native
