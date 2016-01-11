#include <stdio.h>
#include "vhost_raw.h"


int main() {
    const char * const id = "w.1";
    struct vhost_worker_stats *w = remap_vhost_worker(id);
    printf("%s: total_work_cycles: %llu", id, w->total_work_cycles);
    return 0;
}
