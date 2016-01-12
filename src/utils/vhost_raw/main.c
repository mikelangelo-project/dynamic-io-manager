#include <stdio.h>
#include <unistd.h>
#include <errno.h>
#include <fcntl.h>
#include <string.h>
#include "vhost_raw.h"

#define SYS_COPY_TO_USER 316

int main() {
    const char * const id = "w.1";
    struct vhost_worker_stats w;
    u64 ka = vhost_worker_stats_kernel(id);
    printf("%s: ka: %llu\n", id, ka);
    if (ka == 0UL){
        return 1;
    }
    if(syscall(SYS_COPY_TO_USER, &w, (void *)ka, sizeof(w)) == -1) {
        fprintf(stderr, "Error calling syscall: %s\n", strerror(errno));
        return 1;
    }

    printf("%s: total_work_cycles: %llu\n", id, w.total_work_cycles);
    return 0;
}
