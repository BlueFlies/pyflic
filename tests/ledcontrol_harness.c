/* Runs the DFM firmware's Paradigm logic (DFMV3_V2 src/LEDControl.c) on a
 * recording simulated by tests/v4_fixtures.py, for
 * tests/test_ledcontrol_crosscheck.py.
 *
 * It does what the firmware's main loop does for one DFM: InitializeLEDControl
 * at power-up, ResetParadigmState for the buffer reset that starts a recording,
 * the Linkage PyMCU sends, then every millisecond any instruction due (checked
 * and parsed as UART2.c does) and one StepLEDControl, and every record_ms the
 * Status record's Paradigm fields (PacketManager.c FillParadigmStatus).
 *
 * Usage: harness <input> <records out> <masks out>
 *
 * Input, binary, little-endian:
 *   int32 n_ms, int32 record_ms, int32 n_instructions
 *   uint8 linkage[12]
 *   n_instructions x { int32 first_ms; uint8 instruction[63] }   decoded 0xF7, with checksum
 *   n_ms x int32 signals[12]                                     sums of 128 scans per Well
 *
 * Records out, text, one line per record:
 *   index instruction_number paradigm_type phase_bits led_mask
 *   on_ms[12] activations[12] requirement[12] progress[12]
 *
 * Masks out, binary: n_ms x uint16 little-endian, the LED mask after Linkage.
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include "LEDControl.h"

static FILE *input;

static void Fail(const char *what) {
    fprintf(stderr, "harness: %s\n", what);
    exit(2);
}

static int32_t ReadInt32(void) {
    uint8_t b[4];
    if (fread(b, 1, 4, input) != 4)
        Fail("input ended early");
    return (int32_t) ((uint32_t) b[0] | ((uint32_t) b[1] << 8) | ((uint32_t) b[2] << 16) | ((uint32_t) b[3] << 24));
}

/* UART2.c ValidateChecksum: the 4-byte big-endian two's complement of the byte sum. */
static int ChecksumIsValid(const uint8_t *frame) {
    uint32_t sum = 0, expected;
    int i;
    for (i = 0; i < PARADIGM_INSTRUCTION_SIZE - 4; i++)
        sum += frame[i];
    expected = ((uint32_t) frame[59] << 24) | ((uint32_t) frame[60] << 16) | ((uint32_t) frame[61] << 8) | frame[62];
    return (uint32_t) (sum + expected) == 0;
}

int main(int argc, char **argv) {
    FILE *records, *masks;
    int32_t n_ms, record_ms, n_instructions, t, i;
    int32_t *starts;
    uint8_t (*frames)[PARADIGM_INSTRUCTION_SIZE];
    unsigned char linkage[WELL_COUNT];
    int signals[WELL_COUNT];
    int32_t next = 0;
    uint8_t w;

    if (argc != 4)
        Fail("usage: harness <input> <records out> <masks out>");
    input = fopen(argv[1], "rb");
    records = fopen(argv[2], "w");
    masks = fopen(argv[3], "wb");
    if (!input || !records || !masks)
        Fail("cannot open a file");

    n_ms = ReadInt32();
    record_ms = ReadInt32();
    n_instructions = ReadInt32();
    if (n_ms <= 0 || record_ms <= 0 || n_instructions < 0)
        Fail("bad header");
    if (fread(linkage, 1, WELL_COUNT, input) != WELL_COUNT)
        Fail("input ended early");
    starts = malloc(sizeof(int32_t) * (size_t) (n_instructions + 1));
    frames = malloc((size_t) PARADIGM_INSTRUCTION_SIZE * (size_t) (n_instructions + 1));
    if (!starts || !frames)
        Fail("out of memory");
    for (i = 0; i < n_instructions; i++) {
        starts[i] = ReadInt32();
        if (fread(frames[i], 1, PARADIGM_INSTRUCTION_SIZE, input) != PARADIGM_INSTRUCTION_SIZE)
            Fail("input ended early");
        if (!ChecksumIsValid(frames[i]))
            Fail("instruction checksum is wrong");
    }

    InitializeLEDControl();
    ResetParadigmState();
    SetLEDLinkFlags(linkage);

    for (t = 0; t < n_ms; t++) {
        uint16_t mask;
        uint8_t m[2];
        /* An instruction applies from the step after the one it arrived in. */
        while (next < n_instructions && starts[next] == t) {
            ParadigmInstruction instruction;
            if (!ParseParadigmInstruction(frames[next], PARADIGM_INSTRUCTION_SIZE, &instruction))
                Fail("an instruction does not parse");
            ApplyParadigmInstruction(&instruction);
            next++;
        }
        for (w = 0; w < WELL_COUNT; w++)
            signals[w] = (int) ReadInt32();
        mask = StepLEDControl(signals);
        m[0] = (uint8_t) (mask & 0xFF);
        m[1] = (uint8_t) (mask >> 8);
        fwrite(m, 1, 2, masks);
        if ((t + 1) % record_ms == 0) {
            fprintf(records, "%ld %u %u %u %u", (long) ((t + 1) / record_ms), (unsigned) GetInstructionNumber(),
                    (unsigned) GetParadigmType(), (unsigned) GetPhaseBits(), (unsigned) mask);
            for (w = 0; w < WELL_COUNT; w++)
                fprintf(records, " %u", (unsigned) TakeOnMs(w));
            for (w = 0; w < WELL_COUNT; w++)
                fprintf(records, " %u", (unsigned) GetActivations(w));
            for (w = 0; w < WELL_COUNT; w++)
                fprintf(records, " %u", (unsigned) GetRequirement(w));
            for (w = 0; w < WELL_COUNT; w++)
                fprintf(records, " %u", (unsigned) GetProgress(w));
            fputc('\n', records);
        }
    }
    if (next != n_instructions)
        Fail("an instruction starts after the recording ends");
    fclose(input);
    fclose(records);
    fclose(masks);
    free(starts);
    free(frames);
    return 0;
}
