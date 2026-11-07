// Production component contract: the generated native app may link only active DLLs.
#include "runtime.hpp"
#include "rd_sms_mode4.h"
#include "rd_runtime_host.h"
#include <cstdint>
#include <stdexcept>
#include <vector>
#include <iostream>
#define REQUIRE(p) do { if(!(p)) throw std::runtime_error("CUTOVER_ASSERT: " #p); } while(0)
int main(){
 REQUIRE(rd_sms_native_runtime_abi()==0x00010000u);
 REQUIRE(rd_sms_mode4_abi()==RD_SMS_MODE4_ABI);
 REQUIRE(rd_host_abi_version()==RD_HOST_ABI_VERSION);
 rd::State machine;
 machine.rom.resize(262144,0);
 machine.write_byte(0xffff,6);
 REQUIRE(machine.mapper[3]==6);
 REQUIRE(machine.rom_offset(0x8a68)==0x18a68u);
 machine.vdp_regs[2]=0x0e;
 machine.cram[1]=0x03;
 std::vector<std::uint32_t> frame(RD_SMS_MODE4_WIDTH*RD_SMS_MODE4_HEIGHT);
 rd_sms_mode4_stats stats{};
 REQUIRE(rd_sms_mode4_render(machine.vram.data(),16384,machine.cram.data(),32,
    machine.vdp_regs.data(),16,frame.data(),static_cast<uint32_t>(frame.size()),&stats)==1);
 REQUIRE(stats.abi==RD_SMS_MODE4_ABI);
 REQUIRE(frame[0]==0xff000000u);
 RD_Host* host=nullptr;
 REQUIRE(rd_host_create(RD_HOST_MODE_HEADLESS,"cutover",44100,&host)==0);
 REQUIRE(host);
 REQUIRE(rd_host_present(host,frame.data(),RD_SMS_MODE4_WIDTH,RD_SMS_MODE4_HEIGHT,RD_HOST_PIXELS_BGRA8888)==0);
 RD_HostStats host_stats{};host_stats.struct_size=sizeof(host_stats);
 REQUIRE(rd_host_stats(host,&host_stats)==0);
 REQUIRE(host_stats.frames==1 && host_stats.width==256 && host_stats.height==192);
 REQUIRE(rd_host_pump(host)>0);
 REQUIRE(rd_host_buttons(host)==0);
 rd_host_destroy(host);
 std::cout<<"NATIVE_SMS_RUNTIME_CUTOVER_PASS; mapper=6; video=mode4; host=headless\n";
}
