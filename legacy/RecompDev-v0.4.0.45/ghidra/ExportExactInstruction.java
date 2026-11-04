// @category RecompDev
// Export P-code beginning at a requested address, even without a Ghidra Function.
// PostScript: ExportExactInstruction.java OUTPUT.json 0xENTRY
// Always independently attest output against the original ROM before use.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;
import ghidra.program.model.pcode.*;
import ghidra.program.model.lang.Register;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
public class ExportExactInstruction extends GhidraScript {
  String quote(String s) {
    if(s==null)return "null";
    StringBuilder b=new StringBuilder("\"");
    for(char c:s.toCharArray()) {
      if(c=='"'||c=='\\')b.append('\\').append(c);
      else if(c=='\n')b.append("\\n");else if(c=='\r')b.append("\\r");
      else if(c=='\t')b.append("\\t"); else if(c<32)b.append(String.format("\\u%04x",(int)c)); else b.append(c);
    }
    return b.append('"').toString();
  }
  long address(Address a){return a.getOffset();}
  String hex(byte[] bytes)throws Exception {
    byte[] d=MessageDigest.getInstance("SHA-256").digest(bytes);
    StringBuilder sb=new StringBuilder();for(byte x:d)sb.append(String.format("%02x",x&255));return sb.toString();
  }
  String varnode(Varnode v) {
    if(v==null)return "null";
    String space=v.getAddress().getAddressSpace().getName();
    String name=null;
    if(v.isRegister()) {
      Register r=currentProgram.getRegister(v.getAddress(),v.getSize());
      if(r!=null)name=r.getName();
    }
    return "{\"space\":"+quote(space)+",\"offset\":"+Long.toUnsignedString(v.getOffset())+
      ",\"size\":"+v.getSize()+",\"name\":"+quote(name)+"}";
  }
  String flows(Address[] a){StringBuilder b=new StringBuilder("[");if(a!=null)for(int n=0;n<a.length;n++){
    if(n>0)b.append(',');b.append(Long.toUnsignedString(address(a[n])));
  }return b.append(']').toString();}
  public void run()throws Exception {
    String[] args=getScriptArgs();
    if(args.length!=2)throw new IllegalArgumentException("OUTPUT.json 0xENTRY");
    Address start=currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(Long.decode(args[1]));
    if(!currentProgram.getMemory().contains(start))throw new IllegalArgumentException("Unmapped exact-entry: "+start);
    Listing listing=currentProgram.getListing();
    Instruction first=listing.getInstructionAt(start);
    if(first==null){disassemble(start);first=listing.getInstructionAt(start);}
    StringBuilder b=new StringBuilder();
    b.append("{\"schema\":\"recomp-exact-instruction-v1\",\"language\":")
     .append(quote(currentProgram.getLanguageID().getIdAsString()))
     .append(",\"entry\":").append(address(start))
     .append(",\"status\":").append(quote(first==null?"NO_INSTRUCTION_AT_ENTRY":"EXACT_INSTRUCTION_RECOVERED"))
     .append(",\"instructions\":[");
    Address cursor=start;int count=0;
    while(count<64 && !monitor.isCancelled()){
      Instruction ins=listing.getInstructionAt(cursor);
      if(ins==null)break;
      if(count++>0)b.append(',');
      b.append("{\"address\":").append(address(ins.getAddress()))
       .append(",\"length\":").append(ins.getLength())
       .append(",\"bytes_sha256\":").append(quote(hex(ins.getBytes())))
       .append(",\"mnemonic\":").append(quote(ins.getMnemonicString()))
       .append(",\"delay_slots\":").append(ins.getDelaySlotDepth())
       .append(",\"call\":").append(ins.getFlowType().isCall())
       .append(",\"terminal\":").append(ins.getFlowType().isTerminal())
       .append(",\"flows\":").append(flows(ins.getFlows()))
       .append(",\"fallthrough\":").append(ins.getFallThrough()==null?"null":Long.toUnsignedString(address(ins.getFallThrough())))
       .append(",\"pcode\":[");
      PcodeOp[] ops=ins.getPcode();
      for(int j=0;j<ops.length;j++){
        PcodeOp op=ops[j];if(j>0)b.append(',');
        String memSpace=null;
        if ((op.getOpcode()==PcodeOp.LOAD || op.getOpcode()==PcodeOp.STORE) && op.getNumInputs()>0) {
          ghidra.program.model.address.AddressSpace ms=currentProgram.getAddressFactory().getAddressSpace((int)op.getInput(0).getOffset());
          if(ms!=null)memSpace=ms.getName();
        }
        b.append("{\"op\":").append(quote(PcodeOp.getMnemonic(op.getOpcode())))
         .append(",\"memory_space\":").append(quote(memSpace))
         .append(",\"output\":").append(varnode(op.getOutput())).append(",\"inputs\":[");
        for(int k=0;k<op.getNumInputs();k++){
          if(k>0)b.append(',');b.append(varnode(op.getInput(k)));
        }
        b.append("]}");
      }
      b.append("]}");
      if(ins.getFlowType().isTerminal() || ins.getFlowType().isJump() && !ins.getFlowType().isConditional())break;
      Address next=ins.getFallThrough();
      if(next==null || !next.equals(ins.getMaxAddress().next()) || !currentProgram.getMemory().contains(next))break;
      cursor=next;
    }
    if(monitor.isCancelled())throw new IOException("Exact instruction export cancelled");
    b.append("]}\n");
    File f=new File(args[0]);if(f.getParentFile()!=null)f.getParentFile().mkdirs();
    try(Writer w=new OutputStreamWriter(new FileOutputStream(f),StandardCharsets.UTF_8)){w.write(b.toString());}
    println("RECOMP_EXACT_ENTRY="+start+" instructions="+count+" status="+(first==null?"NO_INSTRUCTION":"RECOVERED"));
  }
}
