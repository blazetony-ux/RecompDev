// @category RecompDev
// Export recovered function bodies and raw P-code, without storing original program bytes.
// PostScript: ExportFunctionBodies.java OUTPUT.json TARGET_ID SOURCE_SHA256 [MAX_FUNCTIONS]
// IMPORTANT: SOURCE_SHA256 is a claim from the calling coordinator; it is independently
// checked against original owner-local bytes for EVERY emitted instruction before lowering.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;
import ghidra.program.model.pcode.*;
import ghidra.program.model.lang.Register;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;

public class ExportFunctionBodies extends GhidraScript {
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
    String[] a=getScriptArgs();if(a.length<3||a.length>4)throw new IllegalArgumentException("OUTPUT TARGET_ID SOURCE_SHA256 [MAX_FUNCTIONS]");
    if(!a[2].matches("[a-fA-F0-9]{64}"))throw new IllegalArgumentException("SHA256 required");
    int maximum=a.length==4?Integer.parseInt(a[3]):5000;
    if(maximum<1||maximum>20000)throw new IllegalArgumentException("invalid MAX_FUNCTIONS");
    File f=new File(a[0]);if(f.getParentFile()!=null)f.getParentFile().mkdirs();
    StringBuilder out=new StringBuilder();
    out.append("{\"schema\":\"recomp-function-pcode-v1\",\"target_id\":").append(quote(a[1]))
       .append(",\"source_sha256\":").append(quote(a[2].toLowerCase(Locale.ROOT)))
       .append(",\"analyzer\":\"ghidra-raw-pcode\",\"language\":")
       .append(quote(currentProgram.getLanguageID().getIdAsString()))
       .append(",\"functions\":[");
    FunctionIterator it=currentProgram.getFunctionManager().getFunctions(true);
    int fc=0,ic=0;
    while(it.hasNext()&&!monitor.isCancelled()&&fc<maximum){
      Function fn=it.next();
      if(fn.isExternal()||fn.isThunk())continue;
      if(fc++>0)out.append(',');
      out.append("{\"entry\":").append(address(fn.getEntryPoint()))
         .append(",\"name\":").append(quote(fn.getName()))
         .append(",\"body_min\":").append(address(fn.getBody().getMinAddress()))
         .append(",\"body_max\":").append(address(fn.getBody().getMaxAddress()))
         .append(",\"instructions\":[");
      InstructionIterator ii=currentProgram.getListing().getInstructions(fn.getBody(),true);
      int count=0;
      while(ii.hasNext()&&!monitor.isCancelled()&&count<10000){
        Instruction ins=ii.next();if(count++>0)out.append(',');ic++;
        out.append("{\"address\":").append(address(ins.getAddress()))
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
          PcodeOp op=ops[j];if(j>0)out.append(',');
          String memSpace=null;
          if ((op.getOpcode()==PcodeOp.LOAD || op.getOpcode()==PcodeOp.STORE) && op.getNumInputs()>0) {
            ghidra.program.model.address.AddressSpace ms=currentProgram.getAddressFactory().getAddressSpace((int)op.getInput(0).getOffset());
            if(ms!=null)memSpace=ms.getName();
          }
          out.append("{\"op\":").append(quote(PcodeOp.getMnemonic(op.getOpcode())))
             .append(",\"memory_space\":").append(quote(memSpace))
             .append(",\"output\":").append(varnode(op.getOutput())).append(",\"inputs\":[");
          for(int k=0;k<op.getNumInputs();k++){
            if(k>0)out.append(',');out.append(varnode(op.getInput(k)));
          }
          out.append("]}");
        }
        out.append("]}");
      }
      if(ii.hasNext())throw new IOException("Function instruction limit reached; incomplete export forbidden");
      out.append("]}");
    }
    if(monitor.isCancelled())throw new IOException("Cancelled export; incomplete evidence discarded");
    out.append("]}\n");
    try(Writer w=new OutputStreamWriter(new FileOutputStream(f),StandardCharsets.UTF_8)){w.write(out.toString());}
    println("RECOMP_FUNCTION_PCODE_EXPORTED functions="+fc+" instructions="+ic+" path="+f.getAbsolutePath());
  }
}
