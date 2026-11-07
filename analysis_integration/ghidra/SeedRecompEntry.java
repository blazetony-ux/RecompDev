// @category RecompDev
// PreScript: SeedRecompEntry.java 0xADDRESS
// Creates a conservative entry function for raw binary imports before auto-analysis.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
public class SeedRecompEntry extends GhidraScript {
  public void run() throws Exception {
    String[] args=getScriptArgs();
    if(args.length!=1)throw new IllegalArgumentException("SeedRecompEntry.java 0xADDRESS");
    Address a=currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(Long.decode(args[0]));
    if(!currentProgram.getMemory().contains(a))throw new IllegalArgumentException("Entry not mapped: "+a);
    disassemble(a);
    if(currentProgram.getFunctionManager().getFunctionAt(a)==null)createFunction(a,"recomp_seed_entry");
    println("RECOMP_SEEDED="+a);
  }
}
