// @category RecompDev
// Export metadata-only Ghidra function and call observations into RecompDev.
// Usage as postScript: ExportRecompCatalogue.java OUTPUT.json TARGET_ID ORIGINAL_SHA256
// The operator must ensure the imported Ghidra program matches ORIGINAL_SHA256.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import ghidra.program.model.address.Address;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

public class ExportRecompCatalogue extends GhidraScript {
    private String jsonString(String s) {
        if (s == null) return "null";
        StringBuilder b = new StringBuilder("\"");
        for (char c : s.toCharArray()) {
            if (c=='"' || c=='\\') b.append('\\').append(c);
            else if (c=='\n') b.append("\\n");
            else if (c=='\r') b.append("\\r");
            else if (c=='\t') b.append("\\t");
            else if (c<32) b.append(String.format("\\u%04x",(int)c));
            else b.append(c);
        }
        return b.append('"').toString();
    }
    private long unsignedOffset(Address a) {
        return a.getOffset();
    }
    public void run() throws Exception {
        String[] args=getScriptArgs();
        if (args.length!=3) throw new IllegalArgumentException("Required: OUTPUT.json TARGET_ID ORIGINAL_SHA256");
        if (!args[2].matches("[0-9a-fA-F]{64}")) throw new IllegalArgumentException("Original SHA256 required");
        File out=new File(args[0]);
        if (out.getParentFile()!=null) out.getParentFile().mkdirs();
        StringBuilder funcs=new StringBuilder(),calls=new StringBuilder();
        FunctionManager fm=currentProgram.getFunctionManager();
        FunctionIterator it=fm.getFunctions(true);
        int fc=0,cc=0;
        while(it.hasNext()&&!monitor.isCancelled()) {
            Function f=it.next();
            if(fc++>0)funcs.append(',');
            funcs.append("{\"entry\":").append(unsignedOffset(f.getEntryPoint()))
                 .append(",\"name\":").append(jsonString(f.getName())).append('}');
        }
        InstructionIterator ins=currentProgram.getListing().getInstructions(true);
        while(ins.hasNext()&&!monitor.isCancelled()) {
            Instruction i=ins.next();
            if(!i.getFlowType().isCall()) continue;
            Function owner=fm.getFunctionContaining(i.getAddress());
            Address[] destinations=i.getFlows();
            boolean computed=i.getFlowType().isComputed();
            if(destinations==null || destinations.length==0 || computed) {
                if(cc++>0)calls.append(',');
                calls.append("{\"source\":").append(unsignedOffset(i.getAddress()))
                     .append(",\"target\":null,\"kind\":\"indirect_call\",\"caller_entry\":")
                     .append(owner==null?"null":Long.toString(unsignedOffset(owner.getEntryPoint()))).append('}');
            } else {
                for(Address dst:destinations){
                    if(cc++>0)calls.append(',');
                    calls.append("{\"source\":").append(unsignedOffset(i.getAddress()))
                         .append(",\"target\":").append(unsignedOffset(dst))
                         .append(",\"kind\":\"direct_call\",\"caller_entry\":")
                         .append(owner==null?"null":Long.toString(unsignedOffset(owner.getEntryPoint()))).append('}');
                }
            }
        }
        if(monitor.isCancelled()) throw new IOException("Cancelled: incomplete analysis not exported");
        String doc="{\"schema\":\"recomp-analyzer-discovery-v1\",\"target_id\":"+jsonString(args[1])+
              ",\"source_sha256\":"+jsonString(args[2].toLowerCase(Locale.ROOT))+
              ",\"analyzer\":\"ghidra-function-manager\",\"functions\":["+funcs+"],\"calls\":["+calls+"]}\n";
        try(Writer w=new OutputStreamWriter(new FileOutputStream(out),StandardCharsets.UTF_8)){w.write(doc);}
        println("RECOMPDEV_CATALOGUE_EXPORTED functions="+fc+" callsites="+cc+" file="+out.getAbsolutePath());
    }
}
