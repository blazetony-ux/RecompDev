#pragma once
// CPU-neutral, bounded ingestion queue. Socket thread never draws or calls the
// UI; overflow only drops display samples, never blocks the guest or writer.
#include <algorithm>
#include <cstdint>
#include <deque>
#include <mutex>
#include <string>
#include <vector>
namespace rdmonitor {
class EventQueue {
 std::mutex mu_;
 std::deque<std::string> pending_;
 std::uint64_t dropped_=0;
 public:
 static constexpr std::size_t limit=8192;
 void offer(std::string item){
  std::lock_guard<std::mutex> lock(mu_);
  if(pending_.size()>=limit){pending_.pop_front();++dropped_;}
  pending_.push_back(std::move(item));
 }
 std::vector<std::string> take(std::size_t max_batch){
  std::lock_guard<std::mutex> lock(mu_);
  std::vector<std::string> out;
  const auto n=std::min(pending_.size(),max_batch);
  out.reserve(n);
  for(std::size_t i=0;i<n;++i){out.push_back(std::move(pending_.front()));pending_.pop_front();}
  return out;
 }
 std::uint64_t dropped(){std::lock_guard<std::mutex> lock(mu_);return dropped_;}
 std::size_t waiting(){std::lock_guard<std::mutex> lock(mu_);return pending_.size();}
};
}
