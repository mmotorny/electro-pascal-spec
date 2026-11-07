/*
 * QEMU plugin: records which pairs of translated blocks execute one after
 * the other ("edges"), AFL-style, and writes them out whenever the guest
 * executes the marker instruction XCHG BX,BX (87 DB).
 *
 * Arguments:
 *   out=PATH   file to append to: one line per marker, holding the hex
 *              indices of the edges seen since the previous marker
 *   lo=ADDR    only count blocks at linear addresses >= ADDR (default 0)
 *   hi=ADDR    and < ADDR (default: no limit)
 */
#include <qemu-plugin.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

QEMU_PLUGIN_EXPORT int qemu_plugin_version = QEMU_PLUGIN_VERSION;

#define MAP_SIZE (1 << 16)

static unsigned char map[MAP_SIZE];
static uint64_t prev;
static FILE *out;
static uint64_t lo = 0, hi = UINT64_MAX;

static void flush(void)
{
    for (unsigned i = 0; i < MAP_SIZE; i++) {
        if (map[i]) {
            fprintf(out, "%x ", i);
        }
    }
    fputc('\n', out);
    fflush(out);
    memset(map, 0, sizeof map);
    prev = 0;
}

static void on_block(unsigned int vcpu, void *udata)
{
    uint64_t cur = ((uint64_t)(uintptr_t)udata * 0x9E3779B97F4A7C15ull) >> 48;
    map[(cur ^ prev) & (MAP_SIZE - 1)] = 1;
    prev = cur >> 1;
}

static void on_marker(unsigned int vcpu, void *udata)
{
    flush();
}

static void on_translate(struct qemu_plugin_tb *tb, void *userdata)
{
    uint64_t pc = qemu_plugin_tb_vaddr(tb);
    size_t n = qemu_plugin_tb_n_insns(tb);
    for (size_t i = 0; i < n; i++) {
        struct qemu_plugin_insn *insn = qemu_plugin_tb_get_insn(tb, i);
        unsigned char bytes[2];
        if (qemu_plugin_insn_size(insn) == 2 &&
            qemu_plugin_insn_data(insn, bytes, 2) == 2 &&
            bytes[0] == 0x87 && bytes[1] == 0xDB) {
            qemu_plugin_register_vcpu_insn_exec_cb(insn, on_marker,
                                                   QEMU_PLUGIN_CB_NO_REGS, NULL);
        }
    }
    if (pc >= lo && pc < hi) {
        qemu_plugin_register_vcpu_tb_exec_cb(tb, on_block, QEMU_PLUGIN_CB_NO_REGS,
                                             (void *)(uintptr_t)pc);
    }
}

static void on_exit(void *userdata)
{
    flush();
    fclose(out);
}

QEMU_PLUGIN_EXPORT int qemu_plugin_install(qemu_plugin_id_t id, const qemu_info_t *info,
                                           int argc, char **argv)
{
    const char *path = NULL;
    for (int i = 0; i < argc; i++) {
        if (strncmp(argv[i], "out=", 4) == 0) {
            path = argv[i] + 4;
        } else if (strncmp(argv[i], "lo=", 3) == 0) {
            lo = strtoull(argv[i] + 3, NULL, 0);
        } else if (strncmp(argv[i], "hi=", 3) == 0) {
            hi = strtoull(argv[i] + 3, NULL, 0);
        } else {
            fprintf(stderr, "coverage: unknown argument %s\n", argv[i]);
            return -1;
        }
    }
    if (!path || !(out = fopen(path, "a"))) {
        fprintf(stderr, "coverage: needs out=PATH\n");
        return -1;
    }
    qemu_plugin_register_vcpu_tb_trans_cb(id, on_translate, NULL);
    qemu_plugin_register_atexit_cb(id, on_exit, NULL);
    return 0;
}
