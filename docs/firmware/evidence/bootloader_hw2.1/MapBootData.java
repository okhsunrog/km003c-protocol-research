import ghidra.app.script.GhidraScript;
import java.io.ByteArrayInputStream;
import java.math.BigInteger;

public class MapBootData extends GhidraScript {
    public void run() throws Exception {
        // Startup table at 0x2a80 explicitly copies these flash-backed regions.
        // This is a reconstructed static runtime mapping, not a RAM acquisition.
        byte[] data = getBytes(toAddr(0x2ab0), 0x140);
        currentProgram.getMemory().createInitializedBlock("startup_data", toAddr(0x1fff8000),
            new ByteArrayInputStream(data), data.length, monitor, false);
        currentProgram.getProgramContext().setValue(currentProgram.getRegister("TMode"),
            toAddr(0x1fff8000), toAddr(0x1fff808f), BigInteger.ONE);
        disassemble(toAddr(0x1fff8000));
        createFunction(toAddr(0x1fff8000), "flash_program_from_ram");
        runScript("AnalyzeBoot.java", getScriptArgs());
    }
}
