import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.lang.*;
import java.math.BigInteger;
import java.nio.file.*;
import java.io.*;

public class AnalyzeBoot extends GhidraScript {
    public void run() throws Exception {
        Path out = Path.of(getScriptArgs()[0]);
        Files.createDirectories(out);
        Register thumb = currentProgram.getRegister("TMode");
        if (getInstructionAt(toAddr(0x5c)) == null)
            currentProgram.getProgramContext().setValue(thumb, toAddr(4), toAddr(0x3fff), BigInteger.ONE);
        // First four bytes are absent. Preserve real vector offsets, do not invent SP.
        for (int vector=4; vector<0x48; vector+=4) {
            long value = Integer.toUnsignedLong(getInt(toAddr(vector)));
            if ((value&1)!=0 && value>=0x49 && value<0x4000) {
                Address a=toAddr(value&~1L);
                disassemble(a);
                if (getFunctionAt(a)==null) createFunction(a, "vector_"+Integer.toHexString(vector));
            }
        }
        analyzeAll(currentProgram);
        DecompInterface decompiler = new DecompInterface();
        decompiler.openProgram(currentProgram);
        try (PrintWriter index = new PrintWriter(out.resolve("functions.tsv").toFile());
             PrintWriter asm = new PrintWriter(out.resolve("listing.asm").toFile());
             PrintWriter refs = new PrintWriter(out.resolve("references.tsv").toFile())) {
            FunctionIterator funcs=currentProgram.getFunctionManager().getFunctions(true);
            while (funcs.hasNext()) {
                Function f=funcs.next();
                index.println(f.getEntryPoint()+"\t"+f.getName()+"\t"+f.getBody().getNumAddresses());
                DecompileResults r=decompiler.decompileFunction(f,30,monitor);
                String c=r.decompileCompleted()?r.getDecompiledFunction().getC():"// FAILED: "+r.getErrorMessage();
                Files.writeString(out.resolve(f.getEntryPoint()+".c"), c);
            }
            InstructionIterator insns=currentProgram.getListing().getInstructions(true);
            while (insns.hasNext()) {
                Instruction i=insns.next();
                asm.println(i.getAddress()+"\t"+i.toString());
                for (var ref:i.getReferencesFrom()) refs.println(ref.getFromAddress()+"\t"+ref.getToAddress()+"\t"+ref.getReferenceType());
            }
        }
        decompiler.dispose();
        println("Boot export complete");
    }
}
