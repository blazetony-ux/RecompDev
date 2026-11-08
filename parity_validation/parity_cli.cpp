#include "capture_compare.hpp"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <string>
namespace fs=std::filesystem;
static rdparity::Capture read(const fs::path&p){
 std::error_code ec;if(!fs::is_regular_file(p,ec)||fs::is_symlink(p,ec)||fs::file_size(p,ec)>8*1024*1024||ec)
  throw std::runtime_error("PARITY_CAPTURE_MISSING_OR_OVERSIZED");
 std::ifstream f(p,std::ios::binary);if(!f)throw std::runtime_error("PARITY_CAPTURE_READ_FAILED");
 const std::string data(std::istreambuf_iterator<char>{f},{});
 return rdparity::load(rdjson::Reader(data).parse());
}
int main(int argc,char**argv){
 try {
  if(argc!=5||std::string(argv[1])!="--reference"||std::string(argv[3])!="--candidate"){
   std::cerr<<"Usage: RecompDevParity --reference reference.json --candidate candidate.json\n";return 2;
  }
  const auto reference=read(argv[2]);const auto candidate=read(argv[4]);
  const auto result=rdparity::compare(reference,candidate);
  std::cout<<"RECOMPDEV_PARITY_COMPARISON="<<result.status<<"\n"
           <<"RECOMPDEV_PARITY_REASON="<<result.reason<<"\n"
           <<"RECOMPDEV_PARITY_COMPARED_FRAMES="<<result.compared_frames<<"\n"
           <<"RECOMPDEV_PARITY_FIRST_MISMATCH_FRAME="<<result.first_mismatch<<"\n"
           <<"RECOMPDEV_PARITY_INPUT_ATTESTED="<<(result.full_inputs?"TRUE":"FALSE")<<"\n"
           <<"RECOMPDEV_PARITY_AUDIO_PRESENT="<<(result.full_audio?"TRUE":"FALSE")<<"\n"
           <<"RECOMPDEV_PARITY_STATE_PRESENT="<<(result.full_state?"TRUE":"FALSE")<<"\n"
           <<"RECOMPDEV_GAMEPLAY_PARITY_QUALIFIED=FALSE\n";
  return result.status=="MATCHED_UNQUALIFIED"?0:2;
 }catch(const std::exception&e){std::cerr<<"RECOMPDEV_PARITY_ERROR="<<e.what()<<"\nRECOMPDEV_GAMEPLAY_PARITY_QUALIFIED=FALSE\n";return 2;}
}
