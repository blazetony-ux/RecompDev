#include "rd_sha256.hpp"
#include <cstdint>
#include <cstdio>
#include <string>
int main(){
 auto test=[](const std::string& v,const std::string& expected){
  const auto got=rdhash::sha256(reinterpret_cast<const std::uint8_t*>(v.data()),v.size());
  return got==expected;
 };
 if(!test("","e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855") ||
    !test("abc","ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad") ||
    !test(std::string(1000000,'a'),"cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0")){
  std::puts("SHA256_VECTOR_FAIL");return 1;
 }
 std::puts("SHA256_VECTORS_PASS");return 0;
}
