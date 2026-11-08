#include "monitor_model.hpp"
#include <iostream>
#include <stdexcept>
static void ok(bool yes){if(!yes)throw std::runtime_error("NATIVE_MONITOR_CONTRACT_FAIL");}
int main(){
 rdmonitor::State m;
 ok(!m.ingest(R"({"schema":"other","type":"instruction"})"));
 ok(!m.ingest(R"({"schema":"recompdev.controller.diagnostics.v1","type":"unknown"})"));
 ok(m.ingest(R"({"schema":"recompdev.controller.diagnostics.v1","type":"connected"})"));
 ok(m.ingest(R"({"schema":"recompdev.controller.diagnostics.v1","type":"instruction","cpu":"mips","pc":128,"sp":2048,"steps":63,"guest_cycles":99,"opcode":5,"opcode_class":"LOAD","next_pc":132})"));
 ok(m.cpu.find("mips")!=std::string::npos&&m.cpu.find("0x80")!=std::string::npos);
 ok(m.ingest(R"({"schema":"recompdev.controller.diagnostics.v1","type":"frame","frame":17,"guest_cycles":100,"steps":64})"));
 ok(m.ingest(R"({"schema":"recompdev.controller.diagnostics.v1","type":"native_result","status":"FRAME_BUDGET_REACHED","pc":132,"host_frame":18,"guest_frame":17})"));
 ok(m.frame.find("Host output frames: 18")!=std::string::npos);
 ok(m.status.find("FRAME_BUDGET_REACHED")!=std::string::npos);
 ok(m.ingest(R"({"schema":"recompdev.controller.diagnostics.v1","type":"session","status":"Controller disconnected"})"));
 ok(m.connection.find("disconnected")!=std::string::npos);
 for(int i=0;i<700;++i)ok(m.ingest(R"({"schema":"recompdev.controller.diagnostics.v1","type":"input","buttons":1,"guest_cycles":2})"));
 ok(m.lines.size()==300&&m.accepted==705&&m.rejected==2);
 std::cout<<"PASS: native CPU-neutral monitor event schema, bounded projection and terminal frames\n";
}
