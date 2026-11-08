#include "artifact_store_abi.h"
#include "artifact_store.hpp"
#include <cstring>
#include <limits>
#include <string>
#include <filesystem>
namespace {
int store_put(const char*root,const char*kind,const char*producer,const char*target,const char*abi,
              const uint8_t*data,uint64_t length,char*digest,uint32_t capacity){
 try{
  if(!root||!kind||!producer||!target||!abi||!data||!digest||capacity<65||
     length==0||length>128ull*1024*1024)return 0;
  const auto result=rdartifact::put(std::filesystem::u8path(root),kind,producer,target,abi,
                                   std::string(reinterpret_cast<const char*>(data),static_cast<std::size_t>(length)));
  std::memcpy(digest,result.digest.c_str(),65);return 1;
 }catch(...){return 0;}
}
int store_get(const char*root,const char*kind,const char*producer,const char*target,const char*abi,
              const char*digest,uint8_t*output,uint64_t*capacity){
 try{
  if(!root||!kind||!producer||!target||!abi||!digest||!capacity||std::strlen(digest)!=64)return 0;
  rdartifact::Blob b; b.kind=kind;b.producer=producer;b.target=target;b.abi=abi;b.digest=digest;
  // Read the object only after checking its SHA-256 and immutable descriptor.
  // The exported API never returns an unauthenticated pointer to file memory.
  const auto size=std::filesystem::file_size(std::filesystem::u8path(root)/"objects"/
                                  b.digest.substr(0,2)/b.digest);
  if(size>128ull*1024*1024)return 0;
  b.bytes=size;
  auto result=rdartifact::get(std::filesystem::u8path(root),b);
  if(!output){*capacity=result.size();return -1;}
  if(*capacity<result.size()){*capacity=result.size();return -1;}
  std::memcpy(output,result.data(),result.size());*capacity=result.size();return 1;
 }catch(...){return 0;}
}
const RD_ArtifactStoreAPIv1 api{RD_ARTIFACT_STORE_ABI_V1,sizeof(RD_ArtifactStoreAPIv1),store_put,store_get};
}
extern "C" RD_STORE_EXPORT const RD_ArtifactStoreAPIv1* rd_artifact_store_api_v1(){return &api;}
