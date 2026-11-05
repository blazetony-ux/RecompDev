#pragma once
// RecompDev generic read-only guest memory observation API, v1.
// No CPU, system, emulator, game, register name or address is assumed.
// A machine adapter supplies immutable byte spans and metadata at a sampling point.
// Sampling never mutates the supplied spans. Changes are bounded and opt-in.
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>

namespace rd_state_observer {
struct MemoryRegionView {
 const char* region_id;      // stable, provider-scoped identifier (e.g. "main_ram")
 const char* provider;       // machine/plugin identifier, not a game name
 const char* address_space;  // declared by provider, e.g. "cpu0"
 std::uint64_t base_address;
 const std::uint8_t* bytes;
 std::size_t byte_count;
 const char* byte_order;     // "little", "big", "unknown"; NEVER presumed by recorder
 const char* clock_domain;   // provider-described clock, e.g. "cpu0"
};

class MemoryRecorder final {
 static constexpr std::size_t max_regions_ = 64;
 static constexpr std::size_t max_region_bytes_ = 65536;
 static constexpr std::size_t max_monitored_bytes_ = 262144;
 static constexpr std::uint64_t max_samples_ = 36000;
 static constexpr std::uint64_t max_change_rows_ = 2000000;
 struct RecordedRegion {
  std::string provider,space,byte_order,clock_domain;
  std::uint64_t base=0;
  std::vector<std::uint8_t> previous;
  std::uint64_t samples=0,changes=0;
 };
 std::map<std::string,RecordedRegion> regions_;
 std::ofstream metadata_,changes_,summary_;
 std::size_t monitored_bytes_=0;
 std::uint64_t samples_=0,rows_=0;
 std::map<std::string,std::uint64_t> last_cycles_;
 bool enabled_=false,truncated_=false;
 std::string truncate_reason_="none";
 static std::string checked_token(const char* s,const char* field){
  if(!s||!*s)throw std::invalid_argument(std::string("STATE_OBSERVER_EMPTY_")+field);
  const std::string name(s);
  if(name.size()>96)throw std::invalid_argument("STATE_OBSERVER_TOKEN_TOO_LONG");
  for(const unsigned char c:name){
   if(!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='_'||c=='-'||c=='.'))
    throw std::invalid_argument("STATE_OBSERVER_INVALID_METADATA_TOKEN");
  }
  return name;
 }
 static void open(std::ofstream& f,const std::string& path,const char* header){
  f.open(path,std::ios::out|std::ios::trunc|std::ios::binary);
  if(!f)throw std::runtime_error("STATE_OBSERVER_OPEN_FAILED");
  f<<header<<'\n';
  if(!f)throw std::runtime_error("STATE_OBSERVER_HEADER_WRITE_FAILED");
 }
 void stop(const char* reason){truncated_=true;truncate_reason_=reason;}
 MemoryRecorder(){
  const char* dir=std::getenv("RECOMPDEV_STATE_TRACE_DIR");
  if(!dir||!*dir)return;
  const std::string prefix=std::string(dir)+"/";
  open(metadata_,prefix+"state-memory-regions.csv",
       "region_id,provider,address_space,base_address,size_bytes,byte_order,clock_domain");
  open(changes_,prefix+"state-memory-deltas.csv",
       "sample_seq,guest_frame,guest_cycle,region_id,offset,previous,current");
  open(summary_,prefix+"state-memory-summary.csv","region_id,samples,changes,truncated,truncate_reason");
  enabled_=true;
 }
 public:
 MemoryRecorder(const MemoryRecorder&)=delete;
 MemoryRecorder& operator=(const MemoryRecorder&)=delete;
 static MemoryRecorder& instance(){static MemoryRecorder r;return r;}
 ~MemoryRecorder(){
  if(!enabled_)return;
  for(const auto& kv:regions_){
   summary_<<kv.first<<','<<kv.second.samples<<','<<kv.second.changes<<','
     <<(truncated_?1:0)<<','<<truncate_reason_<<'\n';
  }
 }
 // Sample point is owned by the provider. First sample emits complete baseline
 // with previous=-1, then only changed bytes. This is observation, not state restore.
 void sample(std::uint64_t cycle,std::uint64_t frame,
             const MemoryRegionView* views,std::size_t count){
  if(!enabled_||truncated_)return;
  if(count==0)return;
  if(!views)throw std::invalid_argument("STATE_OBSERVER_NULL_VIEW_ARRAY");
  if(++samples_>max_samples_){stop("sample_limit");return;}
  // Clock domains are provider-defined: CPU0 and CPU1 counters need not align.
  // Only enforce monotonicity within a given domain, never across domains.
  for(std::size_t i=0;i<count;++i){
   const auto& view=views[i];
   const auto id=checked_token(view.region_id,"REGION_ID");
   const auto provider=checked_token(view.provider,"PROVIDER");
   const auto space=checked_token(view.address_space,"ADDRESS_SPACE");
   const auto byte_order=checked_token(view.byte_order,"BYTE_ORDER");
   const auto clock=checked_token(view.clock_domain,"CLOCK_DOMAIN");
   const auto clock_it=last_cycles_.find(clock);
   if(clock_it!=last_cycles_.end()&&cycle<clock_it->second)
    throw std::runtime_error("STATE_OBSERVER_NONMONOTONIC_DOMAIN_CYCLE");
   last_cycles_[clock]=cycle;
   if(!view.bytes||view.byte_count==0||view.byte_count>max_region_bytes_)
     throw std::invalid_argument("STATE_OBSERVER_INVALID_REGION_SPAN");
   auto it=regions_.find(id);
   if(it==regions_.end()){
    if(regions_.size()>=max_regions_||view.byte_count>max_monitored_bytes_-monitored_bytes_){
     stop("region_budget");return;
    }
    RecordedRegion state;
    state.provider=provider;state.space=space;state.byte_order=byte_order;
    state.clock_domain=clock;state.base=view.base_address;
    metadata_<<id<<','<<provider<<','<<space<<','<<view.base_address<<','
      <<view.byte_count<<','<<byte_order<<','<<clock<<'\n';
    // All 256 byte values are impossible as an unseen baseline marker; -1 means unknown.
    for(std::size_t j=0;j<view.byte_count;++j){
     if(rows_>=max_change_rows_){stop("change_budget");return;}
     changes_<<samples_-1<<','<<frame<<','<<cycle<<','<<id<<','<<j<<",-1,"
       <<unsigned(view.bytes[j])<<'\n';
     ++rows_;++state.changes;
    }
    state.previous.assign(view.bytes,view.bytes+view.byte_count);
    state.samples=1;monitored_bytes_+=view.byte_count;
    regions_.emplace(id,std::move(state));
   }else{
    auto& prev=it->second;
    if(prev.provider!=provider||prev.space!=space||prev.base!=view.base_address||
       prev.previous.size()!=view.byte_count||prev.byte_order!=byte_order||prev.clock_domain!=clock)
      throw std::runtime_error("STATE_OBSERVER_REGION_SCHEMA_CHANGED");
    for(std::size_t j=0;j<view.byte_count;++j){
     if(prev.previous[j]==view.bytes[j])continue;
     if(rows_>=max_change_rows_){stop("change_budget");return;}
     changes_<<samples_-1<<','<<frame<<','<<cycle<<','<<id<<','<<j<<','
       <<unsigned(prev.previous[j])<<','<<unsigned(view.bytes[j])<<'\n';
     ++rows_;++prev.changes;
     prev.previous[j]=view.bytes[j];
    }
    ++prev.samples;
   }
  }
  if(!metadata_||!changes_)throw std::runtime_error("STATE_OBSERVER_WRITE_FAILED");
 }
};
inline void sample_memory(std::uint64_t cycle,std::uint64_t frame,
                          const MemoryRegionView* views,std::size_t count){
 MemoryRecorder::instance().sample(cycle,frame,views,count);
}
} // namespace rd_state_observer
