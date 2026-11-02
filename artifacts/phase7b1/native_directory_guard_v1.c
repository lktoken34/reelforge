/* Diagnostic only: deny directory creation/relocation in one child and its descendants.
 * No host policy changes. The wrapper logs verified restrictions, closes the log, then execs.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <linux/audit.h>
#include <linux/filter.h>
#include <linux/seccomp.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/prctl.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <unistd.h>

#define DENY(nr) BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, nr, 0, 1), \
                 BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | EPERM)

int main(int argc, char **argv) {
    if (argc < 5) { return 125; }
    /* argv: LOG SENTINEL -- PROGRAM ARGS...; all paths selected by trusted probe. */
    struct sock_filter filter[] = {
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, arch)),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, AUDIT_ARCH_X86_64, 1, 0),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_KILL_PROCESS),
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, nr)),
        BPF_JUMP(BPF_JMP | BPF_JSET | BPF_K, 0x40000000, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | EPERM),
        DENY(__NR_mkdir), DENY(__NR_mkdirat), DENY(__NR_rename),
        DENY(__NR_renameat), DENY(__NR_renameat2), DENY(__NR_link), DENY(__NR_linkat),
        DENY(__NR_mount), DENY(__NR_umount2), DENY(__NR_unshare), DENY(__NR_setns),
        DENY(__NR_open_tree), DENY(__NR_move_mount), DENY(__NR_fsopen),
        DENY(__NR_fsconfig), DENY(__NR_fsmount), DENY(__NR_fspick), DENY(__NR_mount_setattr),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW)
    };
    struct sock_fprog program = { (unsigned short)(sizeof(filter)/sizeof(filter[0])), filter };
    if (prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) ||
        prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, &program)) {
        perror("diagnostic seccomp unavailable"); return 125;
    }
    int count = 0;
#define CHECK(call) do { errno = 0; long result = (call); \
    if (result == -1 && errno == EPERM) ++count; } while (0)
    CHECK(syscall(__NR_mkdir, argv[2], 0700));
    CHECK(syscall(__NR_mkdirat, AT_FDCWD, argv[2], 0700));
    CHECK(syscall(__NR_rename, argv[2], argv[2]));
    CHECK(syscall(__NR_renameat, AT_FDCWD, argv[2], AT_FDCWD, argv[2]));
    CHECK(syscall(__NR_renameat2, AT_FDCWD, argv[2], AT_FDCWD, argv[2], 0));
    CHECK(syscall(__NR_link, argv[2], argv[2]));
    CHECK(syscall(__NR_linkat, AT_FDCWD, argv[2], AT_FDCWD, argv[2], 0));
    FILE *log = fopen(argv[1], "a");
    if (!log) return 125;
    fprintf(log, "{\"pid\":%ld,\"ppid\":%ld,\"denial_checks\":7,\"denied\":%d,"
            "\"no_new_privs\":%d,\"seccomp_mode\":%d,\"architecture\":\"x86_64\"}\n",
            (long)getpid(), (long)getppid(), count,
            prctl(PR_GET_NO_NEW_PRIVS, 0, 0, 0, 0), prctl(PR_GET_SECCOMP, 0, 0, 0, 0));
    if (fclose(log) || count != 7) return 125;
    execvp(argv[4], &argv[4]);
    perror("diagnostic exec failed");
    return 125;
}
